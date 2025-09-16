
from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import select

import io, csv, re, json, tempfile, os
from app.config import settings
from app.db import init_db, get_session
from app.models import User, Run
from app.auth import oauth, require_login, require_employee
from app.emailer import send_report_email
from app.sheets import export_to_sheets

# Redaction libs
import pdf_redactor
from PIL import Image, ImageFilter
from docx import Document

app = FastAPI(title="ClearPoint DataApp — Enterprise + Redactor")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, same_site="lax", https_only=True)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def normalize_email(value: str):
    if value is None:
        return None, True
    val = value.strip().lower()
    if not val:
        return "", True
    is_invalid = EMAIL_REGEX.match(val) is None
    return val, is_invalid

def normalize_us_phone(value: str):
    if value is None:
        return None, True
    digits = ''.join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        return '+1' + digits, False
    if len(digits) == 11 and digits.startswith('1'):
        return '+1' + digits[1:], False
    return (value or '').strip(), True

def split_csv_cols(s: str):
    if not s: return []
    return [c.strip() for c in s.split(',') if c.strip()]

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": request.session.get("user"), "brand": settings})

# ---------- Auth ----------
@app.get("/login")
async def login(request: Request):
    # If GOOGLE vars not set, we deliberately show auth=disabled (this is the state in your screenshot).
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        return RedirectResponse(url="/?auth=disabled")
    redirect_uri = settings.OAUTH_REDIRECT_URI or (settings.BASE_URL.rstrip('/') + "/auth/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower()

    # Role via allowlist
    role = "employee" if (settings.ALLOWED_GOOGLE_DOMAINS and any(email.endswith("@"+d) for d in settings.ALLOWED_GOOGLE_DOMAINS)) else "client"

    with get_session() as s:
        existing = s.exec(select(User).where(User.email == email)).first()
        if not existing:
            u = User(email=email, name=userinfo.get("name"), picture=userinfo.get("picture"), role=role)
            s.add(u); s.commit(); s.refresh(u)
            user_id, user_role = u.id, u.role
        else:
            user_id, user_role = existing.id, existing.role

    request.session["user"] = {"id": user_id, "email": email, "name": userinfo.get("name"), "picture": userinfo.get("picture"), "role": user_role}
    return RedirectResponse(url="/")

@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# ---------- CSV Cleaning ----------
@app.post("/api/process")
async def process_csv(
    request: Request,
    file: UploadFile = File(...),
    email_columns: str = Form(default=""),
    phone_columns: str = Form(default=""),
    key_columns: str   = Form(default="")
):
    contents = await file.read()
    text = contents.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    email_cols = split_csv_cols(email_columns)
    phone_cols = split_csv_cols(phone_columns)
    key_cols   = split_csv_cols(key_columns)

    invalid_email_count = 0
    invalid_phone_count = 0

    for r in rows:
        for col in email_cols:
            if col in r:
                r[col], bad = normalize_email(r[col])
                invalid_email_count += 1 if bad else 0
        for col in phone_cols:
            if col in r:
                r[col], bad = normalize_us_phone(r[col])
                invalid_phone_count += 1 if bad else 0

    seen = set()
    deduped = []
    dup_count = 0
    for r in rows:
        key = tuple((r.get(c, '') or '').strip().lower() for c in key_cols) if key_cols else None
        if key_cols:
            if key in seen:
                dup_count += 1
                continue
            seen.add(key)
        deduped.append(r)

    fieldnames = list(deduped[0].keys()) if deduped else (reader.fieldnames or [])

    out_io = io.StringIO()
    writer = csv.DictWriter(out_io, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(deduped)
    cleaned_csv_text = out_io.getvalue()

    preview_rows = deduped[:10]

    summary = {
        "rows_in": len(rows),
        "rows_out": len(deduped),
        "duplicates_removed": dup_count,
        "invalid_emails": invalid_email_count,
        "invalid_phones": invalid_phone_count,
        "columns": fieldnames,
    }

    u = request.session.get("user")
    if u:
        with get_session() as s:
            run = Run(
                owner_user_id=u["id"],
                rows_in=summary["rows_in"],
                rows_out=summary["rows_out"],
                duplicates_removed=summary["duplicates_removed"],
                invalid_emails=summary["invalid_emails"],
                invalid_phones=summary["invalid_phones"],
                columns_csv=",".join(fieldnames),
            )
            s.add(run); s.commit()

    return {"summary": summary, "csv_text": cleaned_csv_text, "preview_rows": preview_rows}

# ---------- Redaction UI ----------
@app.get("/redact", response_class=HTMLResponse)
async def redact_page(request: Request):
    return templates.TemplateResponse("redact.html", {"request": request, "brand": settings, "user": request.session.get("user")})

# ---------- Redaction API ----------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
SSN_RE   = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")

def _pdf_redact_bytes(pdf_bytes: bytes, patterns: list[str]):
    cfg = pdf_redactor.RedactorOptions()
    regs = [re.compile(p, re.I) for p in patterns]
    def content_filter(text):
        for r in regs:
            text = r.sub("█████", text)
        return text
    cfg.content_filters = [(re.compile(r".*", re.S), content_filter)]
    # Also strip metadata
    cfg.metadata_filters = { "Title": lambda v: None, "Producer": lambda v: None, "Creator": lambda v: None }
    out = io.BytesIO()
    pdf_redactor.redactor(cfg, input_stream=io.BytesIO(pdf_bytes), output_stream=out)
    return out.getvalue()

def _docx_redact_bytes(docx_bytes: bytes, patterns: list[str]):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp.write(docx_bytes); tmp.close()
    doc = Document(tmp.name)
    regs = [re.compile(p, re.I) for p in patterns]
    for p in doc.paragraphs:
        for r in regs:
            p.text = r.sub("█████", p.text)
    bio = io.BytesIO()
    doc.save(bio)
    os.unlink(tmp.name)
    return bio.getvalue()

def _image_redact_bytes(img_bytes: bytes, patterns: list[str]):
    # We don't OCR; instead we just allow a quick full-image blur if patterns provided
    # (You can extend to per-box UI later.)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # For now, if any patterns specified, apply a subtle blur to entire image (placeholder safe default).
    redacted = img.filter(ImageFilter.GaussianBlur(radius=8))
    out = io.BytesIO(); redacted.save(out, format="PNG"); return out.getvalue()

@app.post("/api/redact")
async def api_redact(file: UploadFile = File(...),
                     redact_emails: int = Form(0),
                     redact_phones: int = Form(0),
                     redact_ssn: int = Form(0),
                     custom_terms: str = Form("")):
    name = (file.filename or "").lower()
    data = await file.read()
    patterns = []
    if redact_emails: patterns.append(EMAIL_RE.pattern)
    if redact_phones: patterns.append(PHONE_RE.pattern)
    if redact_ssn:    patterns.append(SSN_RE.pattern)
    if custom_terms.strip():
        for t in custom_terms.split(","):
            t = t.strip()
            if not t: continue
            patterns.append(re.escape(t))

    if name.endswith(".pdf"):
        red = _pdf_redact_bytes(data, patterns)
        media = "application/pdf"; ext = "pdf"
    elif name.endswith(".docx"):
        red = _docx_redact_bytes(data, patterns)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"; ext = "docx"
    elif name.endswith((".png",".jpg",".jpeg")):
        red = _image_redact_bytes(data, patterns)
        media = "image/png"; ext = "png"
    else:
        return JSONResponse({"error": "Unsupported file type. Use PDF, DOCX, PNG, or JPG."}, status_code=400)

    out_name = f"redacted_{os.path.basename(name) or 'file.'+ext}"
    return StreamingResponse(io.BytesIO(red), media_type=media, headers={"Content-Disposition": f"attachment; filename={out_name}"} )

@app.get("/healthz")
async def health():
    return {"ok": True}

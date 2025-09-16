
from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import select
import io, csv, re, json

from app.config import settings
from app.db import init_db, get_session
from app.models import User, Run

# Auth (Authlib)
from authlib.integrations.starlette_client import OAuth
oauth = OAuth()
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Redactor Pro (PyMuPDF)
import fitz
from PIL import Image, ImageDraw

app = FastAPI(title="ClearPoint Enterprise + Redactor Pro")
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

# ---------- UI ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": request.session.get("user"), "brand": settings})

@app.get("/redact", response_class=HTMLResponse)
async def redact_page(request: Request):
    return templates.TemplateResponse("redactor_pro.html", {"request": request, "user": request.session.get("user"), "brand": settings})

# ---------- Auth ----------
@app.get("/login")
async def login(request: Request):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        return RedirectResponse(url="/?auth=disabled")
    redirect_uri = settings.OAUTH_REDIRECT_URI or (settings.BASE_URL.rstrip('/') + "/auth/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower()
    role = "employee" if (settings.ALLOWED_GOOGLE_DOMAINS and any(email.endswith("@"+d) for d in settings.ALLOWED_GOOGLE_DOMAINS)) else "client"
    from app.db import get_session
    from app.models import User
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

# ---------- CSV API ----------
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

# ---------- Redactor Pro API ----------
@app.post("/api/preview_pdf")
async def preview_pdf(file: UploadFile = File(...)):
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    images = []
    for i in range(min(5, len(doc))):
        pix = doc.load_page(i).get_pixmap(dpi=144)
        images.append(pix.tobytes("png"))
    import base64
    b64s = [base64.b64encode(im).decode("ascii") for im in images]
    return {"pages": b64s}

@app.post("/api/redact_pdf")
async def redact_pdf(file: UploadFile = File(...), rects_json: str = Form("[]")):
    rects = json.loads(rects_json)
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    scale = 72/144
    for r in rects:
        page = doc.load_page(int(r["page"]))
        rect = fitz.Rect(r["x"]*scale, r["y"]*scale, (r["x"]+r["w"])*scale, (r["y"]+r["h"])*scale)
        page.add_redact_annot(rect, fill=(0,0,0))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
    out = io.BytesIO(); doc.save(out)
    return StreamingResponse(io.BytesIO(out.getvalue()), media_type="application/pdf",
        headers={"Content-Disposition":"attachment; filename=redacted.pdf"})

@app.post("/api/redact_image")
async def redact_image(file: UploadFile = File(...), rects_json: str = Form("[]")):
    rects = json.loads(rects_json)
    im = Image.open(io.BytesIO(await file.read())).convert("RGB")
    draw = ImageDraw.Draw(im)
    for r in rects:
        x,y,w,h = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
        draw.rectangle((x,y,x+w,y+h), fill=(0,0,0))
    out = io.BytesIO(); im.save(out, format="PNG")
    return StreamingResponse(io.BytesIO(out.getvalue()), media_type="image/png",
        headers={"Content-Disposition":"attachment; filename=redacted.png"})

@app.get("/healthz")
async def health():
    return {"ok": True}

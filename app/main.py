from fastapi import FastAPI, File, Form, UploadFile, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from sqlmodel import select

import io, csv, re, json
from app.config import settings
from app.db import init_db, get_session
from app.models import User, Run
from app.auth import oauth, require_login
from app.emailer import send_report_email
from app.sheets import export_to_sheets

app = FastAPI(title="ClearPoint DataApp — Enterprise")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

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
    if not s:
        return []
    return [c.strip() for c in s.split(',') if c.strip()]

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "brand": settings})

# ---------- Auth routes
@app.get("/login")
async def login(request: Request):
    if not oauth._clients.get("google"):
        return RedirectResponse(url="/?auth=disabled")
    redirect_uri = settings.OAUTH_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        return RedirectResponse(url="/?auth=failed")
    # store in DB if not exists
    from app.db import get_session
    with get_session() as s:
        existing = s.exec(select(User).where(User.email == userinfo["email"])).first()
        if not existing:
            u = User(email=userinfo["email"], name=userinfo.get("name"), picture=userinfo.get("picture"))
            s.add(u)
            s.commit()
            s.refresh(u)
            user_id = u.id
        else:
            user_id = existing.id
    request.session["user"] = {"id": user_id, "email": userinfo["email"], "name": userinfo.get("name"), "picture": userinfo.get("picture")}
    return RedirectResponse(url="/")

@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# ---------- API
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

    # Persist run if logged in
    user = request.session.get("user")
    if user:
        from app.db import get_session
        from app.models import Run
        with get_session() as s:
            run = Run(
                user_id=user["id"],
                rows_in=summary["rows_in"],
                rows_out=summary["rows_out"],
                duplicates_removed=summary["duplicates_removed"],
                invalid_emails=summary["invalid_emails"],
                invalid_phones=summary["invalid_phones"],
                columns_csv=",".join(fieldnames),
                sample_json=json.dumps(preview_rows)[:20000]
            )
            s.add(run)
            s.commit()

    return {"summary": summary, "csv_text": cleaned_csv_text, "preview_rows": preview_rows}

@app.post("/api/email_report")
async def email_report(request: Request, to_email: str = Form(...), html: str = Form(...)):
    data = send_report_email(to_email=to_email, subject="Your ClearPoint Report", html=html)
    return data

@app.post("/api/export_to_sheets")
async def export_sheet(csv_text: str = Form(...)):
    res = export_to_sheets(csv_text)
    return res

@app.get("/dashboard", response_class=HTMLResponse)
@require_login
async def dashboard(request: Request):
    from app.db import get_session
    from app.models import Run
    from sqlmodel import select
    with get_session() as s:
        user = request.session.get("user")
        runs = s.exec(select(Run).where(Run.user_id == user["id"]).order_by(Run.created_at.desc()).limit(100)).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "runs": runs, "brand": settings, "user": request.session.get("user")})

@app.get("/healthz")
async def health():
    return {"ok": True}

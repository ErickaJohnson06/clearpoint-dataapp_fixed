from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import io, csv, re

app = FastAPI(title="ClearPoint DataApp — Pro")

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

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post('/api/process')
async def process_csv(
    file: UploadFile = File(...),
    email_columns: str = Form(default=''),
    phone_columns: str = Form(default=''),
    key_columns: str   = Form(default='')
):
    contents = await file.read()
    text = contents.decode('utf-8', errors='replace')
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

    if deduped:
        fieldnames = list(deduped[0].keys())
    else:
        fieldnames = reader.fieldnames or []

    out_io = io.StringIO()
    writer = csv.DictWriter(out_io, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(deduped)
    cleaned_csv_text = out_io.getvalue()

    preview_rows = deduped[:10]

    summary = {
        'rows_in': len(rows),
        'rows_out': len(deduped),
        'duplicates_removed': dup_count,
        'invalid_emails': invalid_email_count,
        'invalid_phones': invalid_phone_count,
        'columns': fieldnames,
    }
    return {'summary': summary, 'csv_text': cleaned_csv_text, 'preview_rows': preview_rows}

@app.get('/healthz')
async def health():
    return {'ok': True}

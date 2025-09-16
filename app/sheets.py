import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from app.config import settings

def export_to_sheets(csv_text: str):
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON or not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
        return {"ok": False, "error": "Sheets not configured"}
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
    title = datetime.utcnow().strftime("Cleaned %Y-%m-%d %H:%M")
    ws = sh.add_worksheet(title=title, rows="1", cols="1")
    rows = [row.split(",") for row in csv_text.strip().split("\n")]
    ws.resize(rows=len(rows), cols=max(len(r) for r in rows))
    ws.update("A1", rows)
    return {"ok": True, "worksheet": title}

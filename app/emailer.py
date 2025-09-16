import requests
from app.config import settings

def send_report_email(to_email: str, subject: str, html: str, attachments=None):
    if not settings.RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not configured"}
    url = "https://api.resend.com/emails"
    payload = {
        "from": settings.RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if attachments:
        payload["attachments"] = attachments
    headers = {"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"status_code": r.status_code, "text": r.text}
    return data

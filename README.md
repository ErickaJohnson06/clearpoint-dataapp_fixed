# ClearPoint DataApp — Enterprise

Features:
- Google Sign-In (OAuth2)
- Per-user run history (SQLite + SQLModel)
- Branded UI (logo, colors, tagline via ENV)
- CSV preview, CSV/XLSX download, printable report (Save as PDF)
- Email report via Resend (optional)
- Export to Google Sheets (optional)

## Required ENV
- `SECRET_KEY` (any random string)
- Optional branding: `BRAND_NAME`, `BRAND_TAGLINE`, `BRAND_LOGO_URL`, `BRAND_PRIMARY_HEX`

## Google OAuth (optional)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `OAUTH_REDIRECT_URI` → `https://<your-app>.onrender.com/auth/callback`

## Email via Resend (optional)
- `RESEND_API_KEY`
- `RESEND_FROM` (e.g., noreply@yourdomain.com)

## Google Sheets (optional)
- `GOOGLE_SERVICE_ACCOUNT_JSON` → paste the full JSON string for the service account
- `GOOGLE_SHEETS_SPREADSHEET_ID`

## Run
```bash
uvicorn app.main:app --reload
```

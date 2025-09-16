
# ClearPoint DataApp — Enterprise + Redactor

- CSV cleaner (normalize emails/phones, dedupe) + Report (PDF), Sheets export, email via Resend
- Google Sign-In (set GOOGLE_* envs). If you see `auth=disabled`, your GOOGLE envs are not set.
- **Redactor**: /redact supports PDF (pdf-redactor, text removal + metadata strip), DOCX (regex replace), PNG/JPG (full-image blur placeholder).

## Required ENV
- SECRET_KEY
- BASE_URL (e.g., https://your-app.onrender.com)

## Google OAuth
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- OAUTH_REDIRECT_URI = https://<your-app>/auth/callback
- Optional: ALLOWED_GOOGLE_DOMAINS = yourcompany.com


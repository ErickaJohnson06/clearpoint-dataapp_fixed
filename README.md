# ClearPoint DataApp — Enterprise Orgs

**New**
- Google Sign-In hardened: BASE_URL + OAUTH_REDIRECT_URI + Domain allowlist
- Roles: **employee** vs **client**; employees see all runs, clients see only their own
- Admin page to manage user roles
- Everything from Pro: preview, CSV/XLSX, report (print-to-PDF), email via Resend, Google Sheets export

## Required ENV
- `SECRET_KEY`: long random string
- `BASE_URL`: your full Render URL, e.g. `https://clearpoint-dataapp.onrender.com`

## Google OAuth (Console + Render ENV)
- In Google Cloud Console (Credentials → OAuth 2.0 Client IDs):
  - Authorized JavaScript origin: `https://<your-render-url>`
  - Authorized redirect URI: `https://<your-render-url>/auth/callback`
- In Render (Environment):
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `OAUTH_REDIRECT_URI` = `https://<your-render-url>/auth/callback`
  - Optional: `ALLOWED_GOOGLE_DOMAINS` = `yourcompany.com,anotherdomain.com`

## Branding (optional)
- `BRAND_NAME`, `BRAND_TAGLINE`, `BRAND_LOGO_URL`, `BRAND_PRIMARY_HEX`

## Email (optional)
- `RESEND_API_KEY`, `RESEND_FROM`

## Google Sheets (optional)
- `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEETS_SPREADSHEET_ID`

## Roles
- If `ALLOWED_GOOGLE_DOMAINS` is set, users from those domains are tagged `employee`; others are `client`.
- Employees can access `/admin/users` to change roles.

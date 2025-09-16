import os

class Settings:
    APP_NAME = os.getenv("BRAND_NAME", "ClearPoint Data Services")
    TAGLINE = os.getenv("BRAND_TAGLINE", "Accuracy You Can Trust")
    LOGO_URL = os.getenv("BRAND_LOGO_URL", "")  # Optional
    PRIMARY_HEX = os.getenv("BRAND_PRIMARY_HEX", "#06b6d4")  # cyan-500 default

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")  # for session cookies

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")  # e.g. https://yourapp.onrender.com/auth/callback

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clearpoint.db")

    # Email (Resend)
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM = os.getenv("RESEND_FROM", "noreply@clearpoint.example")

    # Google Sheets (Service Account JSON) + target spreadsheet
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")  # JSON string
    GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

settings = Settings()

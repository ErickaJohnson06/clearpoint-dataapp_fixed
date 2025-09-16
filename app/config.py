
import os

class Settings:
    APP_NAME = os.getenv("BRAND_NAME", "ClearPoint Data Services")
    TAGLINE = os.getenv("BRAND_TAGLINE", "Accuracy You Can Trust")
    LOGO_URL = os.getenv("BRAND_LOGO_URL", "")
    PRIMARY_HEX = os.getenv("BRAND_PRIMARY_HEX", "#06b6d4")

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    BASE_URL = os.getenv("BASE_URL", "")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")

    ALLOWED_GOOGLE_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOWED_GOOGLE_DOMAINS", "").split(",") if d.strip()]

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clearpoint.db")

    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM = os.getenv("RESEND_FROM", "noreply@clearpoint.example")

settings = Settings()

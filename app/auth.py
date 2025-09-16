
from starlette.requests import Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from app.config import settings

oauth = OAuth()
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

def require_login(handler):
    async def wrapper(request: Request, *args, **kwargs):
        if not request.session.get("user"):
            return RedirectResponse(url="/login")
        return await handler(request, *args, **kwargs)
    return wrapper

def require_employee(handler):
    async def wrapper(request: Request, *args, **kwargs):
        u = request.session.get("user")
        if not u:
            return RedirectResponse(url="/login")
        if u.get("role") != "employee":
            return RedirectResponse(url="/?forbidden=1")
        return await handler(request, *args, **kwargs)
    return wrapper

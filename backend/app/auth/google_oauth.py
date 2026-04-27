"""
Google OAuth2 client.
Exchanges authorization code for tokens and fetches the user's Google profile.
"""
from typing import Optional
import httpx
import structlog

from app.config import get_settings
from app.core.errors import UnauthorizedError

logger = structlog.get_logger(__name__)
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GOOGLE_SCOPES = "openid email profile"


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Build the Google OAuth2 authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access + id tokens."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        logger.warning("Google token exchange failed", status=resp.status_code, body=resp.text)
        raise UnauthorizedError("Google authentication failed. Please try again.")
    return resp.json()


async def fetch_google_user_profile(access_token: str) -> dict:
    """Fetch the authenticated user's Google profile."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        logger.warning("Google userinfo fetch failed", status=resp.status_code)
        raise UnauthorizedError("Could not fetch user profile from Google.")

    profile = resp.json()

    if not profile.get("email_verified", False):
        raise UnauthorizedError("Google account email is not verified.")

    return {
        "provider_subject": profile["sub"],
        "email": profile["email"],
        "full_name": profile.get("name"),
        "avatar_url": profile.get("picture"),
    }
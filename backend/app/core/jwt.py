"""
JWT utilities — issue and decode JWT access tokens.
Claims: sub (user_id), email, active_workspace_id, role, exp
"""
from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from jose import JWTError, jwt

from app.config import get_settings
from app.core.dates import utcnow
from app.core.errors import UnauthorizedError

logger = structlog.get_logger(__name__)
settings = get_settings()


def create_access_token(
    user_id: UUID,
    email: str,
    active_workspace_id: UUID,
    role: str,
) -> str:
    """Issue a JWT access token with workspace context."""
    now = utcnow()
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    claims: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "active_workspace_id": str(active_workspace_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(
        claims,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises UnauthorizedError if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT decode failed", error=str(exc))
        raise UnauthorizedError("Invalid or expired token.")

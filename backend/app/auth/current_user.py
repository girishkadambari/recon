"""
CurrentUserContext — the authenticated user + workspace context for every request.
Also provides the get_current_user_context FastAPI dependency.
"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.errors import UnauthorizedError, ForbiddenError
from app.core.jwt import decode_access_token
from app.domain.enums.auth_enums import WorkspaceRole

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUserContext(BaseModel):
    """Decoded JWT context attached to every protected request."""

    user_id: uuid.UUID
    email: str
    active_workspace_id: uuid.UUID
    role: str  # WorkspaceRole value


def get_current_user_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUserContext:
    """
    FastAPI dependency — validates Bearer token and returns CurrentUserContext.
    Raises UnauthorizedError if token is missing or invalid.
    """
    if not credentials:
        raise UnauthorizedError("Authentication required. Provide a Bearer token.")

    payload = decode_access_token(credentials.credentials)

    try:
        return CurrentUserContext(
            user_id=uuid.UUID(payload["sub"]),
            email=payload["email"],
            active_workspace_id=uuid.UUID(payload["active_workspace_id"]),
            role=payload["role"],
        )
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid token claims.") from exc


def require_role(min_role: WorkspaceRole):
    """
    Dependency factory — requires the current user to have at least min_role.
    Usage: Depends(require_role(WorkspaceRole.ADMIN))
    """
    def _guard(ctx: CurrentUserContext = Depends(get_current_user_context)) -> CurrentUserContext:
        from app.core.security import require_role as _require_role
        _require_role(ctx.role, min_role)
        return ctx

    return _guard

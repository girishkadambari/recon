"""
Auth routes.

GET  /api/auth/google/login      — Redirect to Google OAuth
GET  /api/auth/google/callback   — Handle OAuth callback, return JWT
POST /api/auth/logout            — Logout (client-side token drop)
GET  /api/auth/me                — Get current user and workspace
POST /api/auth/dev-login         — LOCAL ONLY: dev bypass login
"""
from __future__ import annotations
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.auth_schemas import DevLoginRequest, MeResponse, TokenResponse, UserProfile, WorkspaceSummary
from app.auth.auth_service import AuthService
from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.auth.google_oauth import exchange_code_for_tokens, fetch_google_user_profile, get_google_auth_url
from app.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.dependencies import get_db
from app.domain.repositories.user_repository import UserRepository
from app.domain.services.workspace_service import WorkspaceService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.get("/google/login", summary="Redirect to Google OAuth")
def google_login(request: Request) -> RedirectResponse:
    """Redirects the browser to Google's OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "GOOGLE_OAUTH_NOT_CONFIGURED",
                    "message": "Google OAuth is not configured. Use /api/auth/dev-login in local mode.",
                    "details": {},
                }
            },
        )
    auth_url = get_google_auth_url()
    return RedirectResponse(url=auth_url)


@router.get("/google/callback", summary="Google OAuth callback")
async def google_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Handles Google OAuth callback, creates/finds user, returns JWT."""
    if error or not code:
        raise UnauthorizedError(f"Google auth failed: {error or 'no code received'}")

    tokens = await exchange_code_for_tokens(code)
    profile = await fetch_google_user_profile(tokens["access_token"])

    svc = AuthService(db)
    result = svc.handle_google_login(
        provider_subject=profile["provider_subject"],
        email=profile["email"],
        full_name=profile.get("full_name"),
        avatar_url=profile.get("avatar_url"),
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    # For MVP, redirect to frontend with access_token in query param
    url = f"{settings.FRONTEND_BASE_URL}/?access_token={result['access_token']}"
    return RedirectResponse(url=url)


@router.post("/logout", summary="Logout")
def logout(
    ctx: CurrentUserContext = Depends(get_current_user_context),
) -> JSONResponse:
    """
    Client-side logout — instructs the client to discard the JWT.
    For MVP, tokens are stateless (no server-side revocation).
    """
    logger.info("User logged out", user_id=str(ctx.user_id))
    return JSONResponse(
        status_code=200,
        content={"data": {"message": "Logged out successfully."}, "request_id": None},
    )


@router.get("/me", summary="Get current user and workspace", response_model=None)
def get_me(
    request: Request,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Returns the authenticated user's profile and active workspace details."""
    user_repo = UserRepository(db)
    workspace_svc = WorkspaceService(db)

    user = user_repo.get_by_id(ctx.user_id)
    if not user:
        raise UnauthorizedError("User not found.")

    workspace = workspace_svc.get_workspace(ctx.active_workspace_id)

    user_data = UserProfile.model_validate(user).model_dump(mode="json")
    ws_data = WorkspaceSummary(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        status=workspace.status,
        role=ctx.role,
    ).model_dump(mode="json")

    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": {"user": user_data, "active_workspace": ws_data},
            "request_id": request_id,
        },
    )


@router.post("/dev-login", summary="Dev login (LOCAL ONLY)", include_in_schema=True)
def dev_login(
    payload: DevLoginRequest,
    request: Request = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Issues a real JWT without Google OAuth.
    Only available when APP_ENV=local or APP_ENV=test.
    """
    if not settings.is_local:
        raise ForbiddenError("Dev login is only available in local/test environments.")

    svc = AuthService(db)
    result = svc.handle_dev_login(
        email=payload.email,
        full_name=payload.full_name,
    )

    request_id = getattr(request.state, "request_id", None) if request else None
    return JSONResponse(
        status_code=200,
        content={"data": result, "request_id": request_id},
    )
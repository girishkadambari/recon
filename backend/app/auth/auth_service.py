"""
AuthService — handles the full login/signup flow.
Business logic only — no HTTP concerns here.
"""
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.dates import utcnow
from app.core.jwt import create_access_token
from app.domain.enums.auth_enums import AuthProvider, WorkspaceRole
from app.domain.enums.audit_enums import AuditEventType
from app.domain.repositories.user_repository import UserRepository
from app.domain.services.audit_service import AuditService
from app.domain.services.workspace_service import WorkspaceService
from app.core.constants import ENTITY_TYPE_USER, ENTITY_TYPE_WORKSPACE

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.workspace_svc = WorkspaceService(db)
        self.audit_svc = AuditService(db)

    def handle_google_login(
        self,
        provider_subject: str,
        email: str,
        full_name: str | None,
        avatar_url: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """
        Find or create user by Google provider_subject.
        On first login:
          - creates User
          - creates default Workspace
          - creates WorkspaceMember with OWNER role
          - logs WORKSPACE_CREATED audit event
        Always logs USER_SIGNED_IN.
        Returns {"access_token": ..., "token_type": "bearer"}.
        """
        is_new_user = False
        user = self.user_repo.get_by_provider(AuthProvider.GOOGLE, provider_subject)

        if not user:
            logger.info("New user signing up via Google", email=email)
            user = self.user_repo.create(
                email=email,
                auth_provider=AuthProvider.GOOGLE,
                provider_subject=provider_subject,
                full_name=full_name,
                avatar_url=avatar_url,
            )
            is_new_user = True
        else:
            # Update profile fields that may have changed
            user.full_name = full_name or user.full_name
            user.avatar_url = avatar_url or user.avatar_url

        # Always update last login
        now = utcnow()
        user.last_login_at = now
        user.updated_at = now

        # ── First login: create default workspace ────────────────────
        if is_new_user:
            workspace_name = f"{(full_name or email.split('@')[0]).title()}'s Workspace"
            workspace = self.workspace_svc.create_workspace(
                name=workspace_name,
                created_by_user_id=user.id,
            )
            self.workspace_svc.add_member(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceRole.OWNER,
                added_by_user_id=user.id,
            )
            self.audit_svc.log(
                event_type=AuditEventType.WORKSPACE_CREATED,
                actor_user_id=user.id,
                workspace_id=workspace.id,
                entity_type=ENTITY_TYPE_WORKSPACE,
                entity_id=workspace.id,
                metadata={"workspace_name": workspace.name},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            active_workspace_id = workspace.id
            active_role = WorkspaceRole.OWNER
        else:
            # Get the user's primary workspace (first active membership)
            workspaces = self.workspace_svc.list_for_user(user.id)
            if workspaces:
                ws = workspaces[0]
                active_workspace_id = ws.id
                member = self.workspace_svc.list_members(ws.id)
                active_role = next(
                    (m.role for m in member if m.user_id == user.id), WorkspaceRole.MEMBER
                )
            else:
                # Edge case: user exists but has no workspace — create one
                workspace = self.workspace_svc.create_workspace(
                    name=f"{(full_name or email.split('@')[0]).title()}'s Workspace",
                    created_by_user_id=user.id,
                )
                self.workspace_svc.add_member(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role=WorkspaceRole.OWNER,
                    added_by_user_id=user.id,
                )
                active_workspace_id = workspace.id
                active_role = WorkspaceRole.OWNER

        # ── Audit: sign in ───────────────────────────────────────────
        self.audit_svc.log(
            event_type=AuditEventType.USER_SIGNED_IN,
            actor_user_id=user.id,
            workspace_id=active_workspace_id,
            entity_type=ENTITY_TYPE_USER,
            entity_id=user.id,
            metadata={"email": email, "is_new_user": is_new_user},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.commit()

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            active_workspace_id=active_workspace_id,
            role=active_role,
        )

        logger.info(
            "User authenticated",
            user_id=str(user.id),
            email=email,
            is_new=is_new_user,
            workspace_id=str(active_workspace_id),
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "workspace_id": str(active_workspace_id),
            "is_new_user": is_new_user,
        }

    def handle_dev_login(
        self,
        email: str,
        full_name: str | None = None,
    ) -> dict:
        """
        Local-only dev login — creates or finds user without Google OAuth.
        MUST only be used when APP_ENV is local or test.
        """
        from app.config import get_settings
        settings = get_settings()
        if not settings.is_local:
            from app.core.errors import ForbiddenError
            raise ForbiddenError("Dev login is only available in local/test environments.")

        return self.handle_google_login(
            provider_subject=f"dev:{email}",
            email=email,
            full_name=full_name or "Dev User",
            avatar_url=None,
        )

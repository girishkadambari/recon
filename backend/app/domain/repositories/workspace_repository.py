"""
Workspace repository — all DB queries for workspaces and workspace members.
All workspace queries are scoped to membership.
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.domain.models.workspace import Workspace
from app.domain.models.workspace_member import WorkspaceMember
from app.domain.enums.auth_enums import WorkspaceMemberStatus, WorkspaceRole, WorkspaceStatus


class WorkspaceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Workspaces ───────────────────────────────────────────────────

    def get_by_id(self, workspace_id: uuid.UUID) -> Optional[Workspace]:
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def get_by_slug(self, slug: str) -> Optional[Workspace]:
        return self.db.query(Workspace).filter(Workspace.slug == slug).first()

    def list_for_user(self, user_id: uuid.UUID) -> list[Workspace]:
        """List all workspaces the user is a member of."""
        return (
            self.db.query(Workspace)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.id,
            )
            .filter(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.status == WorkspaceStatus.ACTIVE,
            )
            .all()
        )

    def create(
        self,
        name: str,
        created_by_user_id: uuid.UUID,
        slug: Optional[str] = None,
    ) -> Workspace:
        ws = Workspace(
            name=name,
            slug=slug,
            status=WorkspaceStatus.ACTIVE,
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(ws)
        self.db.flush()
        return ws

    def update(
        self,
        workspace_id: uuid.UUID,
        name: str,
        updated_by_user_id: uuid.UUID,
    ) -> Optional[Workspace]:
        from app.core.dates import utcnow
        ws = self.get_by_id(workspace_id)
        if ws:
            ws.name = name
            ws.updated_by_user_id = updated_by_user_id
            ws.updated_at = utcnow()
        return ws

    def delete(
        self,
        workspace_id: uuid.UUID,
        updated_by_user_id: uuid.UUID,
    ) -> Optional[Workspace]:
        from app.core.dates import utcnow
        ws = self.get_by_id(workspace_id)
        if ws:
            ws.status = WorkspaceStatus.DELETED
            ws.updated_by_user_id = updated_by_user_id
            ws.updated_at = utcnow()
        return ws

    # ── Workspace Members ────────────────────────────────────────────

    def get_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Optional[WorkspaceMember]:
        return (
            self.db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .first()
        )

    def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        return (
            self.db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .all()
        )

    def create_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        created_by_user_id: uuid.UUID,
        invited_by_user_id: Optional[uuid.UUID] = None,
    ) -> WorkspaceMember:
        from app.core.dates import utcnow

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
            invited_by_user_id=invited_by_user_id,
            joined_at=utcnow(),
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def update_member_role(
        self,
        workspace_id: uuid.UUID,
        member_id: uuid.UUID,
        new_role: str,
        updated_by_user_id: uuid.UUID,
    ) -> Optional[WorkspaceMember]:
        from app.core.dates import utcnow

        member = (
            self.db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.id == member_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
            .first()
        )
        if member:
            member.role = new_role
            member.updated_by_user_id = updated_by_user_id
            member.updated_at = utcnow()
        return member
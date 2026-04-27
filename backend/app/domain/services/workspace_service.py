"""
WorkspaceService — workspace and membership business logic.
"""
from __future__ import annotations
from typing import Optional
import re
import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ForbiddenError
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_member import WorkspaceMember
from app.domain.repositories.workspace_repository import WorkspaceRepository
from app.domain.enums.auth_enums import WorkspaceMemberStatus, WorkspaceRole


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.repo = WorkspaceRepository(db)

    def create_workspace(
        self,
        name: str,
        created_by_user_id: uuid.UUID,
    ) -> Workspace:
        base_slug = _slugify(name)
        slug = self._unique_slug(base_slug)
        return self.repo.create(
            name=name,
            created_by_user_id=created_by_user_id,
            slug=slug,
        )

    def update_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str,
        updated_by_user_id: uuid.UUID,
    ) -> Workspace:
        ws = self.repo.update(
            workspace_id=workspace_id,
            name=name,
            updated_by_user_id=updated_by_user_id,
        )
        if not ws:
            raise NotFoundError(f"Workspace {workspace_id} not found.")
        return ws

    def delete_workspace(
        self,
        workspace_id: uuid.UUID,
        updated_by_user_id: uuid.UUID,
    ) -> Workspace:
        ws = self.repo.delete(
            workspace_id=workspace_id,
            updated_by_user_id=updated_by_user_id,
        )
        if not ws:
            raise NotFoundError(f"Workspace {workspace_id} not found.")
        return ws

    def _unique_slug(self, base: str) -> str:
        slug = base
        counter = 1
        while self.repo.get_by_slug(slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def get_workspace(self, workspace_id: uuid.UUID) -> Workspace:
        ws = self.repo.get_by_id(workspace_id)
        if not ws:
            raise NotFoundError(f"Workspace {workspace_id} not found.")
        return ws

    def list_for_user(self, user_id: uuid.UUID) -> list[Workspace]:
        return self.repo.list_for_user(user_id)

    def assert_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
        """Raise ForbiddenError if user is not an active member of the workspace."""
        member = self.repo.get_member(workspace_id, user_id)
        if not member or member.status != WorkspaceMemberStatus.ACTIVE:
            raise ForbiddenError("You do not have access to this workspace.")
        return member

    def get_member_role(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
        member = self.repo.get_member(workspace_id, user_id)
        return member.role if member else None

    def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        return self.repo.list_members(workspace_id)

    def add_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        added_by_user_id: uuid.UUID,
    ) -> WorkspaceMember:
        existing = self.repo.get_member(workspace_id, user_id)
        if existing:
            # Reactivate if previously removed
            existing.status = WorkspaceMemberStatus.ACTIVE
            existing.role = role
            return existing
        return self.repo.create_member(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            created_by_user_id=added_by_user_id,
            invited_by_user_id=added_by_user_id,
        )

    def update_member_role(
        self,
        workspace_id: uuid.UUID,
        member_id: uuid.UUID,
        new_role: str,
        updated_by_user_id: uuid.UUID,
    ) -> WorkspaceMember:
        member = self.repo.update_member_role(
            workspace_id=workspace_id,
            member_id=member_id,
            new_role=new_role,
            updated_by_user_id=updated_by_user_id,
        )
        if not member:
            raise NotFoundError(f"Member {member_id} not found in workspace {workspace_id}.")
        return member
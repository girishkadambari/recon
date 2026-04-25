"""
Workspace routes.

GET   /api/workspaces                              — List user's workspaces
POST  /api/workspaces                              — Create workspace
GET   /api/workspaces/{workspace_id}               — Get workspace
GET   /api/workspaces/{workspace_id}/members       — List members
POST  /api/workspaces/{workspace_id}/members/invite
PATCH /api/workspaces/{workspace_id}/members/{member_id}/role
"""
import uuid

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.auth_schemas import (
    InviteMemberRequest,
    UpdateMemberRoleRequest,
    WorkspaceCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import require_role as role_guard
from app.dependencies import get_db
from app.domain.enums.auth_enums import WorkspaceRole
from app.domain.repositories.user_repository import UserRepository
from app.domain.services.audit_service import AuditService
from app.domain.services.workspace_service import WorkspaceService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", summary="List user's workspaces")
def list_workspaces(
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = WorkspaceService(db)
    workspaces = svc.list_for_user(ctx.user_id)
    data = [WorkspaceResponse.model_validate(ws).model_dump(mode="json") for ws in workspaces]
    return JSONResponse(status_code=200, content={"data": data})


@router.post("", summary="Create a new workspace")
def create_workspace(
    payload: WorkspaceCreateRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = WorkspaceService(db)
    audit_svc = AuditService(db)

    workspace = svc.create_workspace(name=payload.name, created_by_user_id=ctx.user_id)
    svc.add_member(
        workspace_id=workspace.id,
        user_id=ctx.user_id,
        role=WorkspaceRole.OWNER,
        added_by_user_id=ctx.user_id,
    )
    audit_svc.log(
        event_type="WORKSPACE_CREATED",
        actor_user_id=ctx.user_id,
        workspace_id=workspace.id,
        entity_type="workspace",
        entity_id=workspace.id,
        metadata={"workspace_name": workspace.name},
    )
    db.commit()

    return JSONResponse(
        status_code=201,
        content={"data": WorkspaceResponse.model_validate(workspace).model_dump(mode="json")},
    )


@router.get("/{workspace_id}", summary="Get workspace details")
def get_workspace(
    workspace_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = WorkspaceService(db)
    svc.assert_member(workspace_id, ctx.user_id)
    workspace = svc.get_workspace(workspace_id)
    return JSONResponse(
        status_code=200,
        content={"data": WorkspaceResponse.model_validate(workspace).model_dump(mode="json")},
    )


@router.get("/{workspace_id}/members", summary="List workspace members")
def list_members(
    workspace_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = WorkspaceService(db)
    svc.assert_member(workspace_id, ctx.user_id)
    members = svc.list_members(workspace_id)
    data = [WorkspaceMemberResponse.model_validate(m).model_dump(mode="json") for m in members]
    return JSONResponse(status_code=200, content={"data": data})


@router.post("/{workspace_id}/members/invite", summary="Invite a member")
def invite_member(
    workspace_id: uuid.UUID,
    payload: InviteMemberRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    # Only ADMIN+ can invite
    role_guard(ctx.role, WorkspaceRole.ADMIN)

    svc = WorkspaceService(db)
    svc.assert_member(workspace_id, ctx.user_id)

    user_repo = UserRepository(db)
    target_user = user_repo.get_by_email(payload.email)
    if not target_user:
        raise NotFoundError(f"No user found with email '{payload.email}'. They must sign up first.")

    member = svc.add_member(
        workspace_id=workspace_id,
        user_id=target_user.id,
        role=payload.role,
        added_by_user_id=ctx.user_id,
    )
    db.commit()

    return JSONResponse(
        status_code=200,
        content={"data": WorkspaceMemberResponse.model_validate(member).model_dump(mode="json")},
    )


@router.patch("/{workspace_id}/members/{member_id}/role", summary="Update member role")
def update_member_role(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    role_guard(ctx.role, WorkspaceRole.ADMIN)

    svc = WorkspaceService(db)
    svc.assert_member(workspace_id, ctx.user_id)
    member = svc.update_member_role(
        workspace_id=workspace_id,
        member_id=member_id,
        new_role=payload.role,
        updated_by_user_id=ctx.user_id,
    )
    db.commit()

    return JSONResponse(
        status_code=200,
        content={"data": WorkspaceMemberResponse.model_validate(member).model_dump(mode="json")},
    )

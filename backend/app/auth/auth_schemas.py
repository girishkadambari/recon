"""
Auth and workspace Pydantic schemas (request/response).
"""
from typing import Optional
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


# ── Auth Responses ───────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    workspace_id: str
    is_new_user: bool = False


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    status: str
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: Optional[str]
    status: str
    role: str  # the current user's role in this workspace

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserProfile
    active_workspace: WorkspaceSummary


# ── Dev login request (local only) ───────────────────────────────────

class DevLoginRequest(BaseModel):
    email: str
    full_name: Optional[str] = None


# ── Workspace schemas ────────────────────────────────────────────────

class WorkspaceCreateRequest(BaseModel):
    name: str


class WorkspaceUpdateRequest(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    role: str
    status: str
    joined_at: Optional[datetime]

    @classmethod
    def model_validate(cls, obj, **kwargs):
        res = super().model_validate(obj, **kwargs)
        if hasattr(obj, "user") and obj.user:
            res.user_name = obj.user.full_name
            res.user_email = obj.user.email
        return res

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: str
    role: str = "MEMBER"


class UpdateMemberRoleRequest(BaseModel):
    role: str


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    actor_user_id: Optional[uuid.UUID]
    actor_name: Optional[str] = None
    entity_type: Optional[str]
    entity_id: Optional[uuid.UUID]
    metadata_json: Optional[dict]
    created_at: datetime

    @classmethod
    def model_validate(cls, obj, **kwargs):
        res = super().model_validate(obj, **kwargs)
        if hasattr(obj, "actor") and obj.actor:
            res.actor_name = obj.actor.full_name or obj.actor.email
        return res

    model_config = {"from_attributes": True}
"""
Auth and workspace Pydantic schemas (request/response).
"""
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
    full_name: str | None
    avatar_url: str | None
    status: str
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None
    status: str
    role: str  # the current user's role in this workspace

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserProfile
    active_workspace: WorkspaceSummary


# ── Dev login request (local only) ───────────────────────────────────

class DevLoginRequest(BaseModel):
    email: str
    full_name: str | None = None


# ── Workspace schemas ────────────────────────────────────────────────

class WorkspaceCreateRequest(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    joined_at: datetime | None

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: str
    role: str = "MEMBER"


class UpdateMemberRoleRequest(BaseModel):
    role: str

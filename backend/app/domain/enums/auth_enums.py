"""
Auth-related enums.
"""
from enum import StrEnum


class AuthProvider(StrEnum):
    GOOGLE = "GOOGLE"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETED = "DELETED"


class WorkspaceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    ACCOUNTANT = "ACCOUNTANT"
    VIEWER = "VIEWER"


class WorkspaceMemberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    REMOVED = "REMOVED"

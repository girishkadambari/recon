"""
Auth-related enums.
"""
from enum import Enum


class AuthProvider(str, Enum):
    GOOGLE = "GOOGLE"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETED = "DELETED"


class WorkspaceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class WorkspaceRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    ACCOUNTANT = "ACCOUNTANT"
    VIEWER = "VIEWER"


class WorkspaceMemberStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    REMOVED = "REMOVED"

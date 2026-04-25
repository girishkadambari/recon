"""
Role-based access guard utilities.
For MVP, implements a simple role check utility.
"""
from app.core.errors import ForbiddenError


# Role hierarchy (higher index = more permissions)
ROLE_HIERARCHY = {
    "VIEWER": 0,
    "ACCOUNTANT": 1,
    "MEMBER": 2,
    "ADMIN": 3,
    "OWNER": 4,
}

# Action → minimum role required
ACTION_PERMISSIONS: dict[str, str] = {
    "upload_files": "ACCOUNTANT",
    "normalize_files": "ACCOUNTANT",
    "run_reconciliation": "ACCOUNTANT",
    "approve_matches": "ACCOUNTANT",
    "resolve_exceptions": "ACCOUNTANT",
    "export_reports": "VIEWER",
    "manage_members": "ADMIN",
}


def require_role(current_role: str, required_role: str) -> None:
    """
    Raises ForbiddenError if current_role is below required_role.
    """
    current_level = ROLE_HIERARCHY.get(current_role, -1)
    required_level = ROLE_HIERARCHY.get(required_role, 999)

    if current_level < required_level:
        raise ForbiddenError(
            f"Action requires '{required_role}' role or higher. "
            f"Your current role is '{current_role}'."
        )


def can_perform(current_role: str, action: str) -> bool:
    """Returns True if current_role can perform action."""
    required = ACTION_PERMISSIONS.get(action)
    if required is None:
        return False
    current_level = ROLE_HIERARCHY.get(current_role, -1)
    required_level = ROLE_HIERARCHY.get(required, 999)
    return current_level >= required_level

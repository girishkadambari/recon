"""
Core error types and error response structure.
All business errors should extend ReconError.
"""
from typing import Any


class ReconError(Exception):
    """Base class for all application-level errors."""

    status_code: int = 400
    code: str = "RECON_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code or self.__class__.code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(ReconError):
    status_code = 404
    code = "NOT_FOUND"


class UnauthorizedError(ReconError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(ReconError):
    status_code = 403
    code = "FORBIDDEN"


class ValidationError(ReconError):
    status_code = 422
    code = "VALIDATION_ERROR"


class ConflictError(ReconError):
    status_code = 409
    code = "CONFLICT"


class FileParseError(ReconError):
    status_code = 422
    code = "FILE_PARSE_FAILED"


class FileTooLargeError(ReconError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class UnsupportedFileTypeError(ReconError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"


class WorkspaceNotFoundError(NotFoundError):
    code = "WORKSPACE_NOT_FOUND"


class WorkspaceAccessDeniedError(ForbiddenError):
    code = "WORKSPACE_ACCESS_DENIED"


class ReconciliationError(ReconError):
    status_code = 400
    code = "RECONCILIATION_ERROR"


class AIServiceError(ReconError):
    status_code = 502
    code = "AI_SERVICE_ERROR"


class StorageError(ReconError):
    status_code = 500
    code = "STORAGE_ERROR"


class ExportError(ReconError):
    status_code = 500
    code = "EXPORT_ERROR"

"""
Export job enums.
"""
from enum import StrEnum


class ExportStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ExportFormat(StrEnum):
    XLSX = "XLSX"
    CSV = "CSV"   # future


class ExportScope(StrEnum):
    FULL = "FULL"            # matches + exceptions + summary
    MATCHES_ONLY = "MATCHES_ONLY"
    EXCEPTIONS_ONLY = "EXCEPTIONS_ONLY"

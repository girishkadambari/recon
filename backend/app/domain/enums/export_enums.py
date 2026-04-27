"""
Export job enums.
"""
from enum import Enum


class ExportStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ExportFormat(str, Enum):
    XLSX = "XLSX"
    CSV = "CSV"   # future


class ExportScope(str, Enum):
    FULL = "FULL"            # matches + exceptions + summary
    MATCHES_ONLY = "MATCHES_ONLY"
    EXCEPTIONS_ONLY = "EXCEPTIONS_ONLY"

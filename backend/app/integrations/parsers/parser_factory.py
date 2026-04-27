"""
Parser factory — select the right parser based on file extension / MIME type.
"""
from typing import Optional
from app.integrations.parsers.base_parser import BaseParser
from app.core.errors import UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
SUPPORTED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # commonly sent by browsers for CSV
}


def get_parser(file_name: str, mime_type: Optional[str] = None) -> BaseParser:
    """
    Return the appropriate parser based on file name extension.
    Raises UnsupportedFileTypeError for unknown types.
    """
    from app.integrations.parsers.csv_parser import CSVParser
    from app.integrations.parsers.xlsx_parser import XLSXParser

    ext = _extract_extension(file_name)
    if ext in (".xlsx", ".xls"):
        return XLSXParser()
    if ext == ".csv":
        return CSVParser()

    # Fall back to MIME type check
    if mime_type:
        mt = mime_type.lower().split(";")[0].strip()
        if "spreadsheet" in mt or "excel" in mt or ".xlsx" in mt:
            return XLSXParser()
        if "csv" in mt or "text" in mt or "octet" in mt:
            return CSVParser()

    raise UnsupportedFileTypeError(
        f"Unsupported file type '{file_name}'. Allowed: CSV, XLSX, XLS."
    )


def _extract_extension(file_name: str) -> str:
    """Extract lowercase file extension including the dot."""
    import os
    _, ext = os.path.splitext(file_name)
    return ext.lower()


def is_supported(file_name: str, mime_type: Optional[str] = None) -> bool:
    try:
        get_parser(file_name, mime_type)
        return True
    except UnsupportedFileTypeError:
        return False
"""
Date utilities — all dates must be timezone-aware.
"""
from datetime import datetime, timezone, date
from typing import Any


UTC = timezone.utc


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(tz=UTC)


def parse_date(value: Any, field_name: str = "date") -> datetime | None:
    """
    Parse a date/datetime value to a timezone-aware UTC datetime.
    Accepts: datetime, date, str (ISO 8601 or common formats).
    Returns None for empty/null values.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        # Try common date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%d %b %Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(stripped, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.astimezone(UTC)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse '{value}' as a date for field '{field_name}'")
    raise ValueError(f"Unsupported type {type(value).__name__} for field '{field_name}'")


def parse_date_or_none(value: Any, field_name: str = "date") -> datetime | None:
    """Returns None for empty/null values without raising."""
    try:
        return parse_date(value, field_name)
    except ValueError:
        return None


def is_within_date_window(
    base_date: datetime,
    candidate_date: datetime,
    window_days: int = 5,
) -> bool:
    """
    Returns True if candidate_date is within ±window_days of base_date.
    Used for settlement-to-bank date matching.
    """
    from datetime import timedelta

    delta = abs((base_date.date() - candidate_date.date()).days)
    return delta <= window_days

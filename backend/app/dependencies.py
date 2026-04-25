"""
Common FastAPI dependencies:
- get_db: database session
- get_current_user_context: JWT validation
"""
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database import get_db as _get_db
from app.auth.current_user import get_current_user_context, CurrentUserContext  # noqa: F401


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()

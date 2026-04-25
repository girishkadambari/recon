"""
Database setup — SQLAlchemy engine, session factory, and get_db dependency.
"""
from collections.abc import Generator

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # verify connection health before each use
    pool_size=10,
    max_overflow=20,
    echo=settings.APP_DEBUG,  # log SQL only in debug mode
)

# ── Session factory ──────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Returns True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connection check failed", error=str(exc))
        return False

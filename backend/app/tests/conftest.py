"""
conftest.py — shared test fixtures.

Integration tests use real Postgres (required for JSONB, UUID types).
The test database is the same Postgres instance, with tables created fresh per session.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.domain.models.base import Base
# Import all models so create_all picks them up
import app.domain.models.user  # noqa: F401
import app.domain.models.workspace  # noqa: F401
import app.domain.models.workspace_member  # noqa: F401
import app.domain.models.user_session  # noqa: F401
import app.domain.models.audit_event  # noqa: F401
import app.domain.models.uploaded_file  # noqa: F401
import app.domain.models.source_record  # noqa: F401
import app.domain.models.column_mapping  # noqa: F401
import app.domain.models.canonical_records  # noqa: F401
import app.domain.models.reconciliation_run  # noqa: F401
import app.domain.models.reconciliation_models  # noqa: F401
import app.domain.models.export_job  # noqa: F401

from app.main import app
from app.database import get_db

# Use a separate test database to avoid polluting the dev DB
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://recon:recon@localhost:5432/recon_worker_test",
)


@pytest.fixture(scope="session")
def test_engine():
    # Create the test database if it doesn't exist
    admin_url = "postgresql+psycopg://recon:recon@localhost:5432/recon_worker"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname='recon_worker_test'")
        ).fetchone()
        if not exists:
            conn.execute(text("CREATE DATABASE recon_worker_test"))
    admin_engine.dispose()

    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db(test_engine) -> Session:
    """
    Each test gets its own session wrapped in a transaction.
    Even if services call session.commit() internally, 
    the outer transaction is rolled back, ensuring strictly isolated tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    
    # We use join_transaction=True or equivalent to keep session within our test transaction
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    """FastAPI test client with the test DB injected."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def dev_token(client: TestClient) -> str:
    """Issues a real JWT via dev-login for testing protected endpoints."""
    resp = client.post(
        "/api/auth/dev-login",
        json={"email": "test@example.com", "full_name": "Test User"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.fixture()
def auth_headers(dev_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {dev_token}"}

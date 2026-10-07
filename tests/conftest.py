"""
conftest.py - Shared pytest fixtures for all test modules.

Key decisions:
    - Each test gets its OWN temporary SQLite database (isolated, repeatable)
    - Generated PDFs go to a temporary directory (no repo pollution)
    - A fresh FastAPI TestClient is created per test session
    - Environment variables are overridden to point at the temp dirs
"""

import os
import tempfile
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base, get_db
from app.main import app


# ──────────────────────────────────────────────────────────────────────────────
# Database fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session():
    """
    Provide an isolated in-memory SQLite database session for each test.

    Each test function gets a fresh, empty database.  This guarantees
    test isolation even when tests are run in parallel.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ──────────────────────────────────────────────────────────────────────────────
# TestClient fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def client(tmp_path):
    """
    Provide a FastAPI TestClient wired to an isolated test database
    and a temporary certificates directory.

    The get_db dependency is overridden so every request uses the test DB.
    The CERTIFICATES_DIR env var is overridden to use tmp_path.

    Note:
        TestClient runs background tasks synchronously, which means
        certificate generation happens before the assertion code.
        This is intentional for testing purposes.
    """
    # Use a temporary SQLite file (not in-memory) so the background task
    # (which creates its own SessionLocal) hits the same file.
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Override the get_db dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Override environment variables for DB and file storage
    certs_dir = tmp_path / "generated_certificates"
    certs_dir.mkdir()

    # Patch the module-level variables so background tasks use test paths
    import app.database as db_module
    import app.services.certificate_generator as gen_module
    import app.services.job_processor as proc_module
    from pathlib import Path

    original_engine = db_module.engine
    original_session_local = db_module.SessionLocal
    original_certs_dir = gen_module.CERTIFICATES_DIR

    db_module.engine = engine
    db_module.SessionLocal = TestingSessionLocal
    gen_module.CERTIFICATES_DIR = Path(certs_dir)

    with TestClient(app) as test_client:
        yield test_client

    # Restore originals after test
    app.dependency_overrides.clear()
    db_module.engine = original_engine
    db_module.SessionLocal = original_session_local
    gen_module.CERTIFICATES_DIR = original_certs_dir


# ──────────────────────────────────────────────────────────────────────────────
# Sample data helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_job_payload(
    *,
    event_name: str = "Test Workshop 2026",
    organization_name: str = "Test Organization",
    event_date: str = "2026-10-07",
    recipients: list | None = None,
) -> dict:
    """Build a valid job creation payload dict."""
    if recipients is None:
        recipients = [
            {"name": "Alice Smith", "email": "alice@example.com", "certificate_id": "CERT-001"},
            {"name": "Bob Jones",  "email": "bob@example.com",   "certificate_id": "CERT-002"},
        ]
    return {
        "event_name": event_name,
        "organization_name": organization_name,
        "event_date": event_date,
        "recipients": recipients,
    }

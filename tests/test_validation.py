"""
test_validation.py - Test 2: Input validation tests.

Tests:
    - Empty recipients list → 422
    - Missing recipient name → 422
    - Blank recipient name → 422
    - Invalid email → 422
    - Missing event_name → 422
    - Missing organization_name → 422
    - Invalid date format → 422
    - Duplicate certificate_id → 422
    - Missing certificate_id → 422
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_job_payload


def test_validation_empty_recipients(client: TestClient):
    """Empty recipients list should return 422."""
    payload = make_job_payload(recipients=[])
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_missing_name(client: TestClient):
    """Recipient without a name field should return 422."""
    payload = make_job_payload(
        recipients=[{"email": "test@example.com", "certificate_id": "CERT-001"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_blank_name(client: TestClient):
    """Recipient with a whitespace-only name should return 422."""
    payload = make_job_payload(
        recipients=[{"name": "   ", "email": "test@example.com", "certificate_id": "CERT-001"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_invalid_email(client: TestClient):
    """Invalid email format should return 422."""
    payload = make_job_payload(
        recipients=[{"name": "Alice", "email": "not-an-email", "certificate_id": "CERT-001"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_missing_event_name(client: TestClient):
    """Missing event_name field should return 422."""
    payload = {
        "organization_name": "Test Org",
        "event_date": "2026-10-07",
        "recipients": [{"name": "Alice", "email": "a@example.com", "certificate_id": "CERT-001"}],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_blank_event_name(client: TestClient):
    """Blank event_name should return 422."""
    payload = make_job_payload(event_name="   ")
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_missing_organization_name(client: TestClient):
    """Missing organization_name field should return 422."""
    payload = {
        "event_name": "Test Event",
        "event_date": "2026-10-07",
        "recipients": [{"name": "Alice", "email": "a@example.com", "certificate_id": "CERT-001"}],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_invalid_date(client: TestClient):
    """Invalid date string should return 422."""
    payload = make_job_payload(event_date="not-a-date")
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_duplicate_certificate_id(client: TestClient):
    """Duplicate certificate_id within the same request should return 422."""
    payload = make_job_payload(
        recipients=[
            {"name": "Alice", "email": "alice@example.com", "certificate_id": "CERT-SAME"},
            {"name": "Bob",   "email": "bob@example.com",   "certificate_id": "CERT-SAME"},
        ]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422
    # Confirm the error message mentions the duplicate
    body = response.json()
    error_str = str(body).lower()
    assert "duplicate" in error_str or "cert-same" in error_str.lower()


def test_validation_missing_certificate_id(client: TestClient):
    """Recipient without certificate_id should return 422."""
    payload = make_job_payload(
        recipients=[{"name": "Alice", "email": "alice@example.com"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_validation_error_response_is_json(client: TestClient):
    """Validation errors should return valid JSON with a 'detail' key."""
    payload = make_job_payload(recipients=[])
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body

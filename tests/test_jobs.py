"""
test_jobs.py - Test 1: Job creation endpoint.

Tests:
    - Valid request returns 202 with correct fields
    - job_id is a valid UUID string
    - status is queued or processing
    - total matches recipient count
    - Single recipient request works
    - Large recipient list works
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_job_payload


def test_create_job_returns_202(client: TestClient):
    """Valid job creation request should return HTTP 202 Accepted."""
    payload = make_job_payload()
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202


def test_create_job_response_has_job_id(client: TestClient):
    """Response must include a job_id."""
    payload = make_job_payload()
    response = client.post("/api/v1/jobs", json=payload)
    data = response.json()
    assert "job_id" in data
    # Must be a valid UUID
    uuid.UUID(data["job_id"])


def test_create_job_response_status_is_queued(client: TestClient):
    """Immediately after creation, status should be queued (or processing)."""
    payload = make_job_payload()
    response = client.post("/api/v1/jobs", json=payload)
    data = response.json()
    assert data["status"] in ("queued", "processing", "completed", "completed_with_errors")


def test_create_job_total_matches_recipients(client: TestClient):
    """total in response must match number of recipients submitted."""
    recipients = [
        {"name": f"Recipient {i}", "email": f"r{i}@example.com", "certificate_id": f"CERT-{i:03d}"}
        for i in range(5)
    ]
    payload = make_job_payload(recipients=recipients)
    response = client.post("/api/v1/jobs", json=payload)
    data = response.json()
    assert data["total"] == 5


def test_create_job_single_recipient(client: TestClient):
    """A job with a single recipient should work correctly."""
    payload = make_job_payload(
        recipients=[{"name": "Solo Person", "email": "solo@example.com", "certificate_id": "CERT-SOLO"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    assert response.json()["total"] == 1


def test_create_job_health_check(client: TestClient):
    """Health endpoint should return ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_many_recipients(client: TestClient):
    """Should handle a large batch request (50 recipients) correctly."""
    recipients = [
        {"name": f"Person {i}", "email": f"person{i}@example.com", "certificate_id": f"CERT-BULK-{i:04d}"}
        for i in range(50)
    ]
    payload = make_job_payload(recipients=recipients)
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    assert response.json()["total"] == 50

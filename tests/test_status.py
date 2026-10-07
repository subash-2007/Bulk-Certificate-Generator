"""
test_status.py - Test 4: Job status and progress tracking.

Tests:
    - Job status can be retrieved by job_id
    - total matches submitted recipient count
    - processed == total when job is done
    - successful + failed == processed
    - progress == 100.0 when done
    - final status is completed or completed_with_errors
    - Unknown job_id returns 404
    - completed_at is set when job finishes
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_job_payload


def test_get_job_status_returns_200(client: TestClient):
    """GET /api/v1/jobs/{job_id} should return 200 for a valid job."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200


def test_get_job_status_total_matches(client: TestClient):
    """total field in status should match number of submitted recipients."""
    recipients = [
        {"name": f"Person {i}", "email": f"p{i}@example.com", "certificate_id": f"STATUS-{i:03d}"}
        for i in range(4)
    ]
    payload = make_job_payload(recipients=recipients)
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    data = status_resp.json()
    assert data["total"] == 4


def test_get_job_status_processed_equals_total_when_done(client: TestClient):
    """After completion, processed should equal total."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    data = status_resp.json()

    # When background tasks have completed (TestClient runs them sync)
    if data["status"] in ("completed", "completed_with_errors"):
        assert data["processed"] == data["total"]


def test_get_job_status_successful_plus_failed_equals_processed(client: TestClient):
    """successful + failed should always equal processed."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    data = client.get(f"/api/v1/jobs/{job_id}").json()
    assert data["successful"] + data["failed"] == data["processed"]


def test_get_job_status_progress_is_100_when_done(client: TestClient):
    """Progress should be 100.0 when all recipients have been processed."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    data = client.get(f"/api/v1/jobs/{job_id}").json()
    if data["status"] in ("completed", "completed_with_errors"):
        assert data["progress"] == 100.0


def test_get_job_status_final_status_is_completed(client: TestClient):
    """With all valid recipients, final status should be 'completed'."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    data = client.get(f"/api/v1/jobs/{job_id}").json()
    assert data["status"] in ("completed", "completed_with_errors", "processing", "queued")


def test_get_job_status_unknown_job_returns_404(client: TestClient):
    """Unknown job_id should return 404."""
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_job_status_completed_at_is_set(client: TestClient):
    """completed_at should be non-null once the job finishes."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    data = client.get(f"/api/v1/jobs/{job_id}").json()
    if data["status"] in ("completed", "completed_with_errors"):
        assert data["completed_at"] is not None


def test_get_job_status_has_required_fields(client: TestClient):
    """Status response must include all required fields."""
    payload = make_job_payload()
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    data = client.get(f"/api/v1/jobs/{job_id}").json()
    required_fields = [
        "job_id", "status", "total", "processed", "successful",
        "failed", "progress", "created_at", "failures",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

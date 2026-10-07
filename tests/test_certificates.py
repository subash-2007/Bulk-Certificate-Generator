"""
test_certificates.py - Tests 5 & 6: Failure isolation and certificate retrieval.

Test 5 — Individual failure isolation:
    - Monkeypatch generate_certificate_for_recipient to fail for one specific recipient
    - Verify: successful=2, failed=1, job status=completed_with_errors
    - Verify: failed recipient has error_message
    - Verify: successful recipients still have certificates
    - Verify: failure does NOT stop other recipients

Test 6 — Certificate retrieval:
    - GET /api/v1/certificates/{id} returns 200 with content-type application/pdf
    - Response body is non-empty
    - Nonexistent certificate returns 404
    - Certificate appears in job's certificate list
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tests.conftest import make_job_payload


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Failure isolation
# ──────────────────────────────────────────────────────────────────────────────

def test_one_failure_does_not_stop_others(client: TestClient):
    """
    Critical test: one recipient failure must not abort the remaining recipients.

    Scenario:
        Recipient 1 (CERT-F001) → SUCCESS
        Recipient 2 (CERT-F002) → FORCED FAILURE
        Recipient 3 (CERT-F003) → SUCCESS

    Expected:
        successful = 2
        failed = 1
        job status = completed_with_errors
    """
    payload = make_job_payload(
        recipients=[
            {"name": "Alice Pass",  "email": "alice@example.com",  "certificate_id": "CERT-F001"},
            {"name": "Bob Fail",    "email": "bob@example.com",    "certificate_id": "CERT-F002"},
            {"name": "Carol Pass",  "email": "carol@example.com",  "certificate_id": "CERT-F003"},
        ]
    )

    # Patch the certificate generator to fail for CERT-F002 only
    original_generate = None

    import app.services.certificate_generator as gen_module
    real_generate = gen_module.generate_certificate_for_recipient

    def mock_generate(*, db, recipient, event_name, organization_name, event_date):
        if recipient.certificate_id == "CERT-F002":
            raise RuntimeError("Simulated certificate generation failure")
        return real_generate(
            db=db,
            recipient=recipient,
            event_name=event_name,
            organization_name=organization_name,
            event_date=event_date,
        )

    with patch.object(gen_module, "generate_certificate_for_recipient", side_effect=mock_generate):
        response = client.post("/api/v1/jobs", json=payload)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Check job status
    status_data = client.get(f"/api/v1/jobs/{job_id}").json()

    assert status_data["successful"] == 2, f"Expected 2 successful, got {status_data['successful']}"
    assert status_data["failed"] == 1,     f"Expected 1 failed, got {status_data['failed']}"
    assert status_data["processed"] == 3,  f"Expected 3 processed, got {status_data['processed']}"
    assert status_data["status"] == "completed_with_errors", \
        f"Expected 'completed_with_errors', got '{status_data['status']}'"


def test_failed_recipient_has_error_message(client: TestClient):
    """The failed recipient must have an error_message in the failures list."""
    payload = make_job_payload(
        recipients=[
            {"name": "Alice Pass", "email": "alice@example.com", "certificate_id": "ERR-001"},
            {"name": "Bob Fail",   "email": "bob@example.com",   "certificate_id": "ERR-002"},
        ]
    )

    import app.services.certificate_generator as gen_module
    real_generate = gen_module.generate_certificate_for_recipient

    def mock_fail_cert_002(*, db, recipient, event_name, organization_name, event_date):
        if recipient.certificate_id == "ERR-002":
            raise ValueError("Test-induced failure for ERR-002")
        return real_generate(
            db=db, recipient=recipient, event_name=event_name,
            organization_name=organization_name, event_date=event_date,
        )

    with patch.object(gen_module, "generate_certificate_for_recipient", side_effect=mock_fail_cert_002):
        response = client.post("/api/v1/jobs", json=payload)

    job_id = response.json()["job_id"]
    status_data = client.get(f"/api/v1/jobs/{job_id}").json()

    assert len(status_data["failures"]) == 1
    failure = status_data["failures"][0]
    assert failure["certificate_id"] == "ERR-002"
    assert len(failure["error"]) > 0


def test_successful_recipients_have_certificates_when_one_fails(client: TestClient):
    """Successful recipients must still have downloadable certificates."""
    payload = make_job_payload(
        recipients=[
            {"name": "Success One", "email": "s1@example.com", "certificate_id": "MIX-001"},
            {"name": "Fail One",    "email": "f1@example.com", "certificate_id": "MIX-002"},
            {"name": "Success Two", "email": "s2@example.com", "certificate_id": "MIX-003"},
        ]
    )

    import app.services.certificate_generator as gen_module
    real_generate = gen_module.generate_certificate_for_recipient

    def mock_fail_mix_002(*, db, recipient, event_name, organization_name, event_date):
        if recipient.certificate_id == "MIX-002":
            raise RuntimeError("Simulated failure")
        return real_generate(
            db=db, recipient=recipient, event_name=event_name,
            organization_name=organization_name, event_date=event_date,
        )

    with patch.object(gen_module, "generate_certificate_for_recipient", side_effect=mock_fail_mix_002):
        response = client.post("/api/v1/jobs", json=payload)

    job_id = response.json()["job_id"]
    certs_data = client.get(f"/api/v1/jobs/{job_id}/certificates").json()
    cert_ids = {c["certificate_id"] for c in certs_data["certificates"]}

    # MIX-001 and MIX-003 must have certificates
    assert "MIX-001" in cert_ids
    assert "MIX-003" in cert_ids
    # MIX-002 must NOT have a certificate
    assert "MIX-002" not in cert_ids


def test_all_recipients_failing_results_in_completed_with_errors(client: TestClient):
    """When every recipient fails, status should be completed_with_errors."""
    payload = make_job_payload(
        recipients=[
            {"name": "Fail A", "email": "fa@example.com", "certificate_id": "ALL-FAIL-001"},
            {"name": "Fail B", "email": "fb@example.com", "certificate_id": "ALL-FAIL-002"},
        ]
    )

    import app.services.certificate_generator as gen_module

    def always_fail(*, db, recipient, event_name, organization_name, event_date):
        raise RuntimeError("Always fails")

    with patch.object(gen_module, "generate_certificate_for_recipient", side_effect=always_fail):
        response = client.post("/api/v1/jobs", json=payload)

    job_id = response.json()["job_id"]
    data = client.get(f"/api/v1/jobs/{job_id}").json()

    assert data["failed"] == 2
    assert data["successful"] == 0
    assert data["status"] == "completed_with_errors"


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Certificate retrieval
# ──────────────────────────────────────────────────────────────────────────────

def test_certificate_download_returns_200(client: TestClient):
    """GET /api/v1/certificates/{id} should return 200 for a valid certificate."""
    payload = make_job_payload(
        recipients=[{"name": "Download Test", "email": "dl@example.com", "certificate_id": "DL-001"}]
    )
    client.post("/api/v1/jobs", json=payload)

    response = client.get("/api/v1/certificates/DL-001")
    assert response.status_code == 200


def test_certificate_download_content_type_is_pdf(client: TestClient):
    """Certificate download response must have content-type: application/pdf."""
    payload = make_job_payload(
        recipients=[{"name": "PDF Type Test", "email": "pdf@example.com", "certificate_id": "DL-002"}]
    )
    client.post("/api/v1/jobs", json=payload)

    response = client.get("/api/v1/certificates/DL-002")
    assert "application/pdf" in response.headers.get("content-type", "")


def test_certificate_download_body_is_non_empty(client: TestClient):
    """Downloaded certificate must have a non-empty body."""
    payload = make_job_payload(
        recipients=[{"name": "Body Test", "email": "body@example.com", "certificate_id": "DL-003"}]
    )
    client.post("/api/v1/jobs", json=payload)

    response = client.get("/api/v1/certificates/DL-003")
    assert len(response.content) > 100  # A real PDF is at least a few hundred bytes


def test_nonexistent_certificate_returns_404(client: TestClient):
    """Requesting a non-existent certificate ID should return 404."""
    response = client.get("/api/v1/certificates/DOES-NOT-EXIST-CERT")
    assert response.status_code == 404


def test_certificate_appears_in_job_list(client: TestClient):
    """A generated certificate must appear in the job's certificate list."""
    payload = make_job_payload(
        recipients=[{"name": "List Test", "email": "list@example.com", "certificate_id": "DL-004"}]
    )
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    certs = client.get(f"/api/v1/jobs/{job_id}/certificates").json()
    assert certs["total_certificates"] == 1
    assert certs["certificates"][0]["certificate_id"] == "DL-004"
    assert "/api/v1/certificates/DL-004" in certs["certificates"][0]["download_url"]


def test_unknown_job_certificates_returns_404(client: TestClient):
    """Certificate list for an unknown job should return 404."""
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/certificates")
    assert response.status_code == 404

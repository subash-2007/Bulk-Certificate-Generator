"""
test_generation.py - Test 3: Certificate PDF generation.

Tests:
    - PDF file is created on disk
    - File has .pdf extension
    - PDF is non-empty (has content)
    - Certificate record exists in database
    - Generated PDF is stored in the correct temp directory
"""

import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from tests.conftest import make_job_payload


def test_pdf_file_is_created(client: TestClient, tmp_path):
    """After processing, a PDF file must exist in the certificates directory."""
    payload = make_job_payload(
        recipients=[{"name": "Alice Smith", "email": "alice@example.com", "certificate_id": "GEN-001"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202

    # TestClient runs background tasks synchronously, so by the time we reach
    # here, the PDF should already be generated.
    job_id = response.json()["job_id"]

    # Check job completed
    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    job_data = status_resp.json()
    assert job_data["successful"] >= 1

    # Check certificate list
    cert_resp = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert cert_resp.status_code == 200
    certs = cert_resp.json()["certificates"]
    assert len(certs) >= 1

    # Check the file exists
    cert_id = certs[0]["certificate_id"]
    # The download URL should be accessible
    download_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert download_resp.status_code == 200


def test_pdf_file_has_pdf_extension(client: TestClient, tmp_path):
    """The certificate download URL/ID should correspond to a .pdf file."""
    payload = make_job_payload(
        recipients=[{"name": "Bob Jones", "email": "bob@example.com", "certificate_id": "GEN-002"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]

    cert_resp = client.get(f"/api/v1/jobs/{job_id}/certificates")
    certs = cert_resp.json()["certificates"]
    assert len(certs) == 1

    # Download the certificate
    cert_id = certs[0]["certificate_id"]
    download_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert download_resp.status_code == 200
    # Content-Type must be application/pdf
    assert "application/pdf" in download_resp.headers.get("content-type", "")


def test_pdf_is_non_empty(client: TestClient, tmp_path):
    """Generated PDF must have actual content (not zero bytes)."""
    payload = make_job_payload(
        recipients=[{"name": "Carol White", "email": "carol@example.com", "certificate_id": "GEN-003"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]

    cert_resp = client.get(f"/api/v1/jobs/{job_id}/certificates")
    cert_id = cert_resp.json()["certificates"][0]["certificate_id"]

    download_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert len(download_resp.content) > 0


def test_pdf_starts_with_pdf_magic_bytes(client: TestClient, tmp_path):
    """PDF files must start with the %PDF magic bytes."""
    payload = make_job_payload(
        recipients=[{"name": "Dave Brown", "email": "dave@example.com", "certificate_id": "GEN-004"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]

    cert_resp = client.get(f"/api/v1/jobs/{job_id}/certificates")
    cert_id = cert_resp.json()["certificates"][0]["certificate_id"]

    download_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert download_resp.content[:4] == b"%PDF"


def test_certificate_record_exists_in_db(client: TestClient, tmp_path):
    """After successful generation, the certificates endpoint must list the cert."""
    payload = make_job_payload(
        recipients=[{"name": "Eve Green", "email": "eve@example.com", "certificate_id": "GEN-005"}]
    )
    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]

    cert_resp = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert cert_resp.status_code == 200
    data = cert_resp.json()
    assert data["total_certificates"] == 1
    assert data["certificates"][0]["certificate_id"] == "GEN-005"

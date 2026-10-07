"""
schemas.py - Pydantic request/response models.

These are separate from the SQLAlchemy ORM models.
Pydantic handles input validation; SQLAlchemy handles persistence.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ──────────────────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────────────────

class RecipientRequest(BaseModel):
    """A single recipient within a job creation request."""

    name: str
    email: EmailStr
    certificate_id: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Recipient name must not be blank")
        return v.strip()

    @field_validator("certificate_id")
    @classmethod
    def certificate_id_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("certificate_id must not be blank")
        return v.strip()


class JobCreateRequest(BaseModel):
    """
    Payload for POST /api/v1/jobs.

    All recipients in one request = one job.
    """

    event_name: str
    organization_name: str
    event_date: date  # Pydantic validates ISO-8601 date strings automatically
    recipients: list[RecipientRequest]

    @field_validator("event_name")
    @classmethod
    def event_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("event_name must not be blank")
        return v.strip()

    @field_validator("organization_name")
    @classmethod
    def org_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("organization_name must not be blank")
        return v.strip()

    @field_validator("recipients")
    @classmethod
    def recipients_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("recipients list must not be empty")
        return v

    @model_validator(mode="after")
    def certificate_ids_must_be_unique(self) -> "JobCreateRequest":
        """certificate_id values must be unique within a single request."""
        seen: set[str] = set()
        for recipient in self.recipients:
            cid = recipient.certificate_id
            if cid in seen:
                raise ValueError(
                    f"Duplicate certificate_id '{cid}' found in recipients. "
                    "Each certificate_id must be unique within the request."
                )
            seen.add(cid)
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────────────────────────────────────

class JobCreateResponse(BaseModel):
    """Returned immediately after POST /api/v1/jobs (HTTP 202)."""
    job_id: str
    status: str
    total: int


class FailureDetail(BaseModel):
    """Details about a single failed recipient in a job status response."""
    recipient_id: str
    name: str
    email: str
    certificate_id: str
    error: str


class JobStatusResponse(BaseModel):
    """Full job status returned by GET /api/v1/jobs/{job_id}."""
    job_id: str
    status: str
    event_name: str
    organization_name: str
    event_date: str
    total: int
    processed: int
    successful: int
    failed: int
    progress: float
    created_at: datetime
    completed_at: Optional[datetime]
    failures: list[FailureDetail]

    model_config = {"from_attributes": True}


class CertificateInfo(BaseModel):
    """One certificate entry in the job certificates list."""
    certificate_id: str
    recipient_name: str
    recipient_email: str
    download_url: str

    model_config = {"from_attributes": True}


class JobCertificatesResponse(BaseModel):
    """Response for GET /api/v1/jobs/{job_id}/certificates."""
    job_id: str
    total_certificates: int
    certificates: list[CertificateInfo]

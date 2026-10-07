"""
api/jobs.py - Router for job-related endpoints.

Endpoints:
    POST /api/v1/jobs               Create a bulk certificate generation job
    GET  /api/v1/jobs/{job_id}      Get job status and progress
    GET  /api/v1/jobs/{job_id}/certificates   List downloadable certificates
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    GenerationJob, Recipient, Certificate,
    JobStatus, RecipientStatus,
)
from app.schemas import (
    JobCreateRequest, JobCreateResponse,
    JobStatusResponse, FailureDetail,
    JobCertificatesResponse, CertificateInfo,
)
from app.services.job_processor import process_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/v1/jobs
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreateResponse,
    summary="Create a bulk certificate generation job",
    description=(
        "Accepts a list of recipients and creates a background processing job. "
        "Returns HTTP 202 immediately with a job_id. "
        "Use GET /api/v1/jobs/{job_id} to poll progress."
    ),
)
def create_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    """
    Create a new generation job.

    Flow:
        1. Validate request (done automatically by Pydantic)
        2. Create GenerationJob record
        3. Create one Recipient record per person
        4. Schedule background processing
        5. Return 202 with job_id immediately
    """
    job_id = str(uuid.uuid4())

    # ── Create the Job record ─────────────────────────────────────────────────
    job = GenerationJob(
        id=job_id,
        event_name=payload.event_name,
        organization_name=payload.organization_name,
        event_date=str(payload.event_date),   # Store as ISO string
        status=JobStatus.QUEUED,
        total=len(payload.recipients),
    )
    db.add(job)

    # ── Create Recipient records ──────────────────────────────────────────────
    for r in payload.recipients:
        recipient = Recipient(
            id=str(uuid.uuid4()),
            job_id=job_id,
            name=r.name,
            email=str(r.email),
            certificate_id=r.certificate_id,
            status=RecipientStatus.PENDING,
        )
        db.add(recipient)

    db.commit()

    logger.info("Job '%s' created with %d recipients.", job_id, job.total)

    # ── Schedule background processing ───────────────────────────────────────
    # BackgroundTasks runs process_job AFTER the HTTP response is sent.
    # The processor creates its own DB session (see job_processor.py).
    background_tasks.add_task(process_job, job_id)

    return JobCreateResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        total=job.total,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/v1/jobs/{job_id}
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
    description="Returns current status, progress counters, and details of any failures.",
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Return the current status and progress of a generation job."""
    job: GenerationJob | None = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    # Collect failed recipients for the failures list
    failed_recipients = (
        db.query(Recipient)
        .filter(
            Recipient.job_id == job_id,
            Recipient.status == RecipientStatus.FAILED,
        )
        .all()
    )

    failures = [
        FailureDetail(
            recipient_id=r.id,
            name=r.name,
            email=r.email,
            certificate_id=r.certificate_id,
            error=r.error_message or "Unknown error",
        )
        for r in failed_recipients
    ]

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        event_name=job.event_name,
        organization_name=job.organization_name,
        event_date=job.event_date,
        total=job.total,
        processed=job.processed,
        successful=job.successful,
        failed=job.failed,
        progress=job.progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
        failures=failures,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/v1/jobs/{job_id}/certificates
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{job_id}/certificates",
    response_model=JobCertificatesResponse,
    summary="List downloadable certificates for a job",
    description="Returns only successfully generated certificates with download URLs.",
)
def list_job_certificates(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobCertificatesResponse:
    """List all successfully generated certificates for a job."""
    job: GenerationJob | None = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    certificates = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .join(Recipient, Certificate.recipient_id == Recipient.id)
        .all()
    )

    cert_infos = [
        CertificateInfo(
            certificate_id=cert.id,
            recipient_name=cert.recipient.name,
            recipient_email=cert.recipient.email,
            download_url=f"/api/v1/certificates/{cert.id}",
        )
        for cert in certificates
    ]

    return JobCertificatesResponse(
        job_id=job_id,
        total_certificates=len(cert_infos),
        certificates=cert_infos,
    )

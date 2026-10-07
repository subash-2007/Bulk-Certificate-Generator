"""
job_processor.py - Background task that processes all recipients in a job.

Responsibilities:
    - Transition job status from QUEUED → PROCESSING
    - Iterate over recipients one by one
    - Call certificate_generator for each
    - Mark each recipient SUCCESS or FAILED independently
    - Update aggregate job counters after each recipient
    - Transition job to COMPLETED or COMPLETED_WITH_ERRORS when done
    - Handle unexpected errors and mark job FAILED

IMPORTANT - Session Management:
    FastAPI background tasks run AFTER the HTTP response has been sent.
    The SQLAlchemy session from the original HTTP request is already closed
    by that point.  We therefore create a FRESH session here using
    SessionLocal() rather than reusing the request's session.
    This is a deliberate design decision, not an oversight.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import app.database as db_module  # Import the module so patches to db_module.SessionLocal are respected
import app.services.certificate_generator as cert_gen  # Import module (not function) so test mocks work
from app.models import GenerationJob, Recipient, JobStatus, RecipientStatus

logger = logging.getLogger(__name__)


def process_job(job_id: str) -> None:
    """
    Entry point for the FastAPI BackgroundTask.

    Creates its own database session (see module docstring for why),
    processes every recipient, and finalises the job status.

    Args:
        job_id: UUID string of the GenerationJob to process.
    """
    # Fresh session — independent of the HTTP request session.
    # We call db_module.SessionLocal() at runtime (not import time) so that
    # test fixtures patching db_module.SessionLocal are correctly picked up.
    db: Session = db_module.SessionLocal()
    try:
        _run_job(db, job_id)
    except Exception as exc:
        # Catch completely unexpected errors (e.g. DB connection lost).
        # Attempt to mark the job as FAILED so clients don't wait forever.
        logger.exception("Unexpected error processing job '%s': %s", job_id, exc)
        _mark_job_failed(db, job_id, str(exc))
    finally:
        db.close()


def _run_job(db: Session, job_id: str) -> None:
    """Core processing logic for a single job."""
    job = db.get(GenerationJob, job_id)
    if not job:
        logger.error("Job '%s' not found in database — cannot process.", job_id)
        return

    logger.info("Starting job '%s' (%d recipients)", job_id, job.total)

    # ── Transition: QUEUED → PROCESSING ──────────────────────────────────────
    job.status = JobStatus.PROCESSING
    db.commit()

    # Fetch all pending recipients for this job
    recipients: list[Recipient] = (
        db.query(Recipient)
        .filter(Recipient.job_id == job_id, Recipient.status == RecipientStatus.PENDING)
        .all()
    )

    # ── Process each recipient independently ─────────────────────────────────
    for recipient in recipients:
        _process_single_recipient(db, job, recipient)

    # ── Finalise job status ───────────────────────────────────────────────────
    db.refresh(job)  # Pick up the latest counters
    job.completed_at = datetime.now(timezone.utc)

    if job.failed == 0:
        job.status = JobStatus.COMPLETED
    else:
        # Some succeeded, some failed — or all failed.
        # Either way: processing finished, so NOT the top-level FAILED status.
        job.status = JobStatus.COMPLETED_WITH_ERRORS

    db.commit()
    logger.info(
        "Job '%s' finished — status=%s successful=%d failed=%d",
        job_id, job.status, job.successful, job.failed,
    )


def _process_single_recipient(
    db: Session,
    job: GenerationJob,
    recipient: Recipient,
) -> None:
    """
    Generate a certificate for one recipient.

    ── Failure Isolation ──────────────────────────────────────────────────────
    If certificate generation raises ANY exception, we catch it here,
    mark THIS recipient as FAILED, record the error message, and continue
    to the next recipient.  The job is NEVER aborted due to one failure.
    """
    now = datetime.now(timezone.utc)

    # Mark as processing
    recipient.status = RecipientStatus.PROCESSING
    db.commit()

    try:
        # Call via module reference so test mocks on cert_gen.generate_certificate_for_recipient
        # are correctly picked up at runtime (direct function import would bypass patches).
        cert_gen.generate_certificate_for_recipient(
            db=db,
            recipient=recipient,
            event_name=job.event_name,
            organization_name=job.organization_name,
            event_date=job.event_date,
        )

        # ── Success ───────────────────────────────────────────────────────────
        recipient.status = RecipientStatus.SUCCESS
        recipient.processed_at = datetime.now(timezone.utc)
        job.successful += 1

        logger.info(
            "Recipient '%s' (cert_id=%s) — SUCCESS",
            recipient.name, recipient.certificate_id,
        )

    except Exception as exc:
        # ── Failure (isolated) ────────────────────────────────────────────────
        error_msg = str(exc) or "Unknown error during certificate generation"
        recipient.status = RecipientStatus.FAILED
        recipient.error_message = error_msg
        recipient.processed_at = datetime.now(timezone.utc)
        job.failed += 1

        logger.warning(
            "Recipient '%s' (cert_id=%s) — FAILED: %s",
            recipient.name, recipient.certificate_id, error_msg,
        )

    finally:
        # Always increment processed count and persist, regardless of outcome.
        job.processed += 1
        db.commit()


def _mark_job_failed(db: Session, job_id: str, reason: str) -> None:
    """
    Mark the job as top-level FAILED due to a system-level error.

    This is only reached when something catastrophic happens outside
    normal recipient processing (e.g. DB unavailable, OOM error, etc.).
    """
    try:
        job = db.get(GenerationJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception("Failed to mark job '%s' as FAILED in database.", job_id)

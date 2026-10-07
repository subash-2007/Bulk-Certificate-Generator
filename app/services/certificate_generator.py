"""
certificate_generator.py - Service responsible for generating a single PDF
certificate and recording the result in the database.

Responsibilities:
    - Format certificate data
    - Call the template to render the PDF
    - Persist a Certificate row on success
    - Raise exceptions on failure (handled by job_processor.py)
"""

import os
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Recipient, Certificate, RecipientStatus
from app.templates.certificate_template import build_certificate_pdf

logger = logging.getLogger(__name__)

# Directory where generated PDFs are stored.
# Configurable via environment variable; defaults to "generated_certificates"
# relative to the working directory where the server is started.
CERTIFICATES_DIR: Path = Path(
    os.getenv("CERTIFICATES_DIR", "generated_certificates")
)


def _format_event_date(date_str: str) -> str:
    """
    Convert an ISO date string (YYYY-MM-DD) to a human-readable format.

    Example:
        "2026-10-07" → "07 October 2026"
    """
    try:
        d = date.fromisoformat(date_str)
        return d.strftime("%d %B %Y")
    except ValueError:
        return date_str  # Fall back to raw string if parsing fails


def generate_certificate_for_recipient(
    *,
    db: Session,
    recipient: Recipient,
    event_name: str,
    organization_name: str,
    event_date: str,
) -> Certificate:
    """
    Generate a PDF certificate for one recipient and save the result to the DB.

    Args:
        db:                Active SQLAlchemy session.
        recipient:         The Recipient ORM object.
        event_name:        Event/course name for the certificate body.
        organization_name: Issuing organisation.
        event_date:        ISO date string (YYYY-MM-DD); converted before rendering.

    Returns:
        The newly created Certificate ORM object.

    Raises:
        Exception: Any error during PDF creation.  The caller (job_processor)
                   is responsible for catching this and marking the recipient FAILED.
    """
    certificate_id = recipient.certificate_id
    output_filename = f"{certificate_id}.pdf"
    output_path = CERTIFICATES_DIR / output_filename

    human_date = _format_event_date(event_date)

    logger.info(
        "Generating certificate for recipient='%s' cert_id='%s'",
        recipient.name, certificate_id,
    )

    # ── Render the PDF ───────────────────────────────────────────────────────
    # This call does the actual heavy lifting; any exception propagates up.
    build_certificate_pdf(
        output_path=output_path,
        recipient_name=recipient.name,
        event_name=event_name,
        organization_name=organization_name,
        event_date=human_date,
        certificate_id=certificate_id,
    )

    # ── Persist the Certificate record ───────────────────────────────────────
    certificate = Certificate(
        id=certificate_id,
        recipient_id=recipient.id,
        job_id=recipient.job_id,
        file_path=str(output_path),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    logger.info("Certificate saved: %s", output_path)
    return certificate

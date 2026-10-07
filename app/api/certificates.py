"""
api/certificates.py - Router for certificate retrieval.

Endpoints:
    GET /api/v1/certificates/{certificate_id}   Download a PDF certificate
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    summary="Download a generated certificate PDF",
    description=(
        "Returns the PDF file for a successfully generated certificate. "
        "Returns 404 if the certificate does not exist or the file is missing."
    ),
    response_class=FileResponse,
)
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Retrieve and stream a certificate PDF file.

    Security note:
        - We look up the file path from the database using a trusted certificate_id.
        - We never accept arbitrary filesystem paths from the user.
        - This prevents path traversal attacks.
    """
    # ── Look up the certificate in the database ───────────────────────────────
    certificate: Certificate | None = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found.",
        )

    # ── Verify the PDF file still exists on disk ──────────────────────────────
    file_path = Path(certificate.file_path)
    if not file_path.exists():
        logger.error(
            "Certificate record exists (id=%s) but PDF is missing at '%s'",
            certificate_id, file_path,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Certificate '{certificate_id}' was generated but the file "
                "is no longer available."
            ),
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=f"certificate_{certificate_id}.pdf",
    )

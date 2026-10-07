"""
models.py - SQLAlchemy ORM models for the Bulk Certificate Generator.

Tables:
    generation_jobs  - one record per bulk request
    recipients       - one record per person within a job
    certificates     - one record per successfully generated PDF
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────────────────────────
# Job status constants
# ──────────────────────────────────────────────────────────────────────────────

class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class RecipientStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


# ──────────────────────────────────────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────────────────────────────────────

class GenerationJob(Base):
    """
    Represents a single bulk certificate generation request.

    One job → many recipients → many certificates (for successful ones).
    """
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[str] = mapped_column(String(20), nullable=False)  # ISO date string

    # Job lifecycle status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=JobStatus.QUEUED)

    # Aggregate counters — updated as background processing progresses
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    recipients: Mapped[list["Recipient"]] = relationship(
        "Recipient", back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def progress(self) -> float:
        """Percentage of recipients processed (0–100)."""
        if self.total == 0:
            return 0.0
        return round((self.processed / self.total) * 100, 1)


class Recipient(Base):
    """
    One person within a generation job.

    Each recipient gets exactly one certificate on SUCCESS.
    On FAILED, the error_message field records what went wrong.
    """
    __tablename__ = "recipients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_jobs.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # certificate_id supplied by the caller (e.g. "CERT-001") — unique within a job
    certificate_id: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecipientStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    job: Mapped["GenerationJob"] = relationship("GenerationJob", back_populates="recipients")
    certificate: Mapped["Certificate | None"] = relationship(
        "Certificate", back_populates="recipient", uselist=False, cascade="all, delete-orphan"
    )


class Certificate(Base):
    """
    Represents a successfully generated PDF certificate.

    Only exists for recipients whose status is SUCCESS.
    The actual PDF is stored on disk; only the path is stored here.
    """
    __tablename__ = "certificates"

    # We use the caller-supplied certificate_id as the primary key so
    # the download URL is stable and human-readable.
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    recipient_id: Mapped[str] = mapped_column(String(36), ForeignKey("recipients.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_jobs.id"), nullable=False)

    # Relative path from the project root — e.g. "generated_certificates/CERT-001.pdf"
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)

    # Relationships
    recipient: Mapped["Recipient"] = relationship("Recipient", back_populates="certificate")

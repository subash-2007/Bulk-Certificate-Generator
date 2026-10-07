"""
main.py - FastAPI application entry point.

Responsibilities:
    - Create the FastAPI app instance
    - Register API routers
    - Initialise database tables on startup
    - Expose the /health endpoint
    - Configure logging

Keep this file small. Business logic belongs in services/ and api/.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base  # noqa: F401 — imports all ORM models via Base
from app.api import jobs, certificates

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Lifespan
# ────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown logic using the modern lifespan pattern.

    SQLAlchemy's create_all() is idempotent — it only creates tables that
    don’t already exist.  This avoids a separate migration step for
    assignment-scale usage.  In production, use Alembic migrations.
    """
    logger.info("Initialising database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready.")
    yield  # Application runs here
    # (Add shutdown cleanup here if needed)


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Bulk Certificate Generator API",
    description=(
        "A backend API for bulk PDF certificate generation. "
        "Submit a list of recipients, track generation progress, "
        "and download individual certificates."
    ),
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    license_info={"name": "MIT"},
)

# ── CORS (open for development; restrict origins in production) ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────────────

app.include_router(jobs.router)
app.include_router(certificates.router)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Health check")
def health_check() -> dict:
    """Returns 200 OK when the service is running."""
    return {"status": "ok"}

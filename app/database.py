"""
database.py - SQLAlchemy engine and session configuration.

We use SQLite for simplicity. In production, swap DATABASE_URL
for a PostgreSQL connection string and install psycopg2.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Read from environment or fall back to a local SQLite file.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")

# connect_args is SQLite-specific: allows the same connection to be
# used across threads (needed by FastAPI's async background tasks).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # Set True to log all SQL statements during development
)

# Each call to SessionLocal() gives an independent database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    The session is always closed after the request, even on errors.

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

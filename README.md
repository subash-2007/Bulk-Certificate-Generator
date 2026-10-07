# Bulk Certificate Generator API

A backend API that accepts a bulk certificate generation request, generates PDFs for each recipient, tracks progress, and lets you download individual certificates.

---

## Features

- Accept a list of recipients in one request
- Validate all input with clear error messages
- Generate a PDF certificate per recipient in the background
- Track job progress (total, processed, successful, failed)
- Continue processing if one recipient fails
- Download individual certificates as PDF files
- Full test coverage

---

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite
- Pydantic v2
- ReportLab
- pytest

---

## Setup

```bash
git clone https://github.com/your-username/bulk-certificate-generator.git
cd bulk-certificate-generator

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Run

```bash
uvicorn app.main:app --reload
```

Server: http://127.0.0.1:8000

API docs: http://127.0.0.1:8000/docs

---

## Tests

```bash
pytest -v
```

---

## API

### GET /health

```json
{ "status": "ok" }
```

---

### POST /api/v1/jobs

Create a bulk generation job. Returns immediately with a job ID.

**Request:**

```json
{
  "event_name": "AI Workshop 2026",
  "organization_name": "Example Organization",
  "event_date": "2026-10-07",
  "recipients": [
    {
      "name": "Subash S",
      "email": "subash@example.com",
      "certificate_id": "CERT-001"
    },
    {
      "name": "Rahul Kumar",
      "email": "rahul@example.com",
      "certificate_id": "CERT-002"
    }
  ]
}
```

**Response — HTTP 202:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "total": 2
}
```

---

### GET /api/v1/jobs/{job_id}

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed_with_errors",
  "event_name": "AI Workshop 2026",
  "organization_name": "Example Organization",
  "event_date": "2026-10-07",
  "total": 10,
  "processed": 10,
  "successful": 8,
  "failed": 2,
  "progress": 100.0,
  "created_at": "2026-10-07T09:00:00Z",
  "completed_at": "2026-10-07T09:00:05Z",
  "failures": [
    {
      "recipient_id": "...",
      "name": "John Doe",
      "email": "john@example.com",
      "certificate_id": "CERT-009",
      "error": "Certificate generation failed"
    }
  ]
}
```

---

### GET /api/v1/jobs/{job_id}/certificates

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_certificates": 8,
  "certificates": [
    {
      "certificate_id": "CERT-001",
      "recipient_name": "Subash S",
      "recipient_email": "subash@example.com",
      "download_url": "/api/v1/certificates/CERT-001"
    }
  ]
}
```

---

### GET /api/v1/certificates/{certificate_id}

Returns the PDF file with `Content-Type: application/pdf`. Returns 404 if not found.

---

## Job Status

```
QUEUED -> PROCESSING -> COMPLETED
                     -> COMPLETED_WITH_ERRORS
                     -> FAILED  (system error only)
```

Recipient statuses: `PENDING -> PROCESSING -> SUCCESS / FAILED`

If one recipient fails, the others continue. The job ends as `completed_with_errors`, not `failed`.

---

## Project Structure

```
bulk-certificate-generator/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── api/
│   │   ├── jobs.py
│   │   └── certificates.py
│   ├── services/
│   │   ├── certificate_generator.py
│   │   └── job_processor.py
│   └── templates/
│       └── certificate_template.py
├── tests/
│   ├── conftest.py
│   ├── test_jobs.py
│   ├── test_validation.py
│   ├── test_generation.py
│   ├── test_status.py
│   └── test_certificates.py
├── generated_certificates/
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Design Notes

**Why BackgroundTasks and not Celery/Redis?**

The assignment does not require a distributed task queue. `BackgroundTasks` runs the job after the HTTP response is sent, which is sufficient for this scope. A production system handling high volume would move to Celery + Redis workers, but that would add infrastructure complexity that is not warranted here.

**Background task session handling**

The background task creates its own SQLAlchemy session using `SessionLocal()`. It cannot reuse the HTTP request session because that session is closed by the time the background task starts.

**Why local file storage?**

Simple and has no external dependencies. In production, generated PDFs would go to object storage (S3 or equivalent). The file path stored in the database would just point there instead.

**Why SQLite?**

Zero setup, works everywhere. Swapping to PostgreSQL only requires changing `DATABASE_URL` in `.env`.

---

## Limitations

- `BackgroundTasks` processes jobs in the same process as the web server. Not suitable for high-concurrency production use.
- Local file storage only. Files are lost if the server moves.
- No authentication.
- Failed recipients are not retried automatically.

---

## Possible Extensions

- Celery + Redis for background processing
- PostgreSQL for production database
- S3 for certificate storage
- Authentication (JWT)
- Retry logic for failed recipients
- Docker setup

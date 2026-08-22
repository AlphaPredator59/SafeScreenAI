# SafeScreen AI Backend

Backend foundation for an explainable, context-aware video moderation platform. It provides application configuration, structured logging, a PostgreSQL/SQLAlchemy domain layer, Alembic migrations, and a versioned FastAPI health endpoint. Video ingestion and AI processing are deliberately not implemented yet.

## Prerequisites

- Python 3.11 or newer
- PostgreSQL 16 or newer (needed by later database-backed milestones)

## Local setup

Create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies and create local configuration:

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `DATABASE_URL` in `.env` to match your PostgreSQL instance. The health endpoint does not require a running database.

## PostgreSQL and migrations

Create a local development database (replace the credentials as needed):

```powershell
psql -U postgres -c "CREATE DATABASE safescreen;"
```

Set `DATABASE_URL` in `.env` using SQLAlchemy's psycopg driver format:

```text
DATABASE_URL=postgresql+psycopg://postgres:your-password@localhost:5432/safescreen
```

Apply the initial migration:

```powershell
python -m alembic upgrade head
```

To create a migration after a future model change:

```powershell
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
```

The initial schema contains videos, moderation results, detections, evidence, and transcript segments. The application does not connect to PostgreSQL until a database-backed feature or a future readiness check explicitly uses it.

## Run the API

From the repository root:

```powershell
uvicorn app.main:app --app-dir backend --reload
```

Verify the service:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Expected response:

```json
{"status":"ok","service":"SafeScreen AI"}
```

## Tests

```powershell
pytest
```

The unit suite uses isolated SQLite databases, so it does not require a local PostgreSQL server. PostgreSQL remains the supported runtime database and the Alembic migration targets PostgreSQL-compatible SQLAlchemy types.

## Video upload

`POST /api/v1/videos` accepts multipart field `file`. Supported extensions are MP4, MOV, AVI, and MKV. The current limits are 500 MB and 30 minutes.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/videos -F "file=@C:\path\to\video.mp4;type=video/mp4"
```

```json
{"video_id":"vid_...","status":"UPLOADED"}
```

Files are streamed into `STORAGE_PATH/videos` with server-generated filenames; the client filename is never used as a path. `GET /api/v1/videos/{video_id}` returns stored public metadata and `GET /api/v1/videos/{video_id}/status` returns only the ID and status.

## Internal processing foundation

Internal services sample JPEG frames every `FRAME_SAMPLING_INTERVAL_SECONDS` (default: one second) into controlled `storage/frames` paths, and extract audio into `storage/audio` paths. Audio inspection/extraction requires `ffprobe` and `ffmpeg` available on `PATH`; videos without an audio stream return a successful no-audio result.

## AI interfaces

AI services use vendor-neutral contracts and Protocol interfaces for vision, transcription, text moderation, and context analysis. Deterministic mocks keep tests fast; a YOLO, Whisper, transformer, or VLM adapter can later implement the same interface without changing callers.

## Current structure

```text
backend/
  app/
    api/          Versioned route registration and route handlers
    core/         Settings and logging
    db/           SQLAlchemy engine, enums, models, and session dependency
    schemas/      Pydantic request and response schemas
    main.py       Application factory and FastAPI entry point
  tests/
storage/          Local runtime storage (ignored except for .gitkeep)
migrations/       Alembic migration environment and revision history
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Public application name |
| `APP_ENV` | Runtime environment label |
| `API_V1_PREFIX` | Prefix for public API routes |
| `LOG_LEVEL` | Python log level |
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL |
| `STORAGE_PATH` | Local media storage location |

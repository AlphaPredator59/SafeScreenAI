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

## AI architecture & model adapters

AI services adhere to vendor-neutral contracts and Protocol interfaces for vision, speech-to-text, text moderation, and context analysis. Deterministic mocks keep tests fast, and real adapters can be activated via configuration:

- **Vision (`YoloVisionAnalyzer`)**: Uses Ultralytics YOLO models (default: `yolov8n.pt`, ~6MB nano model) for visual object and weapon/tool detection. Produces timestamped `VisualDetection` contracts with bounding box metadata.
- **Speech-to-Text (`WhisperTranscriber`)**: Uses OpenAI Whisper (default: `tiny`, ~75MB) for speech transcription with segment timestamps. Handles videos without audio streams gracefully.
- **Text Moderation (`TransformerTextModerator`)**: Uses Hugging Face transformer sequence classification pipelines (default: `unitary/toxic-bert`) to evaluate transcript text and extract policy signals (`TextModerationSignal`).
- **Context Engine (`QwenContextAnalyzer`)**: Uses local Qwen 2.5 VL 7B (`qwen2.5vl:7b`) via Ollama. Fuses visual detections, video frames, Whisper audio transcripts, and text policy signals into a structured `ContextualInterpretation`.
- **Deterministic Mocks**: `MockVisionAnalyzer`, `MockTranscriber`, `MockTextModerator`, and `MockContextAnalyzer` provide zero-latency, deterministic execution for local development and CI.

### Model Execution & Hardware Requirements
- **Inference Hardware**: YOLO and Whisper run on standard multi-core CPUs or CUDA. Qwen 2.5 VL (`qwen2.5vl:7b`) runs locally via Ollama with 4-bit quantization on the NVIDIA RTX 3070 Laptop GPU (consuming ~6.6 GB VRAM).
- **Automatic Downloads**: When `AI_MODE=real`, YOLO and Whisper download their checkpoints on first use, and `QwenContextAnalyzer` connects to the local Ollama runtime.

### Switching AI Mode
In `.env`:
```text
# Use fast mocks for test suites & offline dev (default)
AI_MODE=mock

# Or activate real AI models on CPU / CUDA + Ollama Qwen
AI_MODE=real
AI_DEVICE=cpu
CONTEXT_MODEL_NAME=qwen2.5vl:7b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### Running Real Model Smoke Tests
To verify live model inference across YOLO, Whisper, Transformer, and Qwen 2.5 VL:
```powershell
python scripts/smoke_test_ai_models.py --device cpu --qwen-model qwen2.5vl:7b
```

## Current structure

```text
backend/
  app/
    api/          Versioned route registration and route handlers
    core/         Settings and logging
    db/           SQLAlchemy engine, enums, models, and session dependency
    schemas/      Pydantic request and response schemas
    services/
      ai/         AI contracts, protocols, mocks, YOLO/Whisper/Transformer/Qwen adapters, and factory
      video/      Video ingestion, validation, metadata, processing, and repository
    main.py       Application factory and FastAPI entry point
  tests/          Unit tests for domain, migrations, ingestion, processing, AI adapters, and context engine
storage/          Local runtime storage (ignored except for .gitkeep)
migrations/       Alembic migration environment and revision history
scripts/          Utility and smoke testing scripts
```

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_NAME` | Public application name | `SafeScreen AI` |
| `APP_ENV` | Runtime environment label | `development` |
| `API_V1_PREFIX` | Prefix for public API routes | `/api/v1` |
| `LOG_LEVEL` | Python log level | `INFO` |
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL | `postgresql+psycopg://...` |
| `STORAGE_PATH` | Local media storage location | `storage` |
| `AI_MODE` | AI adapter mode (`mock` or `real`) | `mock` |
| `AI_DEVICE` | Hardware device for inference (`cpu` or `cuda`) | `cpu` |
| `VISION_MODEL_NAME` | YOLO model identifier / checkpoint path | `yolov8n.pt` |
| `VISION_CONFIDENCE_THRESHOLD` | Vision minimum detection confidence | `0.25` |
| `TRANSCRIPTION_MODEL_NAME` | Whisper model size (`tiny`, `base`, `small`, etc.) | `tiny` |
| `TEXT_MODERATION_MODEL_NAME` | Hugging Face model identifier for text classification | `unitary/toxic-bert` |
| `TEXT_MODERATION_CONFIDENCE_THRESHOLD` | Minimum text moderation signal confidence | `0.5` |
| `CONTEXT_MODEL_NAME` | Local Qwen model tag in Ollama | `qwen2.5vl:7b` |
| `OLLAMA_BASE_URL` | Ollama HTTP endpoint URL | `http://127.0.0.1:11434` |
| `CONTEXT_TIMEOUT_SECONDS` | Timeout in seconds for Qwen VLM generation | `120.0` |

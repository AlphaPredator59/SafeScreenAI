# SafeScreen AI — Explainable Context-Aware Video Moderation Backend

SafeScreen AI is a modular, explainable backend platform for automated video moderation. It evaluates uploaded videos for potentially harmful or policy-violating content using computer vision, speech-to-text, natural language processing, multimodal contextual analysis, and deterministic risk scoring.

Rather than relying on isolated keyword or object detections—which often produce false positives (e.g., mistaking a culinary kitchen knife for a weapon)—SafeScreen synthesizes multimodal evidence across time, analyzes situational context, and produces grounded, auditable moderation decisions with timestamped evidence references.

---

## Architecture Overview

The system follows a strict layered architecture:

```text
API Layer (FastAPI)
       ↓
Service Layer (Ingestion, Audio/Frame Extractors, AI Adapters, Moderation Engine)
       ↓
Business Logic (Temporal Windowing, Token Budgeting, Policy Severity Scoring, Context Mitigation)
       ↓
Data Access (SQLAlchemy ORM + PostgreSQL Repositories)
       ↓
External Models & Runtime (YOLOv8, Whisper, Toxic-BERT, Ollama Qwen 2.5-VL)
```

### The 9-Stage Moderation Pipeline

1. **Stage 1 — Metadata Extraction**: Extracts duration, resolution, frame rate, container codec, and audio stream presence via `ffprobe` and OpenCV.
2. **Stage 2 — Frame Processing**: Samples video frames at configurable intervals (`FRAME_SAMPLING_INTERVAL_SECONDS`, default 1.0s) and persists JPEG artifacts with deterministic IDs.
3. **Stage 3 — Audio Extraction**: Extracts audio tracks via FFmpeg into normalized 16kHz WAV format. Videos without audio are handled gracefully without pipeline failure.
4. **Stage 4 — Vision Analysis (YOLO)**: Runs YOLOv8 (`yolov8n.pt`) to detect visual objects, tools, weapons, and persons, capturing bounding boxes, timestamps, and confidence scores.
5. **Stage 5 — Speech Transcription (Whisper)**: Transcribes spoken dialogue with start/end segment timestamps using OpenAI Whisper (`tiny`).
6. **Stage 6 — Text Moderation (Transformer)**: Evaluates dialogue segments against safety categories using Hugging Face sequence classification (`unitary/toxic-bert`).
7. **Stage 7 — Multimodal Context Analysis (Qwen 2.5 VL)**: Employs local Qwen 2.5 VL 7B via Ollama to synthesize situational context across bounded temporal windows (e.g., distinguishing cooking from physical assault).
8. **Stage 8 — Moderation Engine Evaluation**: Synthesizes all evidence, applies category severity and context mitigation/aggravation rules, decouples model confidence from risk score, and determines the final platform outcome: `APPROVED`, `REVIEW_REQUIRED`, or `REJECTED`.
9. **Stage 9 — Persistence & Structured Reporting**: Persists the run atomically to PostgreSQL (`moderation_results`, `detections`, `evidence`, `transcript_segments`) and generates structured, audit-ready reports without runtime re-computation.

---

## AI Models & Multimodal Reasoning

| Modality | Default Model | Implementation | Role |
|---|---|---|---|
| **Vision** | `yolov8n.pt` | `YoloVisionAnalyzer` (Ultralytics) | Object detection, weapon/tool identification, person tracking |
| **Speech-to-Text** | `tiny` | `WhisperTranscriber` (OpenAI Whisper) | Spoken dialogue transcription with timestamped segments |
| **Text Moderation** | `unitary/toxic-bert` | `TransformerTextModerator` (Hugging Face) | Toxic speech, harassment, hate speech, threat classification |
| **Context Analysis** | `qwen2.5vl:7b` | `QwenContextAnalyzer` (Ollama runtime) | Multimodal situational reasoning & scenario interpretation |
| **Decision Engine** | Deterministic Engine | `ModerationEngine` | Policy severity weighting, risk calculation, context mitigation |

### Scalable Temporal Context Architecture

To support arbitrarily long multi-minute videos without exceeding the VLM context window:
- **Temporal Windowing**: The video timeline is divided into bounded 30-second windows with 5-second overlaps.
- **Activity-Aware Candidate Filtering**: Windows lacking signals or activity are handled deterministically without dispatching expensive VLM queries.
- **Evidence Summarization**: Visual detections within each window are aggregated into category summaries, bounding boxes, and timestamp spans.
- **Proactive Token-Budget Enforcement**: Input sizes are estimated before dispatch and bounded to `CONTEXT_MAX_INPUT_TOKENS` (default 6,000 tokens), dynamically pruning extra images if necessary.
- **Runtime Context Sizing**: Ollama requests explicitly allocate `num_ctx = CONTEXT_NUM_CTX` (default 8,192 tokens) via `/api/chat` options to ensure vision transformer tokens fit comfortably.

---

## Prerequisites

- **Python**: 3.11 or 3.12
- **PostgreSQL**: 15 or newer
- **FFmpeg & FFprobe**: Available on system `PATH`
- **Ollama**: (Required for real AI mode) running locally with `qwen2.5vl:7b` loaded (`ollama run qwen2.5vl:7b`)
- **GPU (Optional)**: NVIDIA CUDA GPU recommended for real model inference; CPU execution is fully supported for testing.

---

## Local Setup

### 1. Virtual Environment & Dependencies

```powershell
# Create and activate virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment configuration:

```powershell
Copy-Item .env.example .env
```

Ensure the PostgreSQL credentials and Ollama configuration in `.env` match your local environment:

```ini
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/safescreen
AI_MODE=mock              # Set to 'real' for live model execution
AI_DEVICE=cpu             # Set to 'cuda' for GPU acceleration
CONTEXT_NUM_CTX=8192
CONTEXT_MAX_INPUT_TOKENS=6000
```

### 3. Database Initialization & Migrations

Create the database in PostgreSQL:

```powershell
psql -U postgres -c "CREATE DATABASE safescreen;"
```

Apply Alembic migrations:

```powershell
.venv\Scripts\alembic upgrade head
```

#### Migration History
- `20260821_0001`: Initial schema (`videos`, `moderation_results`, `detections`, `evidence`, `transcript_segments`).
- `20260823_0002`: Updated enums and foreign key cascades.
- `20261008_0003`: Altered `evidence.content` from `VARCHAR(1024)` to `TEXT` for unbounded multimodal explanation persistence.

---

## Running the Application

### Start FastAPI Server

```powershell
$env:PYTHONPATH='backend'
.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

Verify service health:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
```

Expected response:
```json
{"status":"ok","service":"SafeScreen AI"}
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

---

## API Usage Guide

### 1. Upload Video
`POST /api/v1/videos`

Accepts multipart form-data. Validates file signature, MIME type, duration (max 30 mins), and size (max 500 MB).

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/videos -F "file=@Test Videos\Cooking.mp4;type=video/mp4"
```

Response:
```json
{
  "video_id": "vid_d2a1d419bb6845e99ab243358e0b4a78",
  "filename": "Cooking.mp4",
  "status": "UPLOADED",
  "duration": 10.6,
  "file_size": 15404927
}
```

### 2. Check Video Processing Status
`GET /api/v1/videos/{video_id}/status`

```powershell
curl.exe http://127.0.0.1:8000/api/v1/videos/{video_id}/status
```

Response:
```json
{
  "video_id": "vid_d2a1d419bb6845e99ab243358e0b4a78",
  "status": "COMPLETED"
}
```

### 3. Retrieve Full Moderation Report
`GET /api/v1/videos/{video_id}/moderation`

Retrieves the structured report from PostgreSQL with findings, confidence scores, risk level, and explainability narrative:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/videos/{video_id}/moderation
```

Sample Response:
```json
{
  "video_id": "test_cooking",
  "filename": "Cooking.mp4",
  "decision": "APPROVED",
  "risk_level": "LOW",
  "risk_score": 0.0,
  "overall_confidence": 0.6701,
  "detected_categories": [],
  "explanation": "Evidence Analyzed: 39 visual detection(s) including ['knife' (0.92), 'person' (0.74)]; context inferred as 'Cooking' (conf: 0.95)... Contextual Impact: Verified benign context ('Cooking') confirms objects are non-harmful tools, mitigating policy risk. Final moderation outcome is APPROVED.",
  "findings": [],
  "evidence": [],
  "transcripts": []
}
```

### 4. Retrieve Traceable Evidence
`GET /api/v1/videos/{video_id}/evidence`

Returns all traceable multi-modal evidence items (frames, timestamps, context explanations) supporting policy findings:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/videos/{video_id}/evidence
```

---

## Running Automated Tests

SafeScreen includes comprehensive test suites (unit, integration, API, migration, and temporal pipeline tests). By default, tests run using isolated SQLite sessions and deterministic AI mocks, requiring no external GPU or Ollama runtime.

```powershell
# Run the entire test suite (115 tests)
$env:PYTHONPATH='backend'
.venv\Scripts\pytest
```

To run individual test modules:
```powershell
# Test temporal context windowing & token budgets
.venv\Scripts\pytest backend/tests/test_temporal_context_pipeline.py

# Test moderation engine decisioning & mitigation
.venv\Scripts\pytest backend/tests/test_moderation_engine.py

# Test PostgreSQL persistence & report generation
.venv\Scripts\pytest backend/tests/test_moderation_persistence.py

# Test API endpoints
.venv\Scripts\pytest backend/tests/test_moderation_routes.py
```

---

## Running the End-to-End Pipeline Evaluation

You can execute the full 9-stage pipeline against test videos on CPU or CUDA:

```powershell
# Run with real AI models on CUDA
.venv\Scripts\python scripts/test_video_pipeline.py --video "Test Videos/Cooking.mp4" --ai-mode real --device cuda

# Run with real AI models on CPU
.venv\Scripts\python scripts/test_video_pipeline.py --video "Test Videos/Shooting Range.mp4" --ai-mode real --device cpu

# Run in mock mode for instant end-to-end testing
.venv\Scripts\python scripts/test_video_pipeline.py --video "Test Videos/Cooking.mp4" --ai-mode mock
```

---

## Project Structure

```text
SafeScreen/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/          # Versioned REST endpoints (health, videos, moderation)
│   │   │   └── validators.py    # Request ID and input format validators
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic BaseSettings loaded from .env
│   │   │   └── logging.py       # Structured JSON/console logging
│   │   ├── db/
│   │   │   ├── database.py      # SQLAlchemy engine, session maker, and connectivity checks
│   │   │   ├── enums.py         # ModerationDecision, RiskLevel, VideoStatus enums
│   │   │   └── models.py        # Video, ModerationResult, Detection, Evidence, Transcript models
│   │   ├── schemas/             # Pydantic request & response schemas
│   │   └── services/
│   │       ├── ai/              # AI contracts, YOLO, Whisper, Toxic-BERT, Qwen, and factory
│   │       │   ├── context.py   # QwenContextAnalyzer Ollama adapter
│   │       │   ├── contracts.py # TimestampedFrame, VisualDetection, TranscriptSegment, Context
│   │       │   ├── factory.py   # AI service resolver (mock vs real)
│   │       │   └── temporal.py  # Temporal windowing, frame selection, token-budget enforcement
│   │       ├── evaluation/      # Benchmark dataset schemas, loaders, metrics, and ablations
│   │       ├── moderation/      # ModerationEngine, persistence, repository, reporting
│   │       └── video/           # Ingestion, validation, metadata, frame & audio processing
│   │   └── main.py              # FastAPI app initialization and route registration
│   └── tests/                   # 115 unit and integration tests
├── evaluation/                  # Benchmark dataset (12 scenarios), metrics, and reports
├── migrations/                  # Alembic environment and database revisions (0001 - 0003)
├── scripts/
│   ├── run_evaluation.py        # Benchmark suite runner with ablation studies
│   ├── smoke_test_ai_models.py  # Standalone live inference validation for AI models
│   └── test_video_pipeline.py   # End-to-End M1–M9 video pipeline evaluation script
├── storage/                     # Local artifact storage (videos, frames, audio)
├── Test Videos/                 # Sample video clips (Cooking, Slap, Shooting Range, etc.)
├── AGENTS.md                    # Backend architecture rules and development principles
├── PROJ_SPEC.md                 # Master project specification and source of truth
└── README.md                    # Project documentation
```

---

## Implementation Status & Roadmap

### What is Fully Implemented

- [x] **Backend Foundation**: FastAPI application, structured logging, configuration management via Pydantic BaseSettings.
- [x] **Relational Persistence**: PostgreSQL with SQLAlchemy ORM, connection pooling, and reversible Alembic migrations.
- [x] **Schema Optimization**: Altered `evidence.content` to PostgreSQL `TEXT` for unbounded multimodal explanation storage.
- [x] **Secure Video Ingestion**: MIME/header validation, size/duration constraints, path traversal protection, server-side UUID storage.
- [x] **Video & Audio Preprocessing**:
  - Frame sampling at customizable intervals (JPEG artifacts with timestamp references).
  - Audio extraction via FFmpeg/ffprobe to 16kHz WAV, gracefully supporting videos without audio.
- [x] **AI Adapters & Abstract Interfaces**:
  - Vendor-neutral protocols (`VisionAnalyzer`, `Transcriber`, `TextModerator`, `ContextAnalyzer`).
  - Full deterministic mock suite for zero-latency CI and offline testing.
  - Real YOLOv8 adapter with bounding box extraction.
  - Real OpenAI Whisper adapter with timestamped dialogue segments.
  - Real Hugging Face Transformer adapter (`toxic-bert`) for policy signals.
- [x] **Scalable Multimodal Context Engine**:
  - Local Qwen 2.5 VL 7B integration via Ollama API.
  - Temporal windowing pipeline handling arbitrary multi-minute videos without context window blowup.
  - Dynamic runtime context sizing (`options.num_ctx = CONTEXT_NUM_CTX`).
  - Proactive token-budget estimation and image pruning (`CONTEXT_MAX_INPUT_TOKENS = 6000`).
- [x] **Context-Aware Moderation Engine**:
  - Standalone, deterministic decisioning service.
  - Separation of model confidence from moderation risk.
  - Contextual mitigation rules (e.g., culinary knives in cooking context producing `APPROVED` with zero violation rows).
  - Contextual aggravation rules (e.g., physical altercation producing `REVIEW_REQUIRED`).
- [x] **Persistence & Reporting Service**:
  - Atomic persistence of moderation outcomes into PostgreSQL with automatic rollback on error.
  - Clean re-processing replacement without orphaned records.
  - Path sanitization preventing internal server storage paths from leaking in API responses.
  - REST endpoints for reports (`GET /videos/{id}/moderation`) and evidence (`GET /videos/{id}/evidence`).
- [x] **Evaluation & Benchmarking Framework**:
  - Benchmark dataset covering 12 distinct moderation scenarios.
  - Automated evaluation runner supporting modality ablation studies (`full`, `visual_qwen`, `visual_audio`, `visual_only`).
  - Error diagnostics and confusion matrix generation.
- [x] **Automated Test Suite**: 115 passing tests across all layers.

---

### What is Left to Implement

The following items are designated for subsequent milestones:

1. **Background Job Queue & Worker System (Celery / Redis / ARQ)**:
   - *Current State*: The API provides upload and retrieval endpoints, while end-to-end pipeline execution is run synchronously or via evaluation scripts.
   - *Next Step*: Decouple upload from processing by dispatching moderation jobs to a distributed worker pool (e.g., Celery + Redis or ARQ), updating video status asynchronously (`UPLOADED` → `PROCESSING` → `COMPLETED` / `FAILED`).

2. **Video Lifecycle Management Endpoints**:
   - `DELETE /api/v1/videos/{video_id}`: Remove video record, database associations, and disk artifacts (frames, audio, raw video).
   - `POST /api/v1/videos/{video_id}/retry`: Allow re-triggering failed or incomplete moderation runs without re-uploading.
   - `POST /api/v1/videos/{video_id}/review`: Enable human moderators to submit manual overrides or review resolutions for `REVIEW_REQUIRED` videos.

3. **Evidence Association Optimization**:
   - *Current State*: If a policy violation is flagged, all valid visual detections across the video are currently attached to that detection finding as raw evidence items.
   - *Next Step*: Filter attached visual evidence items to only include objects directly associated with the flagged policy category or proximate in time to the violation timestamps, reducing database footprint for long videos.

4. **Containerization & Deployment Architecture**:
   - Production multi-stage `Dockerfile` for the FastAPI backend and AI dependencies.
   - `docker-compose.yml` orchestrating PostgreSQL, Redis, Ollama, and FastAPI worker containers.

5. **Authentication & Authorization**:
   - API key or JWT-based authentication for upload and administrative endpoints.
   - Role-Based Access Control (RBAC) distinguishing standard uploaders from compliance moderators.

6. **Frontend & Moderator Dashboard (Out of Current Backend Scope)**:
   - Reviewer web dashboard for human moderation teams to inspect flagged videos, scrubber-synchronized bounding boxes, and timestamped transcripts.

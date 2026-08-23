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
- **Moderation Engine (`ModerationEngine`)**: Standalone, deterministic decisioning service that synthesizes multi-modal signals, evaluates category severity, applies contextual mitigation/aggravation rules (e.g. cooking context mitigating knife detections), computes decoupled risk scores vs confidence, and outputs grounded `ModerationResult` assessments.
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

## Moderation Persistence & Reporting (Milestone 9)

Milestone 9 completes the moderation lifecycle by persisting domain evaluation outcomes to PostgreSQL and exposing them via structured, sanitized public API endpoints without LLM re-computation:

- **Moderation Persistence Layer (`ModerationPersistenceService`, `ModerationRepository`)**:
  - Atomically stores decision, risk level, risk score, confidence, and explainability narrative in `moderation_results`.
  - Persists policy-relevant findings into `detections` (raw non-violating objects like cooking knives or vegetables are NOT recorded as policy violations).
  - Persists multi-modal evidence items in `evidence` with sanitized public references (preventing internal host path exposure).
  - Persists spoken dialogue segments in `transcript_segments` (videos with no audio record 0 rows and succeed).
  - Supports atomic re-processing: re-evaluating a video cleanly replaces the prior moderation tree without orphan records.
- **Report & Evidence Retrieval Service (`ModerationReportService`)**:
  - Generates comprehensive `ModerationReportResponse` objects directly from PostgreSQL.
  - Exposes dedicated `GET /api/v1/videos/{video_id}/evidence` collections (empty lists for benign videos with 0 evidence).

### API Endpoints

#### 1. Retrieve Full Moderation Report
`GET /api/v1/videos/{video_id}/moderation`

```powershell
curl.exe http://127.0.0.1:8000/api/v1/videos/{video_id}/moderation
```

Sample JSON response:
```json
{
  "video_id": "test_slap",
  "filename": "Slap.mp4",
  "created_at": "2026-08-23T11:50:50.123456Z",
  "decision": "REVIEW_REQUIRED",
  "risk_level": "HIGH",
  "risk_score": 0.765,
  "overall_confidence": 0.8261,
  "detected_categories": ["threats"],
  "explanation": "Evidence Analyzed: 39 visual detection(s)... context inferred as 'threatening interaction' (conf: 0.90)... Contextual Impact: Identified threatening/hostile context reinforced policy risk.",
  "findings": [
    {
      "id": "det_...",
      "category": "threats",
      "confidence": 0.95,
      "start_timestamp": 0.0,
      "end_timestamp": 30.0,
      "explanation": "Policy finding for 'threats' supported by multi-modal evidence synthesis.",
      "evidence_references": ["frame_3d7e96a449fd4789bf034c84b716c522", "..."]
    }
  ],
  "evidence": [
    {
      "id": "ev_...",
      "type": "context",
      "timestamp": 0.0,
      "content": "Threatening altercation detected",
      "reference": "frame_3d7e96a449fd4789bf034c84b716c522"
    }
  ],
  "transcripts": [
    {
      "start_timestamp": 0.0,
      "end_timestamp": 2.0,
      "text": "you"
    }
  ]
}
```

#### 2. Retrieve Traceable Evidence Collection
`GET /api/v1/videos/{video_id}/evidence`

```powershell
curl.exe http://127.0.0.1:8000/api/v1/videos/{video_id}/evidence
```

Sample JSON response:
```json
{
  "video_id": "test_cooking",
  "total_count": 0,
  "evidence": []
}
```

## Benchmark Evaluation & Quality Analysis (Milestone 10)

Milestone 10 introduces a systematic evaluation, benchmarking, and error analysis framework to assess moderation decision accuracy, cross-modal disagreements, per-stage latencies, and ablation dynamics.

- **Evaluation Dataset (`evaluation/dataset.json`)**:
  - Represents 12 distinct moderation scenarios (benign cooking, shooting range, physical assault, ambiguous weapons, sports, educational demos, toxic speech, audio-only threats, silent violence, and neutral scenes).
  - Maintains strict ground-truth separation across expected context, expected decision, expected risk band, and expected policy categories.
  - Transparently distinguishes between confirmed available test media and placeholder scenarios.
- **Evaluation Runner (`scripts/run_evaluation.py`)**:
  - Executes benchmarks across dataset samples using the real M1–M9 pipeline without modifying model weights.
  - Supports modality ablation studies (`full`, `visual_qwen`, `visual_audio`, `visual_only`).
  - Exports structured artifacts into `evaluation/`:
    - `results.json`: Detailed sample-level prediction records.
    - `metrics.json`: Serialized decision, context, policy, disagreement, and latency metrics.
    - `summary.md`: Human-readable benchmark report with confusion matrices and ablation comparisons.
    - `errors.md`: Structured root-cause error diagnostics.

### Running Benchmark Evaluations & Ablations

```powershell
# Run benchmark evaluation on available test videos with ablation analysis
python scripts/run_evaluation.py --ai-mode real --device cpu --ablations
```

## Running the End-to-End Pipeline

Run all 9 stages (M1–M9) against real local models and PostgreSQL:

```powershell
# Run on benign cooking video
python scripts/test_video_pipeline.py --video "Test Videos/Cooking.mp4"

# Run on shooting range video
python scripts/test_video_pipeline.py --video "Test Videos/Shooting Range.mp4"

# Run on threatening/violence altercation video
python scripts/test_video_pipeline.py --video "Test Videos/Slap.mp4"
```

## Current structure

```text
backend/
  app/
    api/          Versioned route registration (health, videos, moderation)
    core/         Settings and logging
    db/           SQLAlchemy engine, enums, models, and session dependency
    schemas/      Pydantic request and response schemas (health, video, moderation)
    services/
      ai/         AI contracts, protocols, mocks, YOLO/Whisper/Transformer/Qwen adapters, and factory
      evaluation/ Dataset schemas, loaders, metrics calculator, runner, and report generator
      moderation/ ModerationEngine, severity configs, evidence traceability, repository, persistence, reporting
      video/      Video ingestion, validation, metadata, processing, and repository
    main.py       Application factory and FastAPI entry point
  tests/          Unit and integration tests (migrations, domain, ingestion, processing, AI adapters, context engine, moderation engine, persistence, API routes, evaluation)
evaluation/       Benchmark dataset, metrics JSON, summary markdown, and error diagnostics
storage/          Local runtime storage (ignored except for .gitkeep)
migrations/       Alembic migration environment and revision history
scripts/          Pipeline evaluation, benchmark runner, and smoke test scripts
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
| `MODERATION_LOW_RISK_THRESHOLD` | Risk score bound for LOW risk band | `0.30` |
| `MODERATION_MEDIUM_RISK_THRESHOLD` | Risk score bound for MEDIUM risk band | `0.60` |
| `MODERATION_HIGH_RISK_THRESHOLD` | Risk score bound for HIGH/CRITICAL risk band | `0.85` |
| `MODERATION_AUTO_REJECT_THRESHOLD` | Threshold above which content is REJECTED | `0.85` |
| `MODERATION_REVIEW_THRESHOLD` | Threshold above which content is REVIEW_REQUIRED | `0.40` |
| `MODERATION_MIN_SIGNAL_CONFIDENCE` | Minimum signal confidence considered by engine | `0.30` |

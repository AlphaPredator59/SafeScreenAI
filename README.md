# SafeScreen AI — Explainable Context-Aware Video Moderation Platform

SafeScreen AI is an end-to-end, explainable video moderation platform. It evaluates uploaded videos for policy-violating and harmful content by synthesizing computer vision, speech-to-text, natural language processing, multimodal contextual understanding, temporal event clustering, and deterministic risk scoring.

Rather than relying on isolated keyword matches or object detections—which notoriously trigger false positives (e.g., misclassifying kitchen knives in a cooking tutorial as weapons)—SafeScreen understands situational context across time, separates model confidence from policy risk, and produces evidence-grounded, audit-ready moderation reports with Gemini-powered executive summaries.

---

## Key Highlights

- **Full-Stack Production Architecture**: Modern React 19 + Vite frontend paired with a high-throughput FastAPI backend and an asynchronous transactional database worker.
- **Explainable 9-Stage Pipeline**: Modular stages covering video ingestion, frame extraction, audio extraction, visual object detection, speech transcription, toxic dialogue classification, multimodal scene context reasoning, temporal event clustering, and audit reporting.
- **Multimodal AI Stack**:
  - **Vision**: YOLOv8 (`yolov8n.pt`) for real-time object, tool, and person detection.
  - **Speech Transcription**: OpenAI Whisper (`tiny`) for timestamped dialogue extraction.
  - **Text Moderation**: Hugging Face `unitary/toxic-bert` for toxic speech, hate, threat, and harassment detection.
  - **Multimodal Context**: Ollama Qwen 2.5-VL (`qwen2.5vl:7b`) with 30s sliding temporal windowing and token budgeting.
  - **Executive Reporting**: Google Gemini API (`gemini-2.5-flash` / `gemini-1.5-flash`) for executive summaries and AI justifications with deterministic fallback.
- **Temporal Event Clustering & False-Positive Mitigation**: Coalesces frame-by-frame detections into discrete temporal intervals so frame rates do not artificially inflate risk, while suppressing benign objects (e.g., culinary knives in cooking videos).
- **100% Deterministic & Auditable**: Authorized decisions (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`) are strictly derived from deterministic policy engine rules—generative AI enhances report clarity without overriding policy decisions.

---

## Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   SafeScreen Frontend (React 19 + Vite)                │
│       Session Batch Upload • Interactive Timeline • Report Viewer      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (/api/v1)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI REST API Layer                          │
│         /videos (Upload) • /status • /moderation • /evidence           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Persists / Enqueues
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 PostgreSQL Database (or SQLite in dev)                 │
│         Videos • Results • Detections • Evidence • Transcripts         │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ Transactional Claim (SKIP LOCKED)
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                    Async Moderation Worker Process                     │
│                (scripts/worker.py + PipelineRunner)                    │
│                                                                        │
│  Stage 1: Metadata Extraction (ffprobe & OpenCV)                       │
│  Stage 2: Frame Extraction (1.0s interval sampling)                   │
│  Stage 3: Audio Extraction (16kHz WAV via FFmpeg)                      │
│  Stage 4: Visual Object Detection (YOLOv8)                             │
│  Stage 5: Speech Transcription (Whisper)                               │
│  Stage 6: Text Dialogue Moderation (Toxic-BERT)                        │
│  Stage 7: Multimodal Context Analysis (Qwen 2.5-VL via Ollama)         │
│  Stage 8: Temporal Grouping & Policy Engine (ModerationEngine)         │
│  Stage 9: Atomic Persistence & Gemini Executive Report Formatting      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## AI Models & Modality Matrix

| Modality | Model | Implementation | Role |
|---|---|---|---|
| **Vision** | `yolov8n.pt` | `YoloVisionAnalyzer` (Ultralytics) | Object detection, weapon/tool identification, person tracking |
| **Speech-to-Text** | `tiny` | `WhisperTranscriber` (OpenAI Whisper) | Spoken dialogue transcription with timestamped segments |
| **Text Moderation** | `unitary/toxic-bert` | `TransformerTextModerator` (Hugging Face) | Toxic speech, harassment, hate speech, threat classification |
| **Context Analysis** | `qwen2.5vl:7b` | `QwenContextAnalyzer` (Ollama runtime) | Multimodal situational reasoning & scenario interpretation |
| **Policy Engine** | Deterministic Engine | `ModerationEngine` | Policy severity weighting, temporal event clustering, risk calculation |
| **Executive Reporting** | `gemini-2.5-flash` | `GeminiReportFormatter` (Google GenAI) | Professional executive summaries & evidence justifications (with fallback) |

---

## Temporal Event Clustering & Context Mitigation

### Why It Matters
A 5-minute cooking video sampled at 1 frame per second produces over 300 visual detections of a kitchen knife. Traditional systems multiply these detections, triggering a `CRITICAL DANGER` false alarm.

### How SafeScreen Solves It:
1. **Temporal Event Grouping**: Consecutive frame detections within a 5-second gap are coalesced into a single discrete `PolicyEvent` (e.g., "Knife present from 00:12 to 00:35").
2. **Culinary Context Suppression**: When Qwen 2.5-VL detects an active benign context (e.g., `Cooking`, `Food Preparation`, `Artistic Demonstration`), kitchen tools (knives, forks, spoons, bowls) are suppressed from policy violation lists and assigned severity 0.
3. **Discrete Event Severity Accumulation**: Overall risk score is computed by combining discrete violation events rather than raw video frame counts.
4. **Policy Attribution**: Evidence items (frames, timestamps, transcripts) are linked to specific violation events, keeping database payloads lean and audits clear.

---

## Frontend Web Application

The frontend is located in `frontend/` and built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS**.

### Key Features:
- **Session Batch Upload**: Upload single or multiple videos in one session with drag-and-drop support and immediate file validation.
- **Real-Time Video Cards**: Track per-video moderation status (`UPLOADED` → `PROCESSING` → `ANALYZING` → `COMPLETED`) via automatic polling.
- **Interactive Scrubber & Timeline**: Synchronized video player highlighting flagged intervals with color-coded risk markers.
- **Executive Summary & AI Justification**: Displays Gemini-generated executive findings with confidence score indicators and Gemini model badges.
- **Findings Matrix**: Category-by-category breakdown showing detected violations, discrete temporal events, confidence levels, and severity ratings.
- **Timestamped Transcripts**: Complete dialogue transcription with highlighted toxic or hostile phrases.
- **Traceable Evidence Inspector**: Inspect extracted video frames, bounding boxes, and timestamp references.
- **Theme Support**: Seamless dark and light modes with persistent local storage.

---

## Prerequisites

- **Python**: 3.11 or 3.12
- **Node.js**: v18.0.0 or newer (and npm)
- **PostgreSQL**: 15 or newer (or local SQLite for lightweight testing)
- **FFmpeg & FFprobe**: Installed and accessible on your system `PATH`
- **Ollama** *(Optional, for real VLM context)*: Running locally with `qwen2.5vl:7b` (`ollama run qwen2.5vl:7b`)
- **Google Gemini API Key** *(Optional)*: For enhanced executive summaries (graceful deterministic fallback is enabled if key is omitted)
- **GPU (Optional)**: NVIDIA CUDA GPU recommended for live neural inference; CPU and deterministic mock modes are fully supported.

---

## Quickstart Guide

### 1. Clone & Configure Environment

```powershell
# Clone the repository
git clone https://github.com/AlphaPredator59/SafeScreenAI.git
cd SafeScreenAI

# Copy environment template
Copy-Item .env.example .env
```

Edit `.env` to configure your settings:
```ini
# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/safescreen
# (Or use SQLite: DATABASE_URL=sqlite:///backend/app.db)

# AI Runtime Mode
AI_MODE=mock              # Use 'mock' for instant testing or 'real' for live models
AI_DEVICE=cpu             # 'cpu' or 'cuda'

# Gemini Reporting (Optional)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-2.5-flash

# Multimodal Context (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
CONTEXT_MODEL_NAME=qwen2.5vl:7b
CONTEXT_NUM_CTX=8192
CONTEXT_MAX_INPUT_TOKENS=6000
```

### 2. Backend Setup

```powershell
# Create and activate Python virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Run database migrations
.venv\Scripts\alembic upgrade head
```

### 3. Frontend Setup

```powershell
cd frontend
npm install
cd ..
```

---

## Running the Application

SafeScreen runs with three lightweight services:

### Terminal 1: Start FastAPI Backend
```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```
API Documentation will be live at `http://127.0.0.1:8000/docs`.

### Terminal 2: Start Moderation Worker
```powershell
# Run worker in mock AI mode (instant testing without GPU):
.\.venv\Scripts\python.exe scripts/worker.py --ai-mode mock --poll-interval 1.0

# Or run worker with real AI models on GPU:
.\.venv\Scripts\python.exe scripts/worker.py --ai-mode real --device cuda --poll-interval 1.0
```

### Terminal 3: Start Frontend Dev Server
```powershell
cd frontend
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## REST API Reference

### 1. Upload Video
`POST /api/v1/videos`
- Content-Type: `multipart/form-data`
- Parameters: `file` (MP4, WebM, AVI, MOV; up to 500 MB)
- Returns: `video_id`, `filename`, `status`, `duration`, `file_size`

### 2. Check Video Status
`GET /api/v1/videos/{video_id}/status`
- Returns: `video_id`, `status` (`UPLOADED`, `PROCESSING`, `ANALYZING`, `COMPLETED`, `FAILED`)

### 3. Retrieve Full Moderation Report
`GET /api/v1/videos/{video_id}/moderation`
- Returns: Complete audit report including `decision`, `risk_level`, `risk_score`, `executive_summary`, `ai_justification`, `findings` (with discrete `events`), `transcripts`, and `evidence`.

### 4. Retrieve Traceable Evidence
`GET /api/v1/videos/{video_id}/evidence`
- Returns: Traceable list of bounding boxes, frame paths, and timestamps.

### 5. Service Health
`GET /api/v1/health`
- Returns: `{"status": "ok", "service": "SafeScreen AI"}`

---

## Automated Test Suites

SafeScreen includes a complete suite of **143 automated backend tests** covering the moderation engine, policy severity, context mitigation, temporal clustering, Gemini formatting, pipeline runner, API endpoints, and worker polling.

```powershell
# Run entire test suite (143 tests)
$env:PYTHONPATH='backend'
.\.venv\Scripts\pytest backend/tests -q

# Run cooking video regression tests (false-positive prevention)
.\.venv\Scripts\pytest backend/tests/test_cooking_video_regression.py -q

# Run Gemini report formatting & fallback tests
.\.venv\Scripts\pytest backend/tests/test_gemini_report_formatting.py -q

# Run worker & pipeline runner tests
.\.venv\Scripts\pytest backend/tests/test_worker.py backend/tests/test_pipeline_runner.py -q
```

### Frontend Build & Lint Verification
```powershell
cd frontend
npm run lint
npm run build
```

---

## Project Directory Structure

```text
SafeScreenAI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/              # REST endpoints (health, videos, moderation)
│   │   │   └── validators.py        # Input sanitation and validation
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic BaseSettings & environment configs
│   │   │   └── logging.py           # Structured JSON logging
│   │   ├── db/
│   │   │   ├── database.py          # SQLAlchemy engine & session maker
│   │   │   ├── enums.py             # ModerationDecision, RiskLevel, VideoStatus
│   │   │   └── models.py            # Video, ModerationResult, Detection, Evidence, Transcript
│   │   ├── schemas/                 # Pydantic request & response models
│   │   └── services/
│   │       ├── ai/                  # AI adapters (YOLOv8, Whisper, Toxic-BERT, Qwen 2.5-VL)
│   │       │   ├── context.py       # Qwen Ollama multimodal adapter
│   │       │   ├── contracts.py     # Multimodal data contracts
│   │       │   ├── factory.py       # Mock vs Real AI factory
│   │       │   └── temporal.py      # 30s sliding temporal windowing & token budgeting
│   │       ├── moderation/          # Core decisioning & reporting services
│   │       │   ├── contracts.py     # ModerationResult, PolicyFinding, PolicyEvent
│   │       │   ├── engine.py        # ModerationEngine (decision logic & risk weighting)
│   │       │   ├── formatting.py    # GeminiReportFormatter (executive summary & AI justification)
│   │       │   ├── persistence.py   # Atomic database persistence service
│   │       │   ├── pipeline_runner.py # End-to-end 9-stage pipeline coordinator
│   │       │   ├── reporting.py     # ModerationReportService
│   │       │   ├── repository.py    # Database repository access layer
│   │       │   └── temporal_grouping.py # Discrete temporal event clustering & utensil mitigation
│   │       └── video/               # Frame extraction, audio processing, FFmpeg integration
│   │   └── main.py                  # FastAPI application entrypoint
│   └── tests/                       # 143 unit, regression, integration, and API tests
├── frontend/                        # Modern React 19 + TypeScript + Vite + Tailwind SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/              # Navbar, header, theme controls
│   │   │   ├── moderation/          # Findings list, risk breakdown, policy badges
│   │   │   ├── report/              # ExecutiveSummary, FindingsMatrix, Evidence viewer
│   │   │   ├── session/             # Multi-video session cards, metrics grid
│   │   │   ├── upload/              # Batch video upload dropzone & file preview
│   │   │   └── video/               # Synchronized timeline scrubber & video player
│   │   ├── hooks/                   # useSessionVideos, useVideoStatus, useTheme
│   │   ├── pages/                   # SessionVideosPage, ModerationDetailPage
│   │   └── store/                   # SessionContext & Global state
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── migrations/                      # Alembic migrations (revisions 0001 - 0003)
├── scripts/
│   ├── test_video_pipeline.py       # Pipeline validation CLI tool
│   ├── verify_real_video_report.py  # Live Gemini report verification script
│   └── worker.py                    # Standalone background moderation worker
├── documentations/
│   └── ARCHITECTURE.md              # Deep-dive architectural specification
├── DESIGN.md                        # UI/UX design specifications and color tokens
├── PROJ_SPEC.md                     # Master platform specifications
└── README.md                        # Project documentation
```

---

## License

This project is licensed under the Apache 2.0 License.

# SafeScreen AI — Production Backend & Worker Architecture

## 1. System Overview

SafeScreen AI decouples HTTP request handling from AI workload execution. Uploaded videos are accepted and registered immediately by FastAPI, and subsequently processed asynchronously by a standalone PostgreSQL-backed worker process.

```text
┌─────────────────┐
│ React Frontend  │ (Port 5173 / Polling & Navigation)
└────────┬────────┘
         │ HTTP POST /videos
         ▼
┌─────────────────┐
│ FastAPI Backend │ (Port 8000 / Non-blocking Ingestion)
└────────┬────────┘
         │ INSERT INTO videos (status='UPLOADED')
         ▼
┌─────────────────┐
│   PostgreSQL    │ (Queue abstraction via row-level locks)
└────────┬────────┘
         │ FOR UPDATE SKIP LOCKED (status='PROCESSING')
         ▼
┌─────────────────┐
│ Moderation      │ (scripts/worker.py)
│ Worker Process  │
└────────┬────────┘
         │ Invokes PipelineRunner
         ▼
┌─────────────────┐
│ PipelineRunner  │ (backend/app/services/moderation/pipeline_runner.py)
└────────┬────────┘
         │ Orchestrates M1-M9:
         ├─► Frame Extraction (OpenCV)
         ├─► Audio Extraction (FFmpeg)
         ├─► Status Update (status='ANALYZING')
         ├─► YOLOv8 Vision Analysis
         ├─► Whisper Speech Transcription
         ├─► Toxic-BERT Text Moderation
         ├─► Qwen 2.5-VL Context Analysis (Ollama)
         ├─► ModerationEngine Decision & Scoring
         └─► ModerationPersistenceService (status='COMPLETED')
```

---

## 2. Pipeline Architecture: PipelineRunner

The core moderation execution is extracted into a production-grade service:
`backend/app/services/moderation/pipeline_runner.py`

Both the production worker (`scripts/worker.py`) and development/test scripts (`scripts/test_video_pipeline.py`) call the same `PipelineRunner` implementation:

```text
                  PipelineRunner
                  /           \
                 /             \
        Production Worker    Test Script
        (scripts/worker.py)  (scripts/test_video_pipeline.py)
```

### Lifecycle & Status Semantics

The worker and pipeline adhere strictly to the `VideoStatus` domain enum:
- `UPLOADED`: Video file stored and registered; pending analysis.
- `PROCESSING`: Video claimed by a worker; frame/audio extraction underway.
- `ANALYZING`: Multimodal AI inference in progress (YOLO, Whisper, Toxic-BERT, Qwen 2.5-VL).
- `COMPLETED`: Moderation results and explainable findings persisted to PostgreSQL.
- `FAILED`: Unrecoverable processing failure; error captured in server logs.

---

## 3. Concurrency & Claiming Model

To ensure safe concurrent execution without third-party queue brokers (Celery, Redis, RabbitMQ):

1. **Transactional Row Claims**:
   The worker queries pending videos using PostgreSQL's row-level locking:
   ```sql
   SELECT * FROM videos
   WHERE status IN ('UPLOADED', 'QUEUED')
   ORDER BY created_at ASC
   FOR UPDATE SKIP LOCKED
   LIMIT 1;
   ```
2. **Immediate Lock Release**:
   Upon claiming, the worker transitions the row to `VideoStatus.PROCESSING` and commits immediately. The row lock is released, and other workers will never see or claim this video.
3. **No Duplicate Processing**:
   `SKIP LOCKED` guarantees that concurrent worker processes never block each other or duplicate processing.
4. **Crash Safety**:
   If an exception occurs during any stage of processing (extraction, vision, audio, text, VLM, persistence), the worker catches the error, marks the video as `FAILED`, and continues polling without terminating the worker.

---

## 4. How to Run the System

### Step 1: PostgreSQL
Ensure PostgreSQL is running and the database `safescreen` exists:
```powershell
# Default database URL configured in .env:
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/safescreen
```

### Step 2: FastAPI Backend
Start the API server:
```powershell
uvicorn app.main:app --app-dir backend --port 8000
```
API endpoints available:
- Health check: `GET http://localhost:8000/api/v1/health`
- Video ingestion: `POST http://localhost:8000/api/v1/videos`
- Status polling: `GET http://localhost:8000/api/v1/videos/{video_id}/status`
- Moderation report: `GET http://localhost:8000/api/v1/videos/{video_id}/moderation`

### Step 3: SafeScreen Worker
Start the moderation worker in a separate terminal:

**Option A — Mock AI Mode (Fast, zero-GPU requirement):**
```powershell
python scripts/worker.py --ai-mode mock --poll-interval 1.0
```

**Option B — Real AI Mode (Full multimodal neural pipeline):**
```powershell
# Requires Ollama running with qwen2.5vl:7b
python scripts/worker.py --ai-mode real --device cuda --poll-interval 1.0
```

### Step 4: React Frontend
Start the Vite development server:
```powershell
cd frontend
npm run dev -- --port 5173
```
Access the application at `http://localhost:5173`.

---

## 5. AI Execution Modes: Mock vs Real

| Mode | Environment | Vision (YOLO) | Speech (Whisper) | Text (Toxic-BERT) | Context (VLM) | Speed |
|---|---|---|---|---|---|---|
| `AI_MODE=mock` | Local / CI | Mock detections | Mock transcripts | Mock text signals | Mock context | < 0.2s |
| `AI_MODE=real` | CUDA / PyTorch + Ollama | YOLOv8n (`yolov8n.pt`) | Whisper (`tiny`) | Toxic-BERT (`unitary/toxic-bert`) | Qwen 2.5-VL (`qwen2.5vl:7b`) | Model-dependent |

### Benchmark Telemetry (`AI_MODE=real` on NVIDIA RTX 3070 Laptop GPU):
- Test video: `Shooting Range.mp4` (6.52s duration, 1280x720, 4.03 MB)
- Total processing time: `27.70s`
- Ratio (`processing_time / video_duration`): `4.25x` real-time
- Primary bottleneck: Qwen 2.5-VL 7B multimodal context inference (`18.86s`, 68% of pipeline time)

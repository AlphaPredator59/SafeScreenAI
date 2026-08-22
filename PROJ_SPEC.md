# Safe Screen AI — Backend Project Specification

## 1. Project Overview

### Project Name

SafeScreen AI

### Description

A backend system that analyzes uploaded videos for potentially harmful or policy-violating content using computer vision, speech-to-text, natural language processing, and contextual/multimodal analysis.

The system should generate an explainable moderation result containing risk level, detected categories, confidence scores, timestamps, evidence, and reasoning.

### Primary Goal

Build a production-style backend prototype for YouTube-style video moderation.

### Current Scope

**Backend only.**

The frontend, dashboard UI, authentication UI, and production cloud deployment are out of scope for the initial development phase.

---

# 2. Problem Statement

Manual video moderation is expensive, time-consuming, and difficult to scale.

A video can contain thousands of frames, spoken dialogue, objects, actions, and contextual interactions. Detecting a keyword or object alone is often insufficient to determine whether content actually violates a platform policy.

The system should therefore combine multiple sources of evidence and consider context before producing a moderation decision.

Example:

```text
Knife detected
+
Person preparing food
+
Cooking-related transcript
=
Low-risk context
```

Whereas:

```text
Knife detected
+
Person threatening another person
+
Threatening transcript
=
High-risk context
```

---

# 3. Core Backend Responsibilities

The backend should handle:

1. Video upload
2. Video validation
3. Video storage
4. Video metadata extraction
5. Frame extraction
6. Audio extraction
7. Speech-to-text
8. Visual content analysis
9. Text/audio analysis
10. Context analysis
11. Moderation scoring
12. Final moderation decision
13. Evidence generation
14. Explainable report generation
15. Database persistence
16. Processing status tracking
17. Error handling
18. Logging

---

# 4. Technology Stack

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* PostgreSQL

## Video Processing

* OpenCV
* FFmpeg

## Machine Learning

* PyTorch
* YOLO or another suitable computer-vision model
* Whisper or another suitable speech-to-text model
* Transformer-based NLP model
* Vision-Language Model for contextual analysis
* LLM for structured explanations

## Infrastructure

* Docker
* Docker Compose

A background task/worker system should be introduced when processing becomes computationally expensive.

Possible technologies:

* Redis
* Celery

The final choice should be made during architecture design rather than assumed immediately.

---

# 5. Design Principles

The backend should follow these principles:

### Modular

Video processing, vision, transcription, text moderation, context analysis, moderation logic, and report generation must be separated.

### Model Agnostic

AI models should be replaceable without rewriting the rest of the application.

### Explainable

Every moderation decision should be traceable to evidence.

### Context Aware

The system should not make final decisions from a single frame, object, or keyword whenever additional context is available.

### Testable

Each major service should be independently testable.

### Configurable

Thresholds, model settings, storage paths, and external API configuration should not be hardcoded.

### Secure

Secrets must never be committed to the repository.

### Production Oriented

Use proper error handling, logging, validation, configuration management, and clean separation of concerns.

---

# 6. Initial Architecture

The backend should approximately follow this structure:

```text
backend/
│
├── app/
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── videos.py
│   │       ├── moderation.py
│   │       └── health.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   └── models/
│   │
│   ├── schemas/
│   │   ├── video.py
│   │   ├── moderation.py
│   │   └── report.py
│   │
│   ├── services/
│   │   ├── video/
│   │   ├── audio/
│   │   ├── vision/
│   │   ├── transcription/
│   │   ├── text_moderation/
│   │   ├── context/
│   │   ├── moderation/
│   │   └── reporting/
│   │
│   ├── workers/
│   │   └── moderation_worker.py
│   │
│   └── main.py
│
├── tests/
│
├── models/
│
├── storage/
│
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

This is the initial target structure. It may be refined during implementation if there is a strong architectural reason.

---

# 7. Video Upload

The backend should provide:

```text
POST /api/v1/videos
```

The endpoint should:

1. Accept a video file.
2. Validate the file extension.
3. Validate the MIME type.
4. Validate file size.
5. Generate a unique video ID.
6. Store the video.
7. Extract basic metadata.
8. Create a database record.
9. Queue processing.
10. Return the video ID and processing status.

Example response:

```json
{
  "video_id": "vid_00123",
  "status": "UPLOADED"
}
```

The upload request should not wait for the complete AI moderation pipeline.

---

# 8. Video Validation

The backend should initially support:

* MP4
* MOV
* AVI
* MKV

Initial limits:

* Maximum file size: 500 MB
* Maximum duration: 30 minutes

These limits should be configurable.

Invalid uploads should receive appropriate HTTP errors.

---

# 9. Video Metadata

Extract and store:

* Filename
* File size
* Duration
* Width
* Height
* FPS
* Codec
* Audio availability
* Frame count

Metadata extraction should be implemented as a reusable service.

---

# 10. Processing States

A video should move through explicit processing states:

```text
UPLOADED
    ↓
QUEUED
    ↓
PROCESSING
    ↓
ANALYZING
    ↓
COMPLETED
```

Failure state:

```text
FAILED
```

The state must be persisted in PostgreSQL.

---

# 11. Video Processing Pipeline

The intended backend pipeline is:

```text
Video Upload
     ↓
Validation
     ↓
Metadata Extraction
     ↓
Frame Extraction
     ↓
Audio Extraction
     ↓
 ┌───────────────┬────────────────┐
 │               │                │
 ▼               ▼                ▼
Vision        Speech-to-Text   Metadata
Analysis           │
 │                 ▼
 │            Text Analysis
 │                 │
 └──────────┬──────┘
            ▼
      Context Analysis
            ↓
     Moderation Engine
            ↓
       Risk Scoring
            ↓
     Evidence Generation
            ↓
      Report Generation
            ↓
         Database
```

---

# 12. Frame Extraction

The video-processing service should:

* Open the uploaded video.
* Extract frames.
* Preserve timestamps.
* Store metadata for selected frames.
* Support configurable sampling.

Initial implementation may use FPS-based sampling.

Future implementations may support:

* Scene-change detection
* Adaptive sampling
* Temporal windows

Example frame record:

```json
{
  "frame_id": "frame_0042",
  "timestamp": 42.3,
  "path": "storage/evidence/frame_0042.jpg"
}
```

---

# 13. Visual Analysis

The visual-analysis service should accept video frames and return structured detections.

Potential categories:

* Violence
* Weapons
* Physical assault
* Dangerous behavior
* Child-safety concerns
* Graphic content
* Self-harm indicators

Each detection should contain:

* Category
* Confidence
* Timestamp
* Evidence reference
* Description

Example:

```json
{
  "category": "weapon",
  "confidence": 0.91,
  "timestamp": 42.3,
  "evidence": "frame_0042"
}
```

The visual-analysis service must **not** make the final moderation decision.

It only generates evidence/signals.

---

# 14. Audio Processing

The audio pipeline should:

1. Extract audio from the video.
2. Convert audio into the required model format.
3. Run speech-to-text.
4. Generate timestamped transcript segments.

Example:

```json
{
  "start": 42.1,
  "end": 44.8,
  "text": "Don't come any closer."
}
```

---

# 15. Text Moderation

The text-moderation service should analyze transcript segments.

Potential categories:

* Threats
* Harassment
* Violent intent
* Dangerous instructions
* Child-safety concerns
* Other policy violations

Each result should contain:

* Category
* Confidence
* Timestamp
* Transcript
* Evidence/reference

Like visual analysis, text moderation should generate signals rather than make the final decision.

---

# 16. Context Analysis

Context analysis is a core feature.

The context layer should combine:

* Nearby frames
* Visual detections
* Transcript
* Transcript timestamps
* Objects
* Actions
* Temporal information
* Other available evidence

The purpose is to understand the meaning of potentially problematic events.

Example:

```text
Visual:
Knife detected

Transcript:
"Today we're preparing vegetables."

Context:
Cooking tutorial

Interpretation:
Low risk
```

Another example:

```text
Visual:
Knife detected

Transcript:
"Don't come any closer."

Context:
Threatening interaction

Interpretation:
High risk
```

Context analysis should return structured output that can be consumed by the moderation engine.

---

# 17. Moderation Engine

The moderation engine combines evidence from:

* Vision
* Text/audio
* Context
* Temporal information

Example signals:

```text
weapon_detection = 0.91
threat_detection = 0.84
violent_context = 0.88
temporal_consistency = 0.81
```

The engine should determine:

### Decision

* APPROVED
* REVIEW_REQUIRED
* REJECTED

### Risk

* LOW
* MEDIUM
* HIGH
* CRITICAL

The scoring system must be configurable and should not be hardcoded into API routes.

---

# 18. Evidence

Every moderation finding should be traceable to evidence.

Evidence types may include:

* Frame
* Timestamp
* Transcript segment
* Visual detection
* Text detection
* Context result

Example:

```text
Finding:
Violence

Evidence:
00:42
Frame: frame_0042

Audio:
00:43 - 00:46
"Don't come any closer."

Context:
Threatening interaction

Confidence:
0.87
```

---

# 19. Moderation Report

The backend should generate a structured moderation report.

Example:

```json
{
  "video_id": "vid_00123",
  "decision": "REVIEW_REQUIRED",
  "risk_level": "HIGH",
  "findings": [
    {
      "category": "violence",
      "confidence": 0.87,
      "start_timestamp": 42.0,
      "end_timestamp": 48.0,
      "evidence": [
        "frame_0042",
        "transcript_0021"
      ],
      "explanation": "The visual and audio evidence indicate a threatening interaction."
    }
  ]
}
```

---

# 20. Database

Use PostgreSQL.

Initial entities:

## videos

```text
id
filename
storage_path
duration
file_size
width
height
fps
status
created_at
updated_at
```

## moderation_results

```text
id
video_id
decision
risk_level
overall_confidence
created_at
```

## detections

```text
id
moderation_result_id
category
confidence
start_timestamp
end_timestamp
explanation
```

## evidence

```text
id
detection_id
type
timestamp
storage_path
content
```

## transcript_segments

```text
id
video_id
start_timestamp
end_timestamp
text
```

Relationships should use proper foreign keys and SQLAlchemy relationships where appropriate.

---

# 21. API

Initial API:

```text
POST   /api/v1/videos
GET    /api/v1/videos/{video_id}
GET    /api/v1/videos/{video_id}/status
GET    /api/v1/videos/{video_id}/moderation
GET    /api/v1/videos/{video_id}/evidence
GET    /api/v1/health
```

Later endpoints may include:

```text
DELETE /api/v1/videos/{video_id}
POST   /api/v1/videos/{video_id}/retry
POST   /api/v1/videos/{video_id}/review
```

---

# 22. Error Handling

The backend should provide consistent handling for:

* Invalid files
* Unsupported formats
* Oversized files
* Missing videos
* Failed processing
* Model failures
* Database failures
* External API failures
* Invalid request data

Errors should be logged without exposing sensitive information.

---

# 23. Configuration

Use environment variables for:

* Database URL
* Storage location
* Model configuration
* API keys
* Processing limits
* Moderation thresholds
* Worker configuration

Never hardcode secrets.

Provide:

```text
.env.example
```

with placeholders only.

---

# 24. Logging

Use structured application logging.

Important events should include:

* Video upload
* Processing start
* Processing completion
* Processing failure
* Model inference failure
* Database failure
* Moderation completion

Logs should contain useful IDs such as:

* video_id
* processing/job ID
* error context

---

# 25. Testing

Implement:

## Unit Tests

* File validation
* Metadata extraction
* Frame extraction
* Audio extraction
* Transcription wrapper
* Vision wrapper
* Text moderation
* Context logic
* Risk scoring
* Report generation

## API Tests

* Valid upload
* Invalid upload
* Oversized file
* Missing video
* Status endpoint
* Moderation endpoint

## Integration Tests

Test the pipeline:

```text
Upload
  ↓
Processing
  ↓
Analysis
  ↓
Moderation
  ↓
Report
```

The project should be designed so expensive AI models can be mocked during automated tests.

---

# 26. Security Requirements

The backend should:

* Validate file extensions.
* Validate MIME types.
* Prevent path traversal.
* Generate safe server-side filenames.
* Limit file sizes.
* Never expose internal storage paths unnecessarily.
* Keep secrets outside source code.
* Validate API inputs.
* Avoid executing uploaded content.
* Restrict access to stored media when authentication is introduced.

---

# 27. MVP

The backend MVP must provide:

1. FastAPI application
2. PostgreSQL database
3. Video upload
4. Video validation
5. Metadata extraction
6. Frame extraction
7. Audio extraction
8. Speech-to-text
9. Basic visual analysis
10. Basic text moderation
11. Context analysis
12. Moderation engine
13. Risk scoring
14. Timestamped evidence
15. Explainable moderation report
16. Processing status API
17. Automated tests

The MVP does not require:

* React frontend
* YouTube API integration
* Live-stream moderation
* Large-scale distributed infrastructure
* Automatic removal of videos from YouTube
* Perfect moderation accuracy

---

# 28. Development Milestones

## Milestone 1 — Backend Foundation

Create:

* FastAPI application
* Configuration
* Logging
* PostgreSQL connection
* SQLAlchemy setup
* Pydantic schemas
* Testing setup
* Basic project structure

## Milestone 2 — Video Ingestion

Implement:

* Upload endpoint
* Validation
* Storage
* Metadata extraction
* Video database model
* Processing status

## Milestone 3 — Video Processing

Implement:

* Frame extraction
* Audio extraction
* Processing service

## Milestone 4 — AI Services

Implement:

* Vision model interface
* Speech-to-text interface
* Text moderation interface

## Milestone 5 — Context Engine

Implement:

* Evidence aggregation
* Temporal context
* Multimodal/context reasoning

## Milestone 6 — Moderation Engine

Implement:

* Risk scoring
* Decision logic
* Evidence association

## Milestone 7 — Reporting

Implement:

* Structured moderation report
* Explanations
* Timestamped evidence

## Milestone 8 — Testing & Evaluation

Implement:

* Unit tests
* Integration tests
* API tests
* ML evaluation
* Error handling improvements

---

# 29. Definition of Done

The backend will be considered functional when:

* A video can be uploaded through the API.
* The upload is validated and stored.
* Metadata is extracted.
* Processing occurs asynchronously or through a worker-compatible architecture.
* Frames and audio are extracted.
* Visual and audio information are analyzed.
* Context is considered.
* A moderation decision is produced.
* Risk and confidence are recorded.
* Evidence is linked to timestamps.
* A structured moderation report can be retrieved through the API.
* Errors are handled appropriately.
* Core functionality has automated tests.
* The application can run locally from documented setup instructions.

---

# 30. Important Architectural Constraint

Do not build the system as one large Python file or one large moderation function.

The following components should remain independently replaceable:

```text
Video Processing
       ↓
Vision Service
       ↓
Transcription Service
       ↓
Text Moderation Service
       ↓
Context Service
       ↓
Moderation Engine
       ↓
Report Generator
```

The API layer should orchestrate these components rather than contain their business logic.

---

# 31. Current Development Scope

For the current phase:

**BUILD ONLY THE BACKEND.**

Do not create:

* React
* HTML/CSS UI
* Frontend components
* Dashboard
* Frontend authentication
* UI-specific code

Focus entirely on the backend architecture, video-processing pipeline, AI moderation pipeline, database, APIs, testing, and documentation.

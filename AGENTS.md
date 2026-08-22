# AI Video Moderation Backend — Codex Instructions

## 1. Project Context

This repository contains the backend for an AI-powered video moderation platform.

The source of truth for project requirements is:

`PROJ_SPEC.md`

Read `PROJ_SPEC.md` before making architectural or implementation decisions.

The current development scope is **backend only**.

Do not create frontend code unless explicitly requested.

---

# 2. Development Philosophy

Build the project incrementally.

Do not attempt to implement the entire platform in one step.

For each milestone:

1. Inspect the existing code.
2. Understand the current architecture.
3. Propose the implementation approach.
4. Implement only the requested milestone.
5. Run relevant tests.
6. Fix issues caused by the implementation.
7. Report what changed.
8. Do not modify unrelated parts of the project.

Prefer simple, maintainable solutions over unnecessary complexity.

---

# 3. Architecture Rules

Use a modular architecture.

Keep these responsibilities separate:

```text
API Layer
    ↓
Service Layer
    ↓
Business Logic
    ↓
Data Access
    ↓
External Models / Services
```

Do not place business logic directly inside FastAPI route handlers.

Do not create a single large file containing the entire moderation pipeline.

The following components should remain independently replaceable:

* Video processing
* Frame extraction
* Audio extraction
* Speech-to-text
* Vision analysis
* Text moderation
* Context analysis
* Moderation engine
* Evidence generation
* Report generation
* Storage

---

# 4. Technology Rules

Primary backend language:

Python

Primary framework:

FastAPI

Database:

PostgreSQL

ORM:

SQLAlchemy

Validation:

Pydantic

Video processing:

OpenCV + FFmpeg

ML framework:

PyTorch

Containerization:

Docker

Use additional libraries only when they provide a clear benefit.

Do not add dependencies unnecessarily.

---

# 5. Python Rules

Use:

* Type hints
* Clear function and class names
* Small functions
* Descriptive variable names
* Docstrings for important public interfaces
* Consistent formatting

Avoid:

* Huge functions
* Global mutable state
* Hardcoded configuration
* Silent exception handling
* Dead code
* Unnecessary abstractions

Prefer explicit code over clever code.

---

# 6. Configuration

All environment-specific configuration must come from environment variables or configuration files.

Never hardcode:

* API keys
* Database credentials
* Secret keys
* Absolute machine-specific paths
* Production URLs

Maintain:

`.env.example`

Never commit:

`.env`

---

# 7. Database Rules

Use SQLAlchemy for database access.

Use migrations when the project reaches a stage where schema evolution requires them.

Database models should represent persistent data only.

Do not put complex business logic inside SQLAlchemy models.

Use proper:

* Primary keys
* Foreign keys
* Constraints
* Relationships
* Indexes where appropriate

---

# 8. API Rules

Use versioned API routes:

`/api/v1/...`

Use appropriate HTTP status codes.

Validate incoming requests with Pydantic.

Keep route handlers thin.

For example:

```text
Route
  ↓
Validate request
  ↓
Call service
  ↓
Return response
```

Do not put model inference, video processing, or database-heavy business logic directly inside route handlers.

Use consistent response and error structures.

---

# 9. Video Processing Rules

Uploaded videos are untrusted input.

Always validate:

* File type
* MIME type
* File size
* Duration
* Storage path

Never trust the original filename as a storage filename.

Generate safe server-side filenames/IDs.

Do not execute arbitrary uploaded files.

Preserve timestamps whenever extracting frames, audio, or other evidence.

---

# 10. AI/ML Architecture Rules

AI models must be accessed through service interfaces.

Do not tightly couple the application to one model implementation.

For example:

```text
VisionService
    ↓
VisionModelInterface
    ↓
YOLO / VLM / Future Model
```

A model should be replaceable without rewriting API routes or moderation logic.

The same principle applies to:

* Speech-to-text
* Text moderation
* Context analysis
* LLM explanation generation

---

# 11. Moderation Rules

The moderation system should distinguish between:

### Evidence

What a model detects.

Examples:

* Knife detected
* Threatening phrase detected
* Person detected
* Physical contact detected

### Interpretation

What the combined evidence may mean.

Example:

* Threatening interaction
* Cooking demonstration
* Educational content

### Final Decision

The platform-level moderation outcome:

* APPROVED
* REVIEW_REQUIRED
* REJECTED

Do not automatically treat a single object, keyword, or frame as a final policy violation.

Context should be considered whenever available.

---

# 12. Explainability Rules

Every important moderation finding should be traceable to evidence.

Evidence may include:

* Frame
* Timestamp
* Transcript segment
* Model detection
* Context result

A final moderation result should make it possible to answer:

> Why was this video flagged?

Do not generate explanations that contradict the underlying evidence.

Do not use an LLM to invent evidence.

LLMs may summarize or explain existing evidence, but they must not fabricate detections.

---

# 13. Confidence and Risk

Keep model confidence and moderation risk conceptually separate.

Example:

```text
Model confidence:
0.91

Risk level:
HIGH
```

Do not assume:

`confidence = risk`

The moderation engine should combine multiple signals when determining risk.

Moderation thresholds should be configurable.

---

# 14. Background Processing

Video analysis can be computationally expensive.

Do not design the upload endpoint so it waits for the complete moderation pipeline.

Prefer:

```text
Upload
  ↓
Store video
  ↓
Create processing job
  ↓
Return response
  ↓
Background processing
```

The architecture should remain compatible with a worker system such as Celery + Redis.

Do not introduce a distributed system prematurely if the current milestone does not require it.

---

# 15. Error Handling

Handle errors explicitly.

Expected failures include:

* Invalid video
* Unsupported format
* File too large
* Corrupt video
* Audio extraction failure
* Model inference failure
* Database failure
* External API failure

Do not silently swallow exceptions.

Errors should be logged with useful context such as:

* video_id
* job_id
* service/component
* error type

Do not expose internal stack traces or secrets through API responses.

---

# 16. Logging

Use structured, useful logging.

Important events include:

* Upload started
* Upload completed
* Processing started
* Processing completed
* Processing failed
* Model inference started/completed
* Moderation completed

Avoid excessive debug logging in production code.

---

# 17. Testing Rules

Every significant service should have unit tests.

Use mocks for expensive AI models during regular automated tests.

Tests should cover:

* Normal behavior
* Invalid input
* Failure cases
* Edge cases

Add integration tests as the pipeline becomes functional.

Do not modify tests simply to make failing code appear correct.

When a test fails:

1. Determine whether the implementation is wrong.
2. Determine whether the test is wrong.
3. Fix the actual problem.

---

# 18. Security Rules

Never commit secrets.

Validate all user-controlled input.

Prevent:

* Path traversal
* Unsafe filenames
* Oversized uploads
* Unsupported file types
* Arbitrary file execution

Do not expose internal filesystem paths unnecessarily.

Treat all uploaded videos as untrusted data.

---

# 19. Git Rules

Make small, logical commits.

Preferred commit examples:

```text
Initialize FastAPI backend
Add PostgreSQL configuration
Implement video upload
Add video metadata extraction
Implement frame extraction
Add transcription service
Implement moderation engine
Add moderation report generation
```

Do not make giant commits containing unrelated features.

Before committing, inspect:

```text
git status
git diff
```

---

# 20. Dependency Rules

Before adding a dependency:

1. Check whether the project already has a suitable library.
2. Prefer established, maintained libraries.
3. Avoid adding multiple libraries for the same responsibility.
4. Update dependency files appropriately.

---

# 21. Documentation Rules

Document important architectural decisions.

Keep:

`README.md`

updated with:

* Setup
* Environment configuration
* Running locally
* Running tests
* API usage
* Project structure

Do not create unnecessary documentation for trivial implementation details.

---

# 22. Code Change Rules

When asked to implement a feature:

### Before coding

Inspect:

* Existing structure
* Related files
* Existing interfaces
* Existing tests
* Configuration

### While coding

* Reuse existing architecture.
* Avoid unrelated refactoring.
* Keep changes focused.
* Add tests where appropriate.

### After coding

* Run relevant tests.
* Check for obvious errors.
* Review changed files.
* Explain important implementation decisions.

---

# 23. Scope Control

Current scope:

**BACKEND ONLY**

Do not create:

* React
* Next.js
* HTML UI
* CSS
* Dashboard components
* Frontend state management

unless explicitly instructed.

Focus on:

* FastAPI
* PostgreSQL
* Video processing
* AI/ML services
* Moderation logic
* Evidence
* Reports
* Testing
* Backend documentation

---

# 24. Implementation Order

Prefer the following order unless there is a strong reason to change it:

```text
1. Backend foundation
2. Configuration
3. Database
4. Video upload
5. Video validation
6. Metadata extraction
7. Video/frame processing
8. Audio extraction
9. Speech-to-text
10. Vision service
11. Text moderation
12. Context analysis
13. Moderation engine
14. Evidence handling
15. Report generation
16. API integration
17. Testing
18. Evaluation
```

Do not implement later stages before the architecture required by earlier stages is stable.

---

# 25. Important Rule

Do not guess requirements that are already defined in `PROJ_SPEC.md`.

If an implementation detail is unspecified:

1. Prefer the simplest production-appropriate solution.
2. Preserve modularity.
3. Avoid irreversible architectural decisions.
4. Clearly document significant assumptions.

The goal is to build a backend that is understandable, testable, extensible, and suitable for an academic capstone/portfolio project.

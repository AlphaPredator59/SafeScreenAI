# SafeScreen AI — Frontend Application

Modern React + TypeScript + Vite web interface for **SafeScreen**, an AI-powered video moderation and trust-and-safety platform.

---

## 1. Quick Start

### Prerequisites
- **Node.js**: v18+ (tested on Node v24)
- **SafeScreen Backend**: Running on `http://127.0.0.1:8000`

### Installation
From the repository root or inside `frontend/`:

```bash
cd frontend
npm install
```

### Running Development Server
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

Vite is configured with a reverse proxy that directs all `/api` requests to `http://127.0.0.1:8000`, eliminating browser CORS issues without modifying backend code.

### Building for Production
```bash
npm run build
```

---

## 2. Architecture & Design Principles

SafeScreen frontend is built with high-information-density UI inspired by professional trust-and-safety SaaS platforms.

### Tech Stack
- **Framework**: React 19 + TypeScript
- **Bundler & Tooling**: Vite
- **Styling**: Tailwind CSS with custom design tokens and `@layer base` CSS variables
- **Icons**: Lucide React
- **Routing**: React Router DOM v7

### Directory Structure

```text
frontend/src/
├── components/
│   ├── common/         # Badge, Button, Card, EmptyState, ErrorAlert, Modal, StatCard, LoadingSkeleton
│   ├── layout/         # Navbar (brand, session counter, theme toggle), Footer (live health indicator), PageContainer
│   ├── moderation/     # DecisionBanner, RiskOverview, FindingsList, EvidenceGallery
│   ├── processing/     # StatusCard (live backend polling), PipelineOverview (conceptual architecture)
│   ├── report/         # ReportHeader (print & export), ExecutiveSummary, FindingsMatrix, TranscriptsView
│   ├── session/        # SessionVideoCard, SessionMetricsGrid
│   ├── upload/         # Dropzone (format/size validation), FilePreview (local video preview)
│   └── video/          # VideoPlayer (in-memory Blob URL / honest fallback), ModerationTimeline
├── hooks/
│   ├── useTheme.ts             # Global Light/Dark mode state
│   ├── useSessionVideos.ts     # Current-session videos & aggregated metrics
│   ├── useVideoStatus.ts       # Polling hook for /videos/{id}/status
│   └── useModerationReport.ts  # Full report & evidence fetching
├── pages/
│   ├── DashboardPage.tsx       # Welcome CTA, session metrics, recent uploads
│   ├── UploadPage.tsx          # Drag & drop upload workflow
│   ├── ProcessingPage.tsx      # Real-time lifecycle polling & conceptual pipeline
│   ├── VideoDetailPage.tsx     # Moderation workspace (player, timeline, findings, evidence)
│   ├── SessionVideosPage.tsx   # Filterable & searchable session video registry
│   ├── ReportPage.tsx          # Dedicated print-ready explainable report
│   └── NotFoundPage.tsx        # 404 handler
├── services/api/
│   ├── client.ts       # Typed fetch client with SafeScreenApiError
│   ├── health.ts       # GET /health
│   ├── videos.ts       # POST /videos, GET /videos/{id}, GET /videos/{id}/status
│   └── moderation.ts   # GET /videos/{id}/moderation, GET /videos/{id}/evidence
├── store/
│   ├── themeContext.tsx        # Dark/Light mode provider with localStorage & system preference
│   └── sessionContext.tsx      # Client-side session visibility & in-memory Blob URL registry
└── types/
    ├── api.ts          # 100% verified backend Pydantic schemas & controlled enums
    ├── session.ts      # Client-side session record types
    └── theme.ts        # Theme types
```

---

## 3. Backend Constraints & Integration Model

The frontend treats the FastAPI backend as **read-only infrastructure**. The following constraints are strictly respected:

1. **Client-Side Session Visibility (No Auth/Authorization)**:
   - The MVP backend does not provide user authentication, login tokens, or server-side tenant isolation.
   - `sessionStorage` provides **client-side session visibility filtering only**. Videos uploaded during the active browser tab session are tracked in local session state.
   - Closing the browser tab or clicking **Reset Session** purges the local session records.

2. **Honest Video Playback (Zero Fabricated Streaming)**:
   - The backend stores videos on disk without exposing a public streaming endpoint.
   - For newly uploaded videos in an active session, the frontend utilizes an in-memory `URL.createObjectURL(file)` to provide zero-latency local playback, scrub controls, and synchronized timeline seeking.
   - If the page is reloaded or the video link is opened directly, the player displays an **honest video specification card** (dimensions, fps, duration, file size) with a notice that backend streaming is not supported. The interactive timeline, evidence items, and timestamps remain fully active.

3. **Status Polling vs. Conceptual Pipeline**:
   - `GET /api/v1/videos/{video_id}/status` returns only `{ video_id: string, status: VideoStatus }`.
   - The status card reflects strictly the verified backend status enum (`UPLOADED`, `QUEUED`, `PROCESSING`, `ANALYZING`, `COMPLETED`, `FAILED`).
   - The 6-stage pipeline (Frame Extraction, YOLO, Whisper, Toxic-BERT, Qwen 2.5-VL, ModerationEngine) is presented as an **educational architectural overview**, with zero fake stage checkmarks or percentages.

4. **100% Verified API Schemas**:
   - Every interface in `src/types/api.ts` directly matches the backend Pydantic schemas in `backend/app/schemas/`.
   - Zero fields have been assumed or invented.

---

## 4. Light & Dark Themes

- **Toggle**: Globally accessible in the header on all screens.
- **Persistence**: Saved to `localStorage('safescreen_theme_preference')`.
- **System Preference**: Automatically detects `prefers-color-scheme: dark` on first load.
- **Accessibility**: Includes high-contrast text ratios, distinct non-color status badges, and keyboard navigation.

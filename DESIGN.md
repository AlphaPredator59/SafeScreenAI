# SafeScreen Frontend — Build From Scratch

You are working on an existing full-stack project called **SafeScreen**, an AI-powered video moderation platform.

The repository already contains the backend.

The **`frontend/` directory is currently EMPTY**.

Your task is to build the complete SafeScreen frontend from scratch inside:

```text
frontend/
```

Use the available **Stitch MCP** to design and implement the UI.

---

# 🚨 ABSOLUTE RULE: DO NOT BREAK THE BACKEND

The existing backend is already implemented and is the source of truth.

Everything outside `frontend/` must be treated as protected unless a change is explicitly proven necessary.

### DO NOT modify:

- Backend Python code
- FastAPI routes
- API endpoints
- HTTP methods
- Request schemas
- Response schemas
- Database models
- Database migrations
- PostgreSQL configuration
- AI/ML models
- Video processing pipeline
- Moderation pipeline
- Report generation logic
- Authentication/session logic
- Backend dependencies
- Backend environment variables
- Docker backend configuration

### DO NOT:

- Rewrite the backend.
- Create a second backend.
- Create mock backend APIs.
- Replace existing APIs.
- Rename existing endpoints.
- Change backend response structures just to make frontend development easier.

### YOU MAY:

- Create everything required inside `frontend/`.
- Install frontend dependencies.
- Create React/TypeScript components.
- Create frontend routes.
- Create frontend API services.
- Create frontend hooks.
- Create frontend state management.
- Create frontend styling.
- Create frontend types based on actual backend schemas.
- Create a frontend `.env` or `.env.example` if required.

If the frontend requires information that the backend does not currently expose:

**Do not modify the backend automatically.**

First identify the missing capability and report it.

---

# 1. FIRST STEP — INSPECT THE BACKEND

Before creating the frontend, inspect the existing repository.

Understand:

- Backend framework
- FastAPI application structure
- API routes
- Request models
- Response models
- Authentication
- Session mechanism
- Video upload endpoint
- Video processing endpoint/status
- Moderation result endpoint
- Evidence endpoint
- Report endpoint
- Existing CORS configuration
- Backend URL/port
- Docker configuration

Look for:

```text
backend/
app/
api/
routers/
routes/
schemas/
models/
services/
requirements.txt
pyproject.toml
docker-compose.yml
.env
.env.example
README.md
```

Do not guess the API.

The actual backend implementation is the source of truth.

---

# 2. CREATE THE FRONTEND FROM SCRATCH

Because `frontend/` is empty, create a professional frontend application inside it.

Preferred stack:

```text
React
TypeScript
Vite
Tailwind CSS
```

Use a modern frontend architecture.

Recommended:

```text
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── common/
│   │   ├── layout/
│   │   ├── upload/
│   │   ├── processing/
│   │   ├── video/
│   │   ├── moderation/
│   │   └── report/
│   │
│   ├── pages/
│   ├── hooks/
│   ├── services/
│   │   └── api/
│   ├── types/
│   ├── utils/
│   ├── styles/
│   ├── App.tsx
│   └── main.tsx
│
├── .env.example
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

Adapt the structure if a better architecture is appropriate.

Do not over-engineer the application.

---

# 3. STITCH MCP

Use Stitch MCP to create a cohesive visual system for SafeScreen.

The design must feel like:

**Professional AI Trust & Safety SaaS**

Visual characteristics:

- Modern
- Minimal
- Technical
- Premium
- Clean
- Evidence-focused
- High information clarity
- Professional
- Accessible
- Responsive

Avoid:

- Generic admin dashboard
- Excessive gradients
- Neon cyberpunk styling
- Excessive glassmorphism
- Cartoon UI
- Excessive rounded cards
- Unnecessary animations
- Fake analytics

The final UI should look like a product that could realistically be used by a content moderation team.

---

# 4. SAFE SCREEN BRAND

Product name:

**SafeScreen**

Brand concept:

```text
AI + Video + Safety + Trust
```

Create a simple logo concept combining:

- Video/screen
- Shield/safety
- AI/technology

Keep the branding professional and minimal.

---

# 5. GLOBAL APPLICATION STRUCTURE

The application should contain:

```text
Dashboard
Upload Video
Processing
Moderation Result
Video Detail
Evidence
Report
Session Videos
Settings
```

Primary navigation:

```text
SafeScreen

Dashboard
Session Videos
Upload Video
```

Header right side:

```text
Theme Toggle
Session Indicator
User/Profile if applicable
```

---

# 6. GLOBAL LIGHT / DARK MODE

This is a REQUIRED feature.

The application must support:

**Light Mode**

and

**Dark Mode**

Add a clearly visible toggle to the global header.

Example:

```text
┌───────────────────────────────────────────────────────────┐
│ SafeScreen   Dashboard   Session Videos   Upload    ☀ / ☾ │
└───────────────────────────────────────────────────────────┘
```

Use:

- ☀ Sun → Light mode
- ☾ Moon → Dark mode

The toggle must:

- Work from every major screen.
- Switch instantly.
- Persist while navigating.
- Persist according to frontend storage.
- Respect system preference on first visit if no preference exists.
- Be keyboard accessible.
- Have an accessible label.

---

## Light Theme

Use:

- Light neutral background
- White/near-white surfaces
- Dark primary text
- Muted secondary text
- Subtle borders
- Restrained accent color

## Dark Theme

Do NOT simply invert colors.

Use:

- Deep neutral background
- Slightly lighter surfaces
- Elevated cards
- High contrast text
- Muted secondary text
- Subtle borders
- Controlled accent colors

Use centralized design tokens/CSS variables:

```text
--background
--surface
--surface-elevated
--border
--text-primary
--text-secondary
--accent
--success
--warning
--danger
```

---

# 7. DASHBOARD

Create:

### Analyze your video before you publish.

Supporting text:

> Upload a video and SafeScreen will analyze it for potential policy violations and generate an explainable moderation report.

Primary CTA:

**Upload Video**

---

## Session Metrics

Display:

- Videos in Session
- Completed Analyses
- Review Required
- Violations Detected

IMPORTANT:

These values must come from actual backend/session data.

Do not fabricate numbers.

---

## Recent Session Videos

Display current-session uploads.

Each card:

- Thumbnail
- Filename
- Duration
- Upload time
- Moderation status
- Violation count
- View Report

---

# 8. UPLOAD PAGE

Create a large drag-and-drop upload interface.

Display:

```text
Drop your video here

or browse files from your device
```

Features:

- Drag & drop
- Browse
- File validation
- File preview
- Upload progress
- Retry
- Cancel if supported

Primary CTA:

**Analyze Video**

Use actual backend-supported:

- Formats
- File size limits

Do not invent them.

---

# 9. PROCESSING PAGE

Display:

- Video thumbnail
- Filename
- Duration
- Resolution
- Processing state

Show the conceptual pipeline:

```text
Upload
   ↓
Frame Extraction
   ↓
Object / Action Detection
   ↓
Policy Analysis
   ↓
Context Analysis
   ↓
Report Generation
```

States:

- Pending
- Processing
- Completed
- Failed

IMPORTANT:

Do not fake progress.

If the backend exposes real progress, show it.

If not, show stage-based progress.

Do not pretend to know a frame number if the backend does not provide one.

---

# 10. MODERATION RESULT

Display the actual backend moderation result.

Possible UI states:

```text
SAFE
REVIEW REQUIRED
VIOLATION DETECTED
ANALYSIS FAILED
```

If the backend uses different values, map them in the frontend.

Never change backend values.

Each result must include:

- Status text
- Icon
- Visual status indicator
- Explanation where available

Never communicate status through color alone.

---

# 11. MODERATION SUMMARY

Show actual available data:

- Overall Risk
- Violations Detected
- Highest Confidence
- Frames Flagged
- Processing Time

If a field does not exist in the backend response:

**Do not fabricate it.**

---

# 12. POLICY VIOLATIONS

Render violations dynamically.

Possible categories:

- Violence
- Weapons
- Graphic Content
- Dangerous Activities
- Harassment
- Sexual Content
- Drugs
- Self-Harm
- Other

Do not assume all categories exist.

Each violation should display when available:

```text
Category
Severity
Confidence
Timestamp
Evidence
Explanation
Recommendation
```

---

# 13. VIDEO PLAYER

Create a professional video player.

Controls:

- Play
- Pause
- Seek
- Timestamp
- Duration
- Volume
- Fullscreen

Use the actual backend video.

Do not duplicate or unnecessarily download videos.

---

# 14. MODERATION TIMELINE

This is a key SafeScreen feature.

Create an interactive timeline below the video.

Example:

```text
0:00 ───────●────────────●──────────── 5:42
             ↑            ↑
          Event 1      Event 2
```

Timeline markers must come from actual backend moderation events.

When the user clicks a marker:

1. Seek video to timestamp.
2. Select corresponding event.
3. Display evidence.
4. Display explanation.
5. Highlight selected event.

Do not create fake events.

---

# 15. EVIDENCE FRAME GALLERY

Display evidence frames from the backend.

Each card:

- Frame
- Timestamp
- Category
- Confidence
- Severity

Clicking a frame:

- Enlarges/open preview
- Seeks video to timestamp
- Displays explanation
- Highlights corresponding event

Do not expose backend filesystem paths.

---

# 16. EXPLAINABLE REPORT

Create a dedicated:

# Moderation Report

Show:

- Filename
- Duration
- Resolution
- Analysis time
- Processing time

---

## Executive Summary

Render the actual backend-generated summary.

Do not fabricate AI explanations in the frontend.

---

## Violation Details

Each violation:

```text
Policy
Severity
Confidence
Timestamp
Evidence
Explanation
Recommendation
```

The report should clearly answer:

```text
What happened?
When did it happen?
Why was it flagged?
How confident is the system?
What should happen next?
```

---

# 17. SESSION VIDEOS

Create:

# Session Videos

Supporting text:

> Videos uploaded during your current session.

## 🚨 CRITICAL REQUIREMENT

Users can ONLY see videos uploaded during their **CURRENT SESSION**.

Never expose:

- Previous-session videos
- Other users' videos
- Global video history

This is a security/backend requirement, not just a UI requirement.

Use the existing backend session mechanism.

Do not create a new session system.

Do not retrieve a global video list and filter it only in the frontend.

---

## Video Cards

Display:

- Thumbnail
- Filename
- Duration
- Upload time
- Moderation status
- Violation count
- View Report

Optional:

- Search
- Status filter
- Sort by upload time

Only implement these if compatible with the existing backend.

---

# 18. VIDEO DETAIL PAGE

Create a complete moderation workspace.

Recommended:

```text
┌────────────────────────────────────────────────────────────┐
│ Video Name                              Status              │
├──────────────────────────────────┬─────────────────────────┤
│                                  │ Moderation Summary      │
│                                  │                         │
│          Video Player            │ Risk                    │
│                                  │ Violations              │
│                                  │ Confidence              │
├──────────────────────────────────┴─────────────────────────┤
│ Moderation Timeline                                          │
├────────────────────────────────────────────────────────────┤
│ Violations                                                   │
├────────────────────────────────────────────────────────────┤
│ Evidence                                                     │
├────────────────────────────────────────────────────────────┤
│ Explainable Report                                           │
└────────────────────────────────────────────────────────────┘
```

Tabs:

- Overview
- Timeline
- Violations
- Evidence
- Report

---

# 19. EMPTY STATES

Create polished empty states.

Example:

```text
No videos yet

Upload your first video to start an AI-powered
moderation analysis.

[ Upload Video ]
```

Also:

- No violations
- No evidence
- No session videos
- No completed analyses

---

# 20. ERROR STATES

Upload:

> Something went wrong while uploading your video.

Actions:

**Retry**

**Choose Another Video**

Analysis:

> SafeScreen couldn't complete the analysis.

Actions:

**Retry Analysis**

**Session Videos**

Report:

> The moderation report could not be loaded.

Action:

**Retry**

Never expose raw:

- Stack traces
- Database errors
- Internal paths
- Backend exceptions

---

# 21. LOADING STATES

Use:

- Skeletons
- Progress bars
- Stage indicators
- Disabled actions

Avoid unexplained spinners.

---

# 22. RESPONSIVE DESIGN

Desktop is the primary target.

Support:

- Desktop
- Laptop
- Tablet
- Mobile

Desktop:

- Large video player
- Two-column analysis
- Evidence grid
- Timeline

Mobile:

- Single column
- Compact navigation
- Stacked moderation information
- Scrollable timeline
- Full-width video
- Collapsible report sections

---

# 23. ACCESSIBILITY

Implement:

- Semantic HTML
- Keyboard navigation
- Focus states
- Accessible labels
- Good contrast
- Non-color status indicators
- Keyboard-accessible important controls
- Accessible modal dialogs
- Accessible theme toggle

---

# 24. API ARCHITECTURE

Do not scatter API requests through components.

Use:

```text
UI
 ↓
Hooks / State
 ↓
API Services
 ↓
Existing Backend
```

Recommended:

```text
src/services/api/
├── client.ts
├── videos.ts
├── moderation.ts
└── reports.ts
```

Only implement services for actual backend APIs.

---

# 25. TYPE SAFETY

Use TypeScript.

Create frontend types based on the actual backend schemas.

Never invent API fields.

Handle:

- null
- undefined
- optional fields
- errors

correctly.

---

# 26. NO FAKE DATA

Never hard-code production moderation data.

Do not fabricate:

- Videos
- Risk scores
- Confidence
- Violations
- Evidence timestamps
- Reports
- Processing results

The production UI must use real backend data.

---

# 27. SECURITY

Never expose:

- Backend secrets
- Database credentials
- AI credentials
- Private storage credentials
- Internal filesystem paths

Frontend environment variables must contain only browser-safe values.

---

# 28. PERFORMANCE

Optimize sensibly.

- Lazy-load heavy UI.
- Use evidence thumbnails.
- Avoid unnecessary video downloads.
- Avoid excessive polling.
- Clean up timers/subscriptions.
- Avoid unnecessary re-renders.

Do not over-engineer.

---

# 29. ROUTING

Create appropriate frontend routes.

Recommended:

```text
/dashboard
/upload
/processing/:videoId
/videos
/videos/:videoId
/videos/:videoId/report
/settings
```

Use React Router or the routing system appropriate for the chosen stack.

---

# 30. FRONTEND README

Create:

```text
frontend/README.md
```

Document:

- How to install
- How to run
- Environment variables
- Backend API URL
- Build command
- Development command

Do not document fake APIs.

---

# 31. CORS

Before changing anything related to CORS:

1. Inspect existing backend CORS configuration.
2. Run the frontend against the backend.
3. Determine whether CORS actually fails.

Only if required should a minimal backend CORS adjustment be proposed.

Do not modify backend CORS automatically.

---

# 32. TEST THE APPLICATION

After implementation, test:

## Upload

```text
Dashboard
→ Upload
→ Select video
→ Upload
```

Verify the existing backend receives the video.

## Processing

```text
Upload
→ Processing
```

Verify the UI reflects actual backend state.

## Moderation

```text
Processing
→ Completed
```

Verify actual moderation data appears.

## Evidence

Click an actual moderation event.

Verify:

```text
Timeline
→ Video seeks
→ Evidence changes
→ Explanation changes
```

## Report

Click:

**View Report**

Verify actual backend-generated report appears.

## Session

Upload multiple videos.

Verify all current-session videos appear.

Start a new session according to the existing application mechanism.

Verify previous-session videos are not shown.

## Theme

Test:

```text
Light
↓
Dark
↓
Light
```

Verify every screen updates correctly.

---

# 33. FINAL ACCEPTANCE CHECKLIST

Before finishing:

- [ ] Frontend exists entirely inside `frontend/`.
- [ ] Backend was not rewritten.
- [ ] Backend API routes were not changed.
- [ ] Database was not changed.
- [ ] AI pipeline was not changed.
- [ ] Existing backend still runs.
- [ ] Upload works.
- [ ] Processing works.
- [ ] Moderation results work.
- [ ] Video player works.
- [ ] Moderation timeline works.
- [ ] Evidence works.
- [ ] Explainable report works.
- [ ] Session videos work.
- [ ] Previous-session videos are not exposed.
- [ ] Light mode works.
- [ ] Dark mode works.
- [ ] Theme toggle is globally accessible.
- [ ] Theme persists during navigation.
- [ ] Loading states exist.
- [ ] Error states exist.
- [ ] Empty states exist.
- [ ] Responsive design works.
- [ ] Accessibility basics work.
- [ ] No fake production data remains.
- [ ] Frontend uses actual backend APIs.

---

# 34. ENGINEERING PRIORITY

Always prioritize:

```text
1. Backend Safety
2. Correct API Integration
3. Data Correctness
4. Clean Architecture
5. User Experience
6. Visual Polish
```

If visual convenience conflicts with backend correctness:

**Backend correctness wins.**

If an API is unclear:

**Inspect the backend. Do not guess.**

If a feature requires a backend modification:

**Stop and report the exact requirement rather than changing the backend.**

---

# FINAL COMMAND

Build the SafeScreen frontend from scratch inside the empty `frontend/` directory.

Use Stitch MCP for the visual design.

Connect the frontend to the **existing backend APIs**.

Make the application production-quality, responsive, accessible, and professional.

Implement the complete:

```text
Dashboard
→ Upload
→ Processing
→ Moderation
→ Evidence
→ Report
→ Session Videos
```

workflow.

Include a polished global **Light/Dark Mode toggle**.

Most importantly:

# DO NOT BREAK THE EXISTING BACKEND.

**Inspect first. Build second. Integrate third. Test fourth.**
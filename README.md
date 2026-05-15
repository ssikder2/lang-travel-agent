# Wayfarer: AI Travel Planning Agent

Wayfarer is a full-stack AI travel assistant that helps users plan trips end-to-end in one chat flow: flights, hotels, itinerary, transportation, budget, packing, and travel advisories.

Live demo: [https://lang-travel-agent-git-main-ssikder2s-projects.vercel.app](https://lang-travel-agent-git-main-ssikder2s-projects.vercel.app)

## What This Project Does

- Runs a LangGraph + OpenAI travel agent with tool-calling guardrails
- Streams backend events to a modern Next.js chat UI with quick-reply chips
- Persists trip context per session so the assistant remembers confirmed details
- Shows structured flight/hotel result cards alongside the chat
- Keeps a manual "Trip Snapshot" panel in sync with agent memory

## Why It Was Built This Way

- **Reliable tool use over generic chat**: The system prompt and tool contracts strongly gate when flight/hotel APIs are called, reducing hallucinated searches and bad date/origin assumptions.
- **Stateful planning experience**: A profile store keeps confirmed fields (destination, dates, departure city, style, etc.) so users are not asked the same questions repeatedly.
- **UI + agent co-design**: The backend emits semantic events (tool activity, profile updates, cards, final reply), making the interface feel responsive and transparent.
- **Production-friendly defaults**: CORS supports localhost and Vercel preview/prod domains, and persistence has safe fallbacks if SQLite checkpoint packages are unavailable.

## Core Features

- Flight search through Booking RapidAPI with:
  - strict IATA/date validation
  - one-way vs round-trip gating from saved profile state
  - duplicate-offer collapse and best-offer scoring
- Hotel search through Booking RapidAPI with:
  - date validation
  - quality filters (pricing required, minimum class)
  - normalized result cards for UI rendering
- Prompt-layer controls for:
  - one-question-at-a-time chat behavior
  - profile-first continuity
  - mandatory quick-reply metadata (`[WAYFARER_UI:...]`)
- UI hint system:
  - parses authoritative UI JSON from assistant output
  - fallback extractor model for chips/placeholders
  - repair logic for yes/no mismatch and natural date chips
- Session-scoped memory and reset endpoint
- Save/restore friendly profile persistence via `.wayfarer_profiles.json`

## Architecture Overview

### Backend (Python / FastAPI / LangGraph)

- `main.py`: defines system prompt, tools, and LangGraph ReAct agent
- `server.py`: FastAPI app with streaming chat endpoint and UI event orchestration
- `tools/`: function tools for flights, hotels, itinerary, transportation, budget, packing, advisory, profile memory, and report synthesis

Important API routes:

- `POST /api/chat` (SSE stream)
- `POST /api/reset`
- `POST /api/sync-profile`
- `GET /health`

### Frontend (Next.js)

- `ui/app/page.tsx`: shell layout with nav + planner workspace + chat drawer
- `ui/components/ChatWindow.tsx`: chat loop, SSE event handling, session lifecycle
- `ui/components/PlannerWorkspace.tsx`: trip snapshot inputs, autocomplete/date picker, saved flight/hotel cards
- `ui/lib/api.ts`: streaming client for backend routes

## Data Flow

1. User sends message from `ChatWindow`
2. Frontend calls `POST /api/chat` and consumes SSE events
3. Agent may call tools (flights/hotels/etc.) and update profile state
4. Backend emits:
   - tool status events
   - profile-memory events
   - card payloads from tool metadata
   - final reply with suggestions + placeholder
5. UI updates both chat transcript and planner panels in real time

## Tech Stack

- **Agent/Backend**: Python, FastAPI, LangChain, LangGraph, Pydantic
- **Model provider**: OpenAI chat models via LangChain
- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind, Framer Motion
- **External data**: Booking.com via RapidAPI, SerpApi (advisory/tooling paths)
- **Testing**: Pytest (+ mocked unit tests and live integration tests)

## Local Development

### Prerequisites

- Python 3.11+ (3.12+ recommended)
- Node.js 22.x
- npm

### 1) Install dependencies

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Frontend (from repo root):

```bash
npm install
npm --prefix ui install
```

### 2) Configure environment variables

Create `.env.local` in the project root:

```bash
OPENAI_API_KEY=your_openai_key
X-RAPIDAPI-KEY=your_rapidapi_key
SERPAPI_API_KEY=your_serpapi_key
# Optional comma-separated allowlist additions:
ALLOWED_ORIGINS=http://localhost:3000
```

Create `ui/.env.local`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 3) Run backend and frontend

Backend:

```bash
source .venv/bin/activate
uvicorn server:app --reload
```

Frontend:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Testing

Unit tests (mocked APIs):

```bash
pytest test_tools.py -v
```

Integration tests (real APIs, consumes credits/tokens):

```bash
pytest test_integration.py -v
```

Conversation scenario harness:

```bash
python tests.py
```

## Deployment Notes

- Frontend is Vercel-ready (Next.js build configured in `vercel.json`).
- Backend should run as a persistent Python service (Render/Railway/Fly/AWS, etc.) because it serves SSE and handles protected API keys.
- In production, set frontend `NEXT_PUBLIC_BACKEND_URL` to your deployed backend base URL.

## Repository Layout

```text
.
├── main.py                 # LangGraph agent + system prompt + tool wiring
├── server.py               # FastAPI SSE API
├── tools/                  # Travel tools + profile/report modules
├── ui/                     # Next.js frontend
├── test_tools.py           # Unit tests (mocked external APIs)
├── test_integration.py     # Live integration tests
└── vercel.json             # Frontend deployment config
```

## Build Journey (What Changed)

This project evolved from a simple agent demo into a production-style travel planning experience. High-level milestones:

1. **Initial agent foundation**
   - Set up LangGraph + tool-calling flow for travel tasks (flights, hotels, itinerary, budget, packing, advisory).
   - Added a strong travel-scoped system prompt to keep responses domain-focused.

2. **Streaming backend for real chat UX**
   - Introduced FastAPI SSE chat endpoint (`/api/chat`) so the UI can show tool activity and final responses in real time.
   - Added reset and profile sync endpoints to support session controls from the UI.

3. **Session memory and persistence**
   - Moved from ephemeral memory to session-scoped profile state.
   - Added on-disk profile persistence (`.wayfarer_profiles.json`) so confirmed trip details survive reloads.
   - Added SQLite checkpoint path with graceful fallback when optional checkpoint packages are unavailable.

4. **Tool reliability and guardrails**
   - Hardened flight flow so round-trip/one-way state and date order are explicitly validated.
   - Added stricter date/origin validation to avoid accidental or invalid searches.
   - Improved offer quality with deduplication and best-offer ranking logic.

5. **UI redesign into planner workspace**
   - Built a split-pane planner with section navigation, chat drawer, and a trip snapshot panel.
   - Added saveable flight/hotel cards and richer visual hierarchy for planning states.
   - Synced snapshot inputs back to backend profile memory to reduce repetitive questioning.

6. **Quick-reply chip quality improvements**
   - Added structured UI hint extraction (chips + placeholder) and authoritative inline UI metadata parsing.
   - Added repair logic for common chip failures (e.g., Yes/No where explicit choices are required, robotic ISO date chips).

7. **Testing and deployment hardening**
   - Expanded unit coverage with mocked external APIs.
   - Added live integration tests for real API/provider paths.
   - Finalized Vercel-friendly frontend build config and documented backend deployment separation.

## Current Demo

Use the live deployment here:

[https://lang-travel-agent-git-main-ssikder2s-projects.vercel.app](https://lang-travel-agent-git-main-ssikder2s-projects.vercel.app)

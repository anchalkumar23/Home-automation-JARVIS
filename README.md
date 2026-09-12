# Ultimate JARVIS

A voice-first AI assistant built toward the vision in [`AGENT.md`](AGENT.md): a personal AI operating system that manages a studio, a business, and daily life — not just a chatbot. Built incrementally, one capability at a time, with a full design spec and plan behind every feature (see [`docs/superpowers/`](docs/superpowers/)).

## Quick Start

Non-technical / just want to run it: double-click [`start-jarvis.bat`](start-jarvis.bat) at the project root. It installs anything missing (Python, Node, ffmpeg) and launches everything automatically.

Manual setup: see [`backend/README.md`](backend/README.md) for the backend, and `frontend/` for the Next.js app (`npm install && npm run dev`).

Both `backend/.env` and `frontend/.env.local` need real values before anything works — API keys, and the two secrets described in [Security](#security) below.

## What's Built

### Core Assistant
Voice conversation (English/Spanish, auto-detected), persistent categorized memory (people/projects/documents/decisions/goals), tasks with due dates and reminders, and calendar (read + draft-and-confirm write, never applied silently).

### Tools (31, see [`backend/app/ai/tools.py`](backend/app/ai/tools.py))
Web search, reading a given webpage/PDF, news briefings, market quotes (stocks/forex/crypto), image generation, business report cards, content drafting (captions/scripts/marketing copy), YouTube/papers/patents search, music, Gmail send, calendar events, subtitle generation + translation, silence removal, highlight/Shorts detection, TV control (TCL/Roku, Samsung, LG), and the reflective tools below.

### The "10 Core Functions" — 5 of 10 built
On-demand, reusing existing tools rather than new infrastructure:
- ✅ **Opportunity Engine** — researches a topic across web/news/patents/papers, surfaces evidence-backed opportunities
- ✅ **Second Brain** — categorized memory with recall ("what do I know about X", "why did we decide X")
- ✅ **Error Detector / Decision Simulator** — stress-tests a plan or simulates best/likely/worst-case outcomes, on request
- ✅ **"What Am I Forgetting?" Mode** — reviews open tasks, upcoming events, and memories, flags what's worth surfacing
- ✅ **Learning System (lightweight v1)** — tracks whether recommendations were accepted or dismissed, factors that into future ones
- ⬜ Early Warning System, Global Radar, Time Manager, Autonomous Builder — all need proactive/scheduled background checks, which don't exist yet
- ⬜ Second Brain, Learning System, and the on-demand functions above are v1s — see their specs in `docs/superpowers/specs/` for explicitly deferred scope

### Studio Automation
Direct integration, no Home Assistant — one small tool per device, talking to its local API directly (see the reasoning in [`docs/superpowers/specs/2026-08-19-tv-control-design.md`](docs/superpowers/specs/2026-08-19-tv-control-design.md)).
- ✅ **TV control** (TCL/Roku, Samsung, LG) — power (with Wake-on-LAN), volume, mute, app launch. Code-complete and unit-tested; live end-to-end testing is pending the client's TV MAC addresses and being on the same network.
- ⬜ Smart lighting, cameras, and other devices — pending client hardware confirmation.

### Security
No real login system yet (see [Roadmap](#roadmap)). In the meantime:
- Every sensitive API route requires a shared-secret header (`JARVIS_API_KEY` in `backend/.env`, sent automatically by the frontend).
- Google OAuth tokens are encrypted at rest (`TOKEN_ENCRYPTION_KEY` in `backend/.env`).
- Reflected-XSS fix on the Gmail OAuth callback.

Full findings and reasoning: none checked in (security details aren't published in this repo) — ask the developer if you need the review history.

## Roadmap

Not yet started: real per-user authentication, Tailscale-based remote access (so the app works outside the studio's WiFi — needs an always-on studio machine + a Tailscale account), Stream Deck control (hardware in hand, library identified, not yet built), computer vision, holographic avatar, mobile companion, and the remaining Core Functions above. See `AGENT.md` for the full original requirements and `docs/superpowers/specs/` for what's been designed in detail so far.

## Tech Stack

- **Backend:** Python, FastAPI, SQLite (no ORM)
- **Frontend:** Next.js, React, TypeScript, Tailwind
- **LLM:** Groq (testing), moving to OpenRouter for production
- **Voice:** browser Web Speech API (output) + Groq-hosted Whisper (input transcription)

## Docs

- [`AGENT.md`](AGENT.md) — the original, full client requirements
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — design spec per feature (what, why, scope boundaries)
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — implementation plan per feature
- [`docs/testing-guide.md`](docs/testing-guide.md) — manual test steps per feature

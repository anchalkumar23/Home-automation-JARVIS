# Productivity Foundation — Increment 2c Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let JARVIS propose creating, editing, and deleting Google Calendar events — always as a draft/confirmation the user approves via the UI, never an autonomous AI action, matching the safety boundary already established for email sending.

**Architecture:** Two new AI-callable tools (`draft_calendar_event`, `propose_delete_calendar_event`) only ever return a proposal; three new backend REST endpoints (create/update/delete) perform the actual Google Calendar API calls, triggered solely by direct UI button clicks. `frontend/components/jarvis-interface.tsx` has grown large (1077 lines) after 2a's additions — this increment extracts its reusable message-rendering components into a new `frontend/components/message-cards.tsx`, both to control file size and to give the two new calendar UI components a natural home alongside `EmailDraftCard`.

**Tech Stack:** FastAPI, stdlib `urllib`/`json`, pytest, Next.js/React. No new dependencies.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/build/manual-verification step instead.

---

### Task 1: Extend `ClientAction` and add Calendar REST schemas

**Files:**
- Modify: `backend/app/schemas.py:28-35` (`ClientAction`), append new models after `SendEmailResponse` (current lines 67-69)

- [ ] **Step 1: Extend `ClientAction` with calendar fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-35):
```python
class ClientAction(BaseModel):
    type: Literal[
        "open_url",
        "compose_email",
        "calendar_event_draft",
        "calendar_event_delete_confirm",
    ]
    url: str | None = None
    email_to: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    mailto_link: str | None = None
    event_id: str | None = None
    event_summary: str | None = None
    event_start: str | None = None
    event_end: str | None = None
    event_description: str | None = None
    event_location: str | None = None
    event_attendees: list[str] | None = None
```

- [ ] **Step 2: Add the Calendar REST request/response models**

Modify `backend/app/schemas.py`, appending after the existing `SendEmailResponse` class:
```python


class CalendarEventPayload(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    start: str
    end: str
    description: str = Field(default="")
    location: str = Field(default="")
    attendees: list[str] = Field(default_factory=list)
    time_zone: str | None = None


class CalendarEventResponse(BaseModel):
    ok: bool
    event_id: str | None = None


class DeleteEventResponse(BaseModel):
    ok: bool
```

- [ ] **Step 3: Verify it imports cleanly**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
python -c "from app.schemas import ClientAction, CalendarEventPayload, CalendarEventResponse, DeleteEventResponse; print('ok')"
```
Expected: all 19 existing tests pass; script prints `ok`.

---

### Task 2: `backend/app/routers/calendar.py` — create/update/delete endpoints (TDD)

**Files:**
- Create: `backend/tests/test_calendar.py`
- Create: `backend/app/routers/calendar.py`

- [ ] **Step 1: Write the failing tests for the event-body builder**

Create `backend/tests/test_calendar.py`:
```python
from app.routers.calendar import build_event_body


def test_build_event_body_minimal():
    body = build_event_body("Team sync", "2026-08-10T15:00:00+05:30", "2026-08-10T15:30:00+05:30")

    assert body["summary"] == "Team sync"
    assert body["start"] == {"dateTime": "2026-08-10T15:00:00+05:30"}
    assert body["end"] == {"dateTime": "2026-08-10T15:30:00+05:30"}
    assert "description" not in body
    assert "location" not in body
    assert "attendees" not in body


def test_build_event_body_with_optional_fields():
    body = build_event_body(
        "Team sync",
        "2026-08-10T15:00:00+05:30",
        "2026-08-10T15:30:00+05:30",
        description="Weekly check-in",
        location="Room 4",
        attendees=["a@example.com", "b@example.com"],
    )

    assert body["description"] == "Weekly check-in"
    assert body["location"] == "Room 4"
    assert body["attendees"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]


def test_build_event_body_with_time_zone():
    body = build_event_body(
        "Team sync",
        "2026-08-10T15:00",
        "2026-08-10T15:30",
        time_zone="Asia/Kolkata",
    )

    assert body["start"] == {"dateTime": "2026-08-10T15:00", "timeZone": "Asia/Kolkata"}
    assert body["end"] == {"dateTime": "2026-08-10T15:30", "timeZone": "Asia/Kolkata"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_calendar.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.routers.calendar'`.

- [ ] **Step 3: Create the router with `build_event_body` and the three endpoints**

Create `backend/app/routers/calendar.py`:
```python
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import CalendarEventPayload, CalendarEventResponse, DeleteEventResponse
from app.services import google_auth

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def build_event_body(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    time_zone: str | None = None,
) -> dict[str, Any]:
    start_obj: dict[str, str] = {"dateTime": start}
    end_obj: dict[str, str] = {"dateTime": end}
    if time_zone:
        start_obj["timeZone"] = time_zone
        end_obj["timeZone"] = time_zone

    body: dict[str, Any] = {
        "summary": summary,
        "start": start_obj,
        "end": end_obj,
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]
    return body


def _calendar_request(access_token: str, url: str, method: str, body: dict[str, Any] | None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="That event could no longer be found.") from exc
        raise HTTPException(status_code=502, detail=f"Google Calendar error {exc.code}: {body_text}") from exc


def _access_token_or_raise(request: Request) -> str:
    settings = request.app.state.settings
    store = request.app.state.memory_store
    try:
        return google_auth.get_valid_access_token(settings, store)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/events", response_model=CalendarEventResponse)
async def create_event(payload: CalendarEventPayload, request: Request) -> CalendarEventResponse:
    access_token = _access_token_or_raise(request)
    body = build_event_body(
        payload.summary,
        payload.start,
        payload.end,
        payload.description,
        payload.location,
        payload.attendees,
        payload.time_zone,
    )
    data = _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}?sendUpdates=all", "POST", body)
    return CalendarEventResponse(ok=True, event_id=data.get("id"))


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(event_id: str, payload: CalendarEventPayload, request: Request) -> CalendarEventResponse:
    access_token = _access_token_or_raise(request)
    body = build_event_body(
        payload.summary,
        payload.start,
        payload.end,
        payload.description,
        payload.location,
        payload.attendees,
        payload.time_zone,
    )
    data = _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}/{event_id}?sendUpdates=all", "PATCH", body)
    return CalendarEventResponse(ok=True, event_id=data.get("id"))


@router.delete("/events/{event_id}", response_model=DeleteEventResponse)
async def delete_event(event_id: str, request: Request) -> DeleteEventResponse:
    access_token = _access_token_or_raise(request)
    _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}/{event_id}?sendUpdates=all", "DELETE", None)
    return DeleteEventResponse(ok=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 22 passed (the 3 new `build_event_body` tests plus the previous 19).

---

### Task 3: Add `draft_calendar_event` and `propose_delete_calendar_event` tools

**Files:**
- Modify: `backend/app/ai/tools.py:196-212` (append to `TOOL_DEFINITIONS`), append new functions after `_tool_list_calendar_events` (current lines 453-501), modify `_tool_list_calendar_events`'s event dict (current lines 493-499), `:506-520` (`TOOL_REGISTRY`)

These tools only ever return a proposal — neither calls the Google Calendar API. Consistent with `_tool_compose_email`, they are not unit-tested (no network call to mock); their downstream effect is verified in Task 8.

- [ ] **Step 1: Add `id` to each event returned by `_tool_list_calendar_events`**

Modify `backend/app/ai/tools.py`, replacing the event-building block inside `_tool_list_calendar_events` (current lines 490-499):
```python
    events = []
    for item in data.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "(No title)"),
                "start": start,
                "location": item.get("location"),
            }
        )
```

- [ ] **Step 2: Add the two new tool definitions**

Modify `backend/app/ai/tools.py`, adding these entries to `TOOL_DEFINITIONS` right before its closing `]` (currently right after the `list_calendar_events` entry ends at line 211, before line 212's `]`):
```python
    {
        "type": "function",
        "function": {
            "name": "draft_calendar_event",
            "description": "Propose creating a new calendar event, or editing an existing one if event_id is provided. This only drafts the event for the user to review — it does not create or change anything on the real calendar until the user confirms in the UI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": ["string", "null"],
                        "description": "ID of an existing event to edit. Leave empty when proposing a brand-new event.",
                    },
                    "summary": {"type": "string", "description": "Event title."},
                    "start": {
                        "type": "string",
                        "description": "Start date/time in ISO 8601 format, e.g. 2026-08-10T15:00:00+05:30. Resolve relative dates like 'tomorrow' using get_time first.",
                    },
                    "end": {
                        "type": "string",
                        "description": "End date/time in ISO 8601 format.",
                    },
                    "description": {"type": ["string", "null"], "description": "Optional event description."},
                    "location": {"type": ["string", "null"], "description": "Optional event location."},
                    "attendees": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "description": "Optional list of attendee email addresses. They will receive a real calendar invite if the user confirms.",
                    },
                },
                "required": ["summary", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_calendar_event",
            "description": "Propose deleting an existing calendar event, shown to the user as a confirmation. Does not delete anything until the user confirms in the UI. Use list_calendar_events first to find the event_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to delete."},
                    "summary_for_display": {"type": "string", "description": "Event title, shown in the confirmation."},
                    "start_for_display": {"type": "string", "description": "Event start time, shown in the confirmation."},
                },
                "required": ["event_id", "summary_for_display", "start_for_display"],
            },
        },
    },
```

- [ ] **Step 3: Add the two tool implementations**

Modify `backend/app/ai/tools.py`, adding these functions right after `_tool_list_calendar_events` (which currently ends at line 501) and before the `# ── Tool registry ─────` comment:
```python


def _tool_draft_calendar_event(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Propose a new or edited calendar event for the user to review and confirm."""
    event_id = args.get("event_id") or None
    summary = str(args.get("summary", "")).strip()
    start = str(args.get("start", "")).strip()
    end = str(args.get("end", "")).strip()
    if not summary or not start or not end:
        raise ValueError("Event summary, start, and end are required.")

    description = str(args.get("description") or "").strip()
    location = str(args.get("location") or "").strip()
    attendees_raw = args.get("attendees") or []
    attendees = [str(a).strip() for a in attendees_raw if str(a).strip()]

    return {
        "action": {
            "type": "calendar_event_draft",
            "event_id": event_id,
            "event_summary": summary,
            "event_start": start,
            "event_end": end,
            "event_description": description,
            "event_location": location,
            "event_attendees": attendees,
        },
        "message": (
            f"I've {'updated' if event_id else 'drafted'} the event \"{summary}\" for your review. "
            "Nothing is created or changed on your calendar until you confirm it."
        ),
    }


def _tool_propose_delete_calendar_event(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Propose deleting an existing calendar event, pending user confirmation."""
    event_id = str(args.get("event_id", "")).strip()
    summary = str(args.get("summary_for_display", "")).strip()
    start = str(args.get("start_for_display", "")).strip()
    if not event_id:
        raise ValueError("event_id is required.")

    return {
        "action": {
            "type": "calendar_event_delete_confirm",
            "event_id": event_id,
            "event_summary": summary or "this event",
            "event_start": start,
        },
        "message": f"Please confirm you'd like to delete \"{summary or 'this event'}\".",
    }
```

- [ ] **Step 4: Register both tools**

Modify `backend/app/ai/tools.py`, replacing `TOOL_REGISTRY` (current lines 506-520):
```python
TOOL_REGISTRY: dict[str, ToolFunction] = {
    "get_time": _tool_get_time,
    "get_system_status": _tool_get_system_status,
    "save_memory": _tool_save_memory,
    "get_memory": _tool_get_memory,
    "add_task": _tool_add_task,
    "list_tasks": _tool_list_tasks,
    "open_url": _tool_open_url,
    "web_search": _tool_web_search,
    "generate_image": _tool_generate_image,
    "get_news": _tool_get_news,
    "play_music": _tool_play_music,
    "compose_email": _tool_compose_email,
    "list_calendar_events": _tool_list_calendar_events,
    "draft_calendar_event": _tool_draft_calendar_event,
    "propose_delete_calendar_event": _tool_propose_delete_calendar_event,
}
```

- [ ] **Step 5: Verify the test suite still passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
python -c "from app.ai.tools import TOOL_REGISTRY; print('draft_calendar_event' in TOOL_REGISTRY, 'propose_delete_calendar_event' in TOOL_REGISTRY)"
```
Expected: 22 tests pass; script prints `True True`.

---

### Task 4: Teach `ToolRunner.extract_action` about the two new action types

**Files:**
- Modify: `backend/app/services/tool_runner.py:25-45` (`extract_action`)

- [ ] **Step 1: Add the two new branches**

Modify `backend/app/services/tool_runner.py`, replacing the `extract_action` static method (current lines 25-45):
```python
    @staticmethod
    def extract_action(tool_results: list[ToolResult]) -> ClientAction | None:
        """Extract the first client action from tool results."""
        for tool_result in tool_results:
            if not tool_result.ok or not isinstance(tool_result.result, dict):
                continue
            action = tool_result.result.get("action")
            if not isinstance(action, dict):
                continue
            action_type = action.get("type")
            if action_type == "open_url" and action.get("url"):
                return ClientAction(type="open_url", url=str(action["url"]))
            if action_type == "compose_email":
                return ClientAction(
                    type="compose_email",
                    email_to=action.get("email_to") or "",
                    email_subject=action.get("email_subject") or "",
                    email_body=action.get("email_body") or "",
                    mailto_link=action.get("mailto_link") or "",
                )
            if action_type == "calendar_event_draft":
                return ClientAction(
                    type="calendar_event_draft",
                    event_id=action.get("event_id"),
                    event_summary=action.get("event_summary") or "",
                    event_start=action.get("event_start") or "",
                    event_end=action.get("event_end") or "",
                    event_description=action.get("event_description") or "",
                    event_location=action.get("event_location") or "",
                    event_attendees=action.get("event_attendees") or [],
                )
            if action_type == "calendar_event_delete_confirm":
                return ClientAction(
                    type="calendar_event_delete_confirm",
                    event_id=action.get("event_id") or "",
                    event_summary=action.get("event_summary") or "",
                    event_start=action.get("event_start") or "",
                )
        return None
```

- [ ] **Step 2: Verify the test suite still passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 22 tests pass.

---

### Task 5: Register the router and update the system prompt

**Files:**
- Modify: `backend/app/main.py` (full-file replacement)
- Modify: `backend/app/ai/provider.py:80-101` (tool list + new behavior rule in `SYSTEM_PROMPT`)

- [ ] **Step 1: Register `calendar_router`**

Replace the full contents of `backend/app/main.py` with:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.calendar import router as calendar_router
from app.routers.chat import router as chat_router
from app.routers.gmail import router as gmail_router
from app.routers.transcribe import router as transcribe_router
from app.services.memory import MemoryStore
from app.services.tool_runner import ToolRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    memory_store = MemoryStore(settings.database_path)
    app.state.settings = settings
    app.state.memory_store = memory_store
    app.state.tool_runner = ToolRunner(memory_store)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JARVIS Backend", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(transcribe_router)
    app.include_router(gmail_router)
    app.include_router(calendar_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "jarvis-backend"}

    return app


app = create_app()
```

- [ ] **Step 2: Add the tool bullets and a new behavior rule**

Modify `backend/app/ai/provider.py`, replacing the `list_calendar_events` bullet line (current line 81):
```
• compose_email — Draft an email for the user to review and send.
• list_calendar_events — Check the user's upcoming Google Calendar events.
• draft_calendar_event — Propose creating or editing a calendar event for the user to confirm.
• propose_delete_calendar_event — Propose deleting a calendar event for the user to confirm.
```

Modify `backend/app/ai/provider.py`, adding a new rule 15 directly after the existing rule 14 (current line 101, immediately before the closing `"""`):
```
15. Any request to schedule, create, edit, reschedule, or delete a calendar event — even a vague one — must go through draft_calendar_event or propose_delete_calendar_event, never described in plain chat text instead. These tools only propose a change; the user must confirm it in the UI before anything actually happens on their real calendar, so never claim an event was created, changed, or deleted — only that you've drafted or proposed it. When the user gives a relative date or time (e.g. "tomorrow," "next Friday," "in an hour"), call get_time first to know the current date/time before resolving it — do not guess.
```

- [ ] **Step 3: Restart the backend and verify it boots with all routers**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
python -m pytest tests/ -v
```
Expected: health check returns `{"status":"online","service":"jarvis-backend"}`; all 22 tests pass.

---

### Task 6: Extract reusable message components into `frontend/components/message-cards.tsx`

**Files:**
- Create: `frontend/components/message-cards.tsx`

This moves `ClientAction`, `TypewriterText` (and its `useTypewriter` hook), `ImageModal`, `CopyButton`, `EmailDraftCard`, and `InlineImage` out of `jarvis-interface.tsx` (which has grown to 1077 lines) into their own file, and adds the two new calendar components alongside them. Task 7 removes these from `jarvis-interface.tsx` and imports them from here instead.

- [ ] **Step 1: Create the file**

Create `frontend/components/message-cards.tsx`:
```typescript
"use client"

import { useEffect, useRef, useState } from "react"
import { CalendarClock, Check, ClipboardCopy, Download, Loader2, Mail, Maximize2, X } from "lucide-react"
import { cn } from "@/lib/utils"

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface ClientAction {
  type: "open_url" | "compose_email" | "calendar_event_draft" | "calendar_event_delete_confirm"
  url?: string
  email_to?: string
  email_subject?: string
  email_body?: string
  mailto_link?: string
  event_id?: string
  event_summary?: string
  event_start?: string
  event_end?: string
  event_description?: string
  event_location?: string
  event_attendees?: string[]
}

/* ── Typewriter hook ───────────────────────────────────────────────────── */

function useTypewriter(text: string, speed = 18) {
  const [displayed, setDisplayed] = useState("")
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!text) {
      setDisplayed("")
      setDone(true)
      return
    }
    setDisplayed("")
    setDone(false)
    let i = 0
    const interval = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) {
        clearInterval(interval)
        setDone(true)
      }
    }, speed)
    return () => clearInterval(interval)
  }, [text, speed])

  return { displayed, done }
}

/* ── Typing Message Component ───────────────────────────────────────────── */

export function TypewriterText({ text, onDone }: { text: string; onDone?: () => void }) {
  const { displayed, done } = useTypewriter(text, 16)
  const calledRef = useRef(false)

  useEffect(() => {
    if (done && onDone && !calledRef.current) {
      calledRef.current = true
      onDone()
    }
  }, [done, onDone])

  return (
    <>
      {displayed}
      {!done && <span className="animate-pulse text-primary">▌</span>}
    </>
  )
}

/* ── Fullscreen Image Modal ─────────────────────────────────────────────── */

export function ImageModal({ src, onClose }: { src: string; onClose: () => void }) {
  const handleDownload = async () => {
    try {
      const response = await fetch(src)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `jarvis-image-${Date.now()}.png`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      window.open(src, "_blank")
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="relative max-h-[90vh] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt="Generated image fullscreen"
          className="max-h-[85vh] max-w-[85vw] rounded-lg border border-primary/30 object-contain shadow-2xl"
        />
        <div className="absolute -top-3 right-0 flex gap-2">
          <button
            onClick={handleDownload}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-card/90 text-primary shadow-lg backdrop-blur-md transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="Download image"
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-card/90 text-primary shadow-lg backdrop-blur-md transition-colors hover:bg-destructive hover:text-white"
            aria-label="Close fullscreen"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Copy-to-clipboard button ───────────────────────────────────────────── */

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement("textarea")
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand("copy")
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.15em] text-primary transition-colors hover:bg-primary/10"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" /> Copied
        </>
      ) : (
        <>
          <ClipboardCopy className="h-3 w-3" /> {label}
        </>
      )}
    </button>
  )
}

/* ── Email Draft Card with editable recipient ───────────────────────────── */

export function EmailDraftCard({
  action,
  onSend,
  sending,
}: {
  action: ClientAction
  onSend: (to: string, subject: string, body: string) => void
  sending: boolean
}) {
  const [to, setTo] = useState(action.email_to || "")
  const [subject, setSubject] = useState(action.email_subject || "")
  const [body, setBody] = useState(action.email_body || "")

  const mailtoLink = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <Mail className="h-3 w-3" />
        Email Draft
      </div>
      <input
        value={to}
        onChange={(e) => setTo(e.target.value)}
        placeholder="Recipient email address"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Recipient email address"
      />
      <input
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Email subject"
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Email body"
        rows={4}
        className="max-h-[160px] w-full resize-y rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Email body"
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={sending}
          onClick={() => onSend(to, subject, body)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <Mail className="h-3 w-3" /> {sending ? "Sending…" : "Send via Gmail"}
        </button>
        <a
          href={mailtoLink}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-accent-foreground transition-opacity hover:opacity-90"
        >
          <Mail className="h-3 w-3" /> Open in Mail App
        </a>
        <CopyButton text={mailtoLink} label="Copy link" />
        <CopyButton text={`Subject: ${subject}\n\n${body}`} label="Copy email" />
      </div>
    </div>
  )
}

/* ── Inline Image with loading state ────────────────────────────────────── */

export function InlineImage({
  src,
  onFullscreen,
}: {
  src: string
  onFullscreen: () => void
}) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

  return (
    <div className="group relative mt-3">
      {!loaded && !errored && (
        <div className="flex h-[200px] items-center justify-center rounded-md border border-primary/20 bg-primary/5">
          <div className="flex flex-col items-center gap-2 text-primary/60">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em]">
              Generating image…
            </span>
          </div>
        </div>
      )}
      {errored && (
        <div className="flex h-[120px] items-center justify-center rounded-md border border-destructive/30 bg-destructive/5">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-destructive">
            Image failed to load
          </span>
        </div>
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="AI generated image"
        className={cn(
          "max-h-[240px] w-full rounded-md border border-primary/20 object-cover transition-opacity",
          loaded ? "opacity-100" : "h-0 opacity-0",
        )}
        loading="eager"
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
      {loaded && (
        <div className="absolute right-2 top-2 flex gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            onClick={onFullscreen}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-card/80 text-primary shadow backdrop-blur-sm transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="View fullscreen"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={async () => {
              try {
                const r = await fetch(src)
                const blob = await r.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement("a")
                a.href = url
                a.download = `jarvis-image-${Date.now()}.png`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
                URL.revokeObjectURL(url)
              } catch {
                window.open(src, "_blank")
              }
            }}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-card/80 text-primary shadow backdrop-blur-sm transition-colors hover:bg-primary hover:text-primary-foreground"
            aria-label="Download image"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Calendar Event Draft Card (create or edit) ─────────────────────────── */

export function CalendarEventDraftCard({
  action,
  onSave,
  saving,
}: {
  action: ClientAction
  onSave: (
    eventId: string | undefined,
    summary: string,
    start: string,
    end: string,
    description: string,
    location: string,
    attendees: string[],
  ) => void
  saving: boolean
}) {
  const [summary, setSummary] = useState(action.event_summary || "")
  const [start, setStart] = useState(action.event_start || "")
  const [end, setEnd] = useState(action.event_end || "")
  const [description, setDescription] = useState(action.event_description || "")
  const [location, setLocation] = useState(action.event_location || "")
  const [attendeesText, setAttendeesText] = useState((action.event_attendees || []).join(", "))

  const isEdit = Boolean(action.event_id)

  const handleSubmit = () => {
    const attendees = attendeesText
      .split(",")
      .map((email) => email.trim())
      .filter(Boolean)
    onSave(action.event_id, summary, start, end, description, location, attendees)
  }

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <CalendarClock className="h-3 w-3" />
        {isEdit ? "Edit Calendar Event" : "New Calendar Event"}
      </div>
      <input
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="Event title"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event title"
      />
      <div className="flex gap-2">
        <input
          type="datetime-local"
          value={start.slice(0, 16)}
          onChange={(e) => setStart(e.target.value)}
          className="w-1/2 rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground focus:outline-none"
          aria-label="Start date and time"
        />
        <input
          type="datetime-local"
          value={end.slice(0, 16)}
          onChange={(e) => setEnd(e.target.value)}
          className="w-1/2 rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground focus:outline-none"
          aria-label="End date and time"
        />
      </div>
      <input
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder="Location (optional)"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event location"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        rows={2}
        className="max-h-[100px] w-full resize-y rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Event description"
      />
      <input
        value={attendeesText}
        onChange={(e) => setAttendeesText(e.target.value)}
        placeholder="Attendee emails, comma-separated (optional — they'll get a real invite)"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Attendee email addresses"
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={saving}
          onClick={handleSubmit}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <CalendarClock className="h-3 w-3" />
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Event"}
        </button>
      </div>
    </div>
  )
}

/* ── Calendar Event Delete Confirmation ─────────────────────────────────── */

export function CalendarEventDeleteConfirm({
  action,
  onConfirm,
  onCancel,
  deleting,
}: {
  action: ClientAction
  onConfirm: (eventId: string) => void
  onCancel: () => void
  deleting: boolean
}) {
  return (
    <div className="mt-3 space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-destructive">
        <CalendarClock className="h-3 w-3" />
        Delete Event?
      </div>
      <p className="text-[11px] text-foreground">
        {action.event_summary || "This event"}
        {action.event_start ? ` — ${action.event_start}` : ""}
      </p>
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={deleting}
          onClick={() => action.event_id && onConfirm(action.event_id)}
          className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {deleting ? "Deleting…" : "Delete Event"}
        </button>
        <button
          type="button"
          disabled={deleting}
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: errors will appear in `jarvis-interface.tsx` at this point (it still has its own, now-duplicate, definitions of `ClientAction`/`TypewriterText`/`ImageModal`/`EmailDraftCard`/`InlineImage`) — that's expected and resolved entirely in Task 7. No errors should originate from `message-cards.tsx` itself.

---

### Task 7: Rewrite `jarvis-interface.tsx` to use the extracted components and wire in calendar actions

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx` (full-file replacement)

- [ ] **Step 1: Replace the full contents**

This removes the six components now living in `message-cards.tsx` (saving roughly 290 lines), trims the `lucide-react` imports to only what's still used directly in this file, adds calendar save/delete/cancel handlers following the exact same pattern as the existing Gmail handlers, and wires the two new action types into the message-rendering loop.

Replace the full contents of `frontend/components/jarvis-interface.tsx` with:
```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { AudioLines, Keyboard, Mail, Mic, Power, SendHorizonal, Volume2, VolumeX } from "lucide-react"
import { ArcReactor } from "@/components/arc-reactor"
import { ClockPanel, StatusPanel, SystemPanel } from "@/components/hud-panels"
import {
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  EmailDraftCard,
  ImageModal,
  InlineImage,
  TypewriterText,
} from "@/components/message-cards"
import { VoiceVisualizer } from "@/components/voice-visualizer"
import { useSpeech } from "@/lib/use-speech"
import { useWakeWord } from "@/lib/use-wake-word"
import { cn } from "@/lib/utils"

/* ── Types ──────────────────────────────────────────────────────────────── */

type OrbState = "idle" | "listening" | "thinking" | "speaking"

interface ToolUsed {
  name: string
  arguments?: Record<string, unknown>
  result?: unknown
  ok: boolean
  error?: string | null
}

interface BackendResponse {
  answer: string
  provider: string
  model?: string | null
  tools_used?: ToolUsed[]
  action?: ClientAction | null
  error?: string | null
  image_url?: string | null
  language?: string
}

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  provider?: string
  model?: string | null
  toolsUsed?: ToolUsed[]
  action?: ClientAction | null
  imageUrl?: string | null
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const BACKEND_URL = process.env.NEXT_PUBLIC_JARVIS_BACKEND ?? "http://127.0.0.1:8000"

const STATE_COPY: Record<OrbState, string> = {
  idle: "Ready when you are",
  listening: "Listening...",
  thinking: "Processing...",
  speaking: "Responding...",
}

const FILLER_PHRASES = [
  "One moment, sir…",
  "Working on that…",
  "Let me look into it…",
  "Processing your request…",
  "Give me a second…",
  "Checking now…",
  "On it…",
  "Analyzing…",
  "Running the query…",
  "Just a moment…",
]

function randomFiller(): string {
  return FILLER_PHRASES[Math.floor(Math.random() * FILLER_PHRASES.length)]
}

/* ── Backend API call ──────────────────────────────────────────────────── */

async function sendToBackend(
  message: string,
  history: { role: "user" | "assistant"; content: string }[],
): Promise<BackendResponse> {
  const response = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history: history.map((h) => ({ role: h.role, content: h.content })),
      provider: "auto",
      user_id: "default",
    }),
  })
  if (!response.ok) {
    throw new Error(`Backend ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

function offlineFallback(input: string): BackendResponse {
  const text = input.toLowerCase()
  let answer: string
  if (/\b(hi|hello|hey|greetings)\b/.test(text)) {
    answer =
      "Hello. I'm running in offline mode — the backend appears unreachable. Basic conversation is available."
  } else if (text.includes("time")) {
    answer = `It's currently ${new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}. Note: I'm running offline.`
  } else if (text.includes("status") || text.includes("diagnostic") || text.includes("system")) {
    answer =
      "I'm operating in offline fallback mode. The backend server at " +
      BACKEND_URL +
      " is unreachable. Please start the backend to unlock full capabilities."
  } else {
    answer = `I've received your message, but I'm currently unable to reach the backend at ${BACKEND_URL}. Please ensure the Python server is running, then try again.`
  }
  return { answer, provider: "offline_fallback", tools_used: [] }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function JarvisInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [orbState, setOrbState] = useState<OrbState>("idle")
  const [booted, setBooted] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [fillerText, setFillerText] = useState("")
  const [typingMsgId, setTypingMsgId] = useState<string | null>(null)
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null)
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null)
  const [gmailEmail, setGmailEmail] = useState<string | null>(null)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [savingCalendarEvent, setSavingCalendarEvent] = useState(false)
  const [deletingCalendarEvent, setDeletingCalendarEvent] = useState(false)

  const {
    supported,
    listening,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
    voices,
    selectedVoiceURI,
    setSelectedVoiceURI,
    muted,
    setMuted,
    micLevelsRef,
  } = useSpeech()

  const { wakeWordSupported, wakeWordActive, startWakeWordDetection, stopWakeWordDetection } =
    useWakeWord()

  const stateRef = useRef<OrbState>("idle")
  stateRef.current = orbState
  const messagesRef = useRef<Message[]>([])
  messagesRef.current = messages
  const scrollRef = useRef<HTMLDivElement>(null)

  // Boot animation
  useEffect(() => {
    const t = setTimeout(() => setBooted(true), 120)
    return () => clearTimeout(t)
  }, [])

  // Check backend health on mount
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(4000) })
        if (!cancelled) setBackendOnline(res.ok)
      } catch {
        if (!cancelled) setBackendOnline(false)
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [])

  // Check Gmail connection status on mount
  useEffect(() => {
    let cancelled = false
    async function checkGmail() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/status`)
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) {
          setGmailConnected(Boolean(data.connected))
          setGmailEmail(data.email ?? null)
        }
      } catch {
        if (!cancelled) setGmailConnected(false)
      }
    }
    checkGmail()
    return () => {
      cancelled = true
    }
  }, [])

  // Auto-scroll comms log
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, orbState, fillerText])

  // ── Send message handler ────────────────────────────────────────────
  const handleSend = useCallback(
    async (raw: string) => {
      const content = raw.trim()
      if (!content) return
      setInput("")

      // Interrupt current speech if speaking
      if (stateRef.current === "speaking") {
        cancelSpeech()
      }

      const userMsg: Message = { id: crypto.randomUUID(), role: "user", content }
      setMessages((prev) => [...prev, userMsg])
      setOrbState("thinking")
      setFillerText(randomFiller())

      // Build history for the backend (last 12 messages)
      const currentMessages = messagesRef.current
      const history = [...currentMessages, userMsg]
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-12)
        .map((m) => ({ role: m.role, content: m.content }))

      let response: BackendResponse
      try {
        response = await sendToBackend(content, history)
        setBackendOnline(true)
      } catch {
        response = offlineFallback(content)
        setBackendOnline(false)
      }

      setFillerText("")

      // Handle client-side actions from backend
      if (response.action?.type === "open_url" && response.action.url) {
        try {
          const a = document.createElement("a")
          a.href = response.action.url
          a.target = "_blank"
          a.rel = "noopener noreferrer"
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
        } catch {
          // Link will be in the chat
        }
      }

      const msgId = crypto.randomUUID()
      const assistantMsg: Message = {
        id: msgId,
        role: "assistant",
        content: response.answer,
        provider: response.provider,
        model: response.model,
        toolsUsed: response.tools_used,
        action: response.action,
        imageUrl: response.image_url,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setTypingMsgId(msgId)

      if (!muted && supported) {
        setOrbState("speaking")
        speak(response.answer, () => setOrbState("idle"), response.language)
      } else {
        setOrbState("idle")
      }
    },
    [speak, supported, muted, cancelSpeech],
  )

  // ── Shared comms-log system message helper ─────────────────────────
  const pushSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant" as const, content }])
  }, [])

  // ── Voice input error handler ────────────────────────────────────────
  const handleVoiceError = useCallback(
    (message: string) => {
      setOrbState("idle")
      pushSystemMessage(message)
    },
    [pushSystemMessage],
  )

  // ── Gmail connect + send handlers ───────────────────────────────────
  const handleConnectGmail = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/gmail/auth-url`)
      if (!res.ok) throw new Error()
      const data = await res.json()
      if (data.url) window.open(data.url, "_blank", "noopener,noreferrer")
    } catch {
      pushSystemMessage(
        "Couldn't start the Gmail connection — check that the backend is configured with Google OAuth credentials.",
      )
    }
  }, [pushSystemMessage])

  const handleSendViaGmail = useCallback(
    async (to: string, subject: string, body: string) => {
      if (!to.trim()) {
        pushSystemMessage("Please enter a recipient email address before sending.")
        return
      }
      setSendingEmail(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to, subject, body }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Gmail send failed.")
        }
        pushSystemMessage(`Email sent to ${to} via Gmail.`)
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Couldn't send the email via Gmail.")
      } finally {
        setSendingEmail(false)
      }
    },
    [pushSystemMessage],
  )

  // ── Calendar create/edit/delete handlers ────────────────────────────
  const handleSaveCalendarEvent = useCallback(
    async (
      eventId: string | undefined,
      summary: string,
      start: string,
      end: string,
      description: string,
      location: string,
      attendees: string[],
    ) => {
      if (!summary.trim() || !start || !end) {
        pushSystemMessage("Event title, start, and end time are required before saving.")
        return
      }
      setSavingCalendarEvent(true)
      try {
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
        const res = await fetch(
          eventId ? `${BACKEND_URL}/api/calendar/events/${eventId}` : `${BACKEND_URL}/api/calendar/events`,
          {
            method: eventId ? "PATCH" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              summary,
              start,
              end,
              description,
              location,
              attendees,
              time_zone: timeZone,
            }),
          },
        )
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Could not save the calendar event.")
        }
        pushSystemMessage(
          eventId ? `Updated "${summary}" on your calendar.` : `Created "${summary}" on your calendar.`,
        )
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Could not save the calendar event.")
      } finally {
        setSavingCalendarEvent(false)
      }
    },
    [pushSystemMessage],
  )

  const handleDeleteCalendarEvent = useCallback(
    async (eventId: string) => {
      setDeletingCalendarEvent(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/calendar/events/${eventId}`, { method: "DELETE" })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Could not delete the calendar event.")
        }
        pushSystemMessage("Event deleted from your calendar.")
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Could not delete the calendar event.")
      } finally {
        setDeletingCalendarEvent(false)
      }
    },
    [pushSystemMessage],
  )

  const handleCancelCalendarDelete = useCallback(() => {
    pushSystemMessage("Cancelled — the event was not deleted.")
  }, [pushSystemMessage])

  // ── Mic toggle ─────────────────────────────────────────────────────
  const toggleMic = useCallback(() => {
    if (!supported) return
    if (listening) {
      stopListening()
      setOrbState("idle")
      return
    }
    cancelSpeech()
    setOrbState("listening")
    startListening((text) => {
      setOrbState("thinking")
      handleSend(text)
    }, handleVoiceError)
  }, [supported, listening, stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])

  // Reset orb when recognition ends externally
  useEffect(() => {
    if (!listening && stateRef.current === "listening") setOrbState("idle")
  }, [listening])

  // ── Keyboard shortcuts: Ctrl+J / Alt+J ──────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.altKey) && e.key.toLowerCase() === "j") {
        e.preventDefault()
        if (stateRef.current === "speaking") {
          cancelSpeech()
          setOrbState("idle")
        }
        if (stateRef.current === "listening") {
          stopListening()
          setOrbState("idle")
        } else if (stateRef.current === "idle") {
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])

  // ── Wake word ────────────────────────────────────────────────────────
  const toggleWakeWord = useCallback(() => {
    if (wakeWordActive) {
      stopWakeWordDetection()
    } else {
      startWakeWordDetection(() => {
        if (stateRef.current === "idle") {
          stopWakeWordDetection()
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      }, handleVoiceError)
    }
  }, [
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
    cancelSpeech,
    startListening,
    handleSend,
    handleVoiceError,
  ])

  /* ── Render helpers ─────────────────────────────────────────────────── */

  const comms: Message[] = messages.length
    ? messages
    : [
        {
          id: "boot",
          role: "assistant" as const,
          content:
            "Good day. All systems are online and operating within nominal parameters. How may I assist you?",
        },
      ]

  const providerLabel = (msg: Message) => {
    if (!msg.provider) return null
    const parts: string[] = []
    if (msg.provider && msg.provider !== "offline_fallback") parts.push(msg.provider)
    if (msg.model) parts.push(msg.model)
    return parts.length ? parts.join(" · ") : null
  }

  const toolsLabel = (msg: Message) => {
    if (!msg.toolsUsed?.length) return null
    return msg.toolsUsed.map((t) => (t.ok ? `✓ ${t.name}` : `✗ ${t.name}`)).join(", ")
  }

  return (
    <main className="hud-grid relative h-screen overflow-y-auto bg-background text-foreground lg:overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-vignette" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 hud-scanlines" />

      {fullscreenImage && (
        <ImageModal src={fullscreenImage} onClose={() => setFullscreenImage(null)} />
      )}

      <div
        className={cn(
          "relative z-10 mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-4 py-3 transition-all duration-700 sm:px-6 lg:h-screen lg:min-h-0 lg:px-8",
          booted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0",
        )}
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <header className="shrink-0 flex items-center justify-between border-b border-primary/20 pb-3">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-primary/35 bg-primary/10 text-primary shadow-[0_0_18px_color-mix(in_oklch,var(--primary)_30%,transparent)]">
              <Power className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <p className="font-mono text-xl font-semibold leading-none tracking-[0.22em] text-primary text-glow sm:text-2xl">
                JARVIS
              </p>
              <p className="mt-1 hidden font-mono text-[9px] uppercase tracking-[0.45em] text-muted-foreground sm:block">
                Just A Rather Very Intelligent System
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <span
              className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-[0.35em] sm:flex"
              style={{ color: backendOnline === false ? "var(--destructive)" : "var(--primary)" }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  backgroundColor:
                    backendOnline === false ? "var(--destructive)" : "var(--primary)",
                  boxShadow: `0 0 12px ${backendOnline === false ? "var(--destructive)" : "var(--primary)"}`,
                }}
              />
              {backendOnline === null ? "Checking" : backendOnline ? "Online" : "Offline"}
            </span>

            {voices.length > 0 && (
              <select
                id="voice-select"
                value={selectedVoiceURI}
                onChange={(e) => setSelectedVoiceURI(e.target.value)}
                className="hidden h-9 max-w-[140px] truncate rounded-md border border-primary/25 bg-card/50 px-2 font-mono text-[10px] uppercase tracking-[0.1em] text-primary backdrop-blur-md focus:outline-none sm:block"
                aria-label="Select voice"
              >
                {voices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name}
                  </option>
                ))}
              </select>
            )}

            <button
              id="mute-toggle"
              onClick={() => {
                if (!muted) cancelSpeech()
                setMuted((m) => !m)
              }}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                !muted
                  ? "border-primary/35 bg-primary/10 text-primary"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={!muted}
              aria-label={muted ? "Unmute voice" : "Mute voice"}
            >
              {muted ? (
                <VolumeX className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">{muted ? "Muted" : "Voice"}</span>
            </button>

            {wakeWordSupported && (
              <button
                id="wake-word-toggle"
                onClick={toggleWakeWord}
                className={cn(
                  "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                  wakeWordActive
                    ? "border-accent/40 bg-accent/15 text-accent"
                    : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={wakeWordActive}
                title={'Say "Jarvis" to activate'}
              >
                <AudioLines className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Wake</span>
              </button>
            )}

            <button
              id="google-toggle"
              onClick={handleConnectGmail}
              disabled={gmailConnected === null}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                gmailConnected
                  ? "border-primary/35 bg-primary/10 text-primary hover:bg-primary/20"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              title={
                gmailConnected
                  ? `Connected as ${gmailEmail ?? "unknown"} (Mail + Calendar) — click to reconnect`
                  : "Connect Google to send email and read your calendar"
              }
            >
              <Mail className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">{gmailConnected ? "Google" : "Connect Google"}</span>
            </button>
          </div>
        </header>

        {/* ── Main grid ────────────────────────────────────────────── */}
        <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 py-4 lg:grid-cols-[280px_minmax(320px,1fr)_360px] lg:gap-6 lg:overflow-hidden">
          <aside className="order-2 space-y-4 lg:order-1 lg:min-h-0 lg:overflow-hidden lg:pt-3">
            <SystemPanel />
            <StatusPanel />
            <div className="rounded-lg border border-primary/15 bg-card/30 p-3 backdrop-blur-sm">
              <h3 className="mb-2 font-mono text-[10px] tracking-[0.3em] text-muted-foreground">
                SHORTCUTS
              </h3>
              <ul className="space-y-1.5 font-mono text-[10px] text-muted-foreground">
                <li className="flex items-center gap-2">
                  <Keyboard className="h-3 w-3 text-primary" aria-hidden="true" />
                  <span>
                    <kbd className="rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 text-primary">
                      Ctrl+J
                    </kbd>{" "}
                    Voice input
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Keyboard className="h-3 w-3 text-primary" aria-hidden="true" />
                  <span>
                    <kbd className="rounded border border-primary/25 bg-primary/10 px-1.5 py-0.5 text-primary">
                      Alt+J
                    </kbd>{" "}
                    Voice input
                  </span>
                </li>
              </ul>
            </div>
          </aside>

          {/* ── Center: ARC reactor ─────────────────────────────────── */}
          <section className="order-1 flex min-h-[420px] flex-col items-center justify-center lg:order-2 lg:min-h-0 lg:overflow-hidden">
            <div className="w-full max-w-[520px] shrink-0">
              <ClockPanel />
            </div>
            <div className="relative mt-4 flex min-h-0 w-full flex-1 items-center justify-center">
              <div aria-hidden="true" className="absolute h-[72%] w-px bg-primary/15" />
              <div aria-hidden="true" className="absolute h-px w-[72%] bg-primary/15" />
              <ArcReactor state={orbState} className="w-[min(42vh,380px)] max-w-[380px]" />
            </div>
            <div className="mt-2 w-full max-w-[320px] shrink-0">
              <VoiceVisualizer state={orbState} levelsRef={micLevelsRef} />
              <p className="mt-1 text-center font-mono text-[10px] uppercase tracking-[0.42em] text-primary text-glow">
                {STATE_COPY[orbState]}
              </p>
            </div>
          </section>

          {/* ── Comms Log ───────────────────────────────────────────── */}
          <aside className="order-3 flex min-h-[360px] flex-col rounded-lg border border-primary/20 bg-card/35 p-4 shadow-hud backdrop-blur-md lg:mt-3 lg:min-h-0 lg:overflow-hidden">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <div>
                <h2 className="font-mono text-[10px] uppercase tracking-[0.35em] text-muted-foreground">
                  Comms Log
                </h2>
                <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.35em] text-muted-foreground">
                  J.A.R.V.I.S
                </p>
              </div>
              <span className="font-mono text-[9px] uppercase tracking-[0.28em] text-primary">
                {muted ? "Muted" : "Voice on"}
              </span>
            </div>
            <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
              {comms.map((message) => (
                <article
                  key={message.id}
                  className={cn(
                    "animate-rise rounded-lg border px-4 py-3 font-mono text-xs leading-relaxed",
                    message.role === "user"
                      ? "ml-auto max-w-[82%] border-accent/30 bg-accent/10 text-foreground"
                      : "mr-auto max-w-[88%] border-primary/35 bg-primary/10 text-card-foreground shadow-[0_0_24px_color-mix(in_oklch,var(--primary)_12%,transparent)]",
                  )}
                >
                  <p className="mb-2 text-[9px] uppercase tracking-[0.32em] text-muted-foreground">
                    {message.role === "user" ? "Operator" : "J.A.R.V.I.S"}
                  </p>

                  {/* Typewriter effect for the latest assistant message */}
                  {message.role === "assistant" && message.id === typingMsgId ? (
                    <TypewriterText text={message.content} onDone={() => setTypingMsgId(null)} />
                  ) : (
                    message.content
                  )}

                  {/* Generated image inline with loading state */}
                  {message.imageUrl && (
                    <InlineImage
                      src={message.imageUrl}
                      onFullscreen={() => setFullscreenImage(message.imageUrl!)}
                    />
                  )}

                  {/* Clickable link for open_url actions */}
                  {message.action?.type === "open_url" && message.action.url && (
                    <a
                      href={message.action.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
                    >
                      🔗 {message.action.url}
                    </a>
                  )}

                  {/* Email draft: recipient input + real send + mailto fallback + copy buttons */}
                  {message.action?.type === "compose_email" && (
                    <EmailDraftCard
                      action={message.action}
                      onSend={handleSendViaGmail}
                      sending={sendingEmail}
                    />
                  )}

                  {/* Calendar event draft: create or edit, pending confirmation */}
                  {message.action?.type === "calendar_event_draft" && (
                    <CalendarEventDraftCard
                      action={message.action}
                      onSave={handleSaveCalendarEvent}
                      saving={savingCalendarEvent}
                    />
                  )}

                  {/* Calendar event deletion: pending confirmation */}
                  {message.action?.type === "calendar_event_delete_confirm" && (
                    <CalendarEventDeleteConfirm
                      action={message.action}
                      onConfirm={handleDeleteCalendarEvent}
                      onCancel={handleCancelCalendarDelete}
                      deleting={deletingCalendarEvent}
                    />
                  )}

                  {/* Provider + tools metadata */}
                  {message.role === "assistant" &&
                    (providerLabel(message) || toolsLabel(message)) && (
                      <div className="mt-2 border-t border-primary/15 pt-2 text-[9px] tracking-[0.2em] text-muted-foreground/70">
                        {providerLabel(message) && (
                          <span className="mr-3">⚡ {providerLabel(message)}</span>
                        )}
                        {toolsLabel(message) && <span>🔧 {toolsLabel(message)}</span>}
                      </div>
                    )}
                </article>
              ))}

              {/* Thinking indicator with filler phrase */}
              {orbState === "thinking" && (
                <article className="mr-auto max-w-[88%] animate-rise rounded-lg border border-primary/35 bg-primary/10 px-4 py-3 font-mono text-xs text-card-foreground">
                  <p className="mb-2 text-[9px] uppercase tracking-[0.32em] text-muted-foreground">
                    J.A.R.V.I.S
                  </p>
                  {fillerText && (
                    <p className="mb-2 italic text-muted-foreground/80">{fillerText}</p>
                  )}
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                  </span>
                </article>
              )}
            </div>
          </aside>
        </section>

        {/* ── Input bar ─────────────────────────────────────────────── */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend(input)
          }}
          className="mb-0 flex shrink-0 items-center gap-3 rounded-lg border border-primary/25 bg-card/50 p-2 shadow-hud backdrop-blur-md"
        >
          <button
            type="button"
            onClick={toggleMic}
            disabled={!supported}
            aria-label={listening ? "Stop listening" : "Start voice input"}
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-md border transition-colors",
              listening
                ? "border-primary bg-primary text-primary-foreground"
                : "border-primary/25 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40",
            )}
          >
            <Mic className="h-[18px] w-[18px]" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              listening
                ? "Listening..."
                : supported
                  ? "Speak or type a command..."
                  : "Type a command..."
            }
            className="min-w-0 flex-1 bg-transparent font-mono text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
            aria-label="Message Jarvis"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            aria-label="Send message"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            <SendHorizonal className="h-[18px] w-[18px]" />
          </button>
        </form>
        {!supported && (
          <p className="pb-2 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Voice input requires microphone access and browser audio support. Text input is
            always available.
          </p>
        )}
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Verify the frontend type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 8: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart both servers**

Run (PowerShell), in separate terminals as needed:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Open `http://localhost:3000`.

- [ ] **Step 2: Create an event**

Ask "Schedule a team sync tomorrow at 3pm for 30 minutes." Expected: a "New Calendar Event" draft card appears with the title and correctly resolved date/time pre-filled (confirming the `get_time`-first behavior from the system prompt). Edit a field if you like, then click "Create Event." Expected: a confirmation message in the comms log, and the event actually appears on the real Google Calendar.

- [ ] **Step 3: Create an event with an attendee**

Ask to schedule something and include an attendee's email address (use an address you can check, e.g. a second personal account). Confirm the draft, click "Create Event." Expected: the event is created, and the attendee actually receives a real Google Calendar invitation email.

- [ ] **Step 4: Edit an existing event**

Ask "What's on my calendar this week?" (from increment 2b), then ask to reschedule or edit one of the listed events. Expected: the draft card appears in edit mode ("Edit Calendar Event" / "Save Changes"), pre-filled with that event's existing details. Change something and save — confirm the real event is actually updated, not duplicated.

- [ ] **Step 5: Delete an event**

Ask to delete an event. Expected: a "Delete Event?" confirmation appears (not a full draft card) showing the event's title/time. Click "Delete Event." Expected: a confirmation message, and the event is actually removed from the real calendar.

- [ ] **Step 6: Verify cancel does nothing**

Trigger another delete confirmation and click "Cancel" instead. Expected: a "Cancelled" message, and the event is still present on the real calendar afterward.

- [ ] **Step 7: Confirm nothing regressed**

Quickly re-verify a 2a/2b capability still works — e.g. send a test email via "Send via Gmail," and ask "what's on my calendar" again. Expected: both work exactly as before, confirming the `jarvis-interface.tsx` rewrite and `message-cards.tsx` extraction didn't break existing functionality.

- [ ] **Step 8: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- 2d: Task/reminder redesign.
- Recurring events, multiple calendars, reminder/notification customization beyond Google's defaults.
- Everything else in `AGENT.md` beyond Section 1 and this productivity sub-sequence.

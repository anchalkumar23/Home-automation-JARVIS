# Productivity Foundation — Increment 2b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let JARVIS answer "what's on my calendar" questions by widening the existing Gmail OAuth connection to also cover read-only Google Calendar access, and exposing calendar reading as a normal AI-callable tool.

**Architecture:** `google_auth.py`'s scope constant becomes a list covering both `gmail.send` and `calendar.readonly`, requested together on the next connect. A new `list_calendar_events` tool follows the exact same self-contained pattern as the existing `get_news`/`web_search` tools — its own inline `urllib` call, reusing the existing `get_valid_access_token` for auth, registered in `TOOL_DEFINITIONS`/`TOOL_REGISTRY` like every other tool.

**Tech Stack:** FastAPI, `google-auth`/`google-auth-oauthlib` (already installed), stdlib `urllib`, pytest. No new dependencies.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/manual-verification step instead of a commit step.

---

### Task 1: Widen the OAuth scope to include Calendar read access (TDD)

**Files:**
- Modify: `backend/tests/test_google_auth.py:24-31`
- Modify: `backend/app/services/google_auth.py:16` (scope constant), `:31-36` (`_make_flow`), `:69-86` (`exchange_code`), `:89-124` (`get_valid_access_token`)

- [ ] **Step 1: Extend the failing test**

Modify `backend/tests/test_google_auth.py`, replacing the existing test function (current lines 24-31):
```python
def test_build_auth_url_includes_client_id_and_scope():
    from app.services.google_auth import build_auth_url

    url = build_auth_url(_fake_settings())

    assert "accounts.google.com" in url
    assert "client_id=test-client-id" in url
    assert "gmail.send" in url
    assert "calendar.readonly" in url
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_google_auth.py -v
```
Expected: FAIL — `assert 'calendar.readonly' in url` fails, since only `gmail.send` is currently requested.

- [ ] **Step 3: Replace the scope constant with a list**

Modify `backend/app/services/google_auth.py`, replacing the current line 16 (`GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"`):
```python
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
REQUIRED_SCOPES = [GMAIL_SEND_SCOPE, CALENDAR_READONLY_SCOPE]
```

- [ ] **Step 4: Use the combined scope list everywhere a scope is requested or defaulted**

Modify `backend/app/services/google_auth.py`, replacing `_make_flow` (current lines 31-36):
```python
def _make_flow(settings: Settings) -> Flow:
    return Flow.from_client_config(
        _client_config(settings),
        scopes=REQUIRED_SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
```

In `exchange_code` (current lines 69-86), replace the `scopes=` line inside `store.save_google_tokens(...)`:
```python
        scopes=" ".join(credentials.scopes or REQUIRED_SCOPES),
```
(This is the only line in `exchange_code` that changes — everything else in that function stays as-is.)

In `get_valid_access_token` (current lines 89-124), there are two occurrences of `[GMAIL_SEND_SCOPE]` to replace with `REQUIRED_SCOPES`. First, in the `Credentials(...)` construction:
```python
    credentials = Credentials(
        token=stored["access_token"],
        refresh_token=stored["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=stored["scopes"].split() if stored.get("scopes") else REQUIRED_SCOPES,
        expiry=stored_expiry,
    )
```
Second, in the post-refresh `store.save_google_tokens(...)` call inside the `if not credentials.valid:` block:
```python
        store.save_google_tokens(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or stored["refresh_token"],
            expiry=credentials.expiry.isoformat() if credentials.expiry else "",
            scopes=" ".join(credentials.scopes or REQUIRED_SCOPES),
            email=stored.get("email"),
        )
```
(Only the `scopes=` line in each of these two blocks changes — the rest of `get_valid_access_token` stays as-is.)

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: all 19 tests pass (the extended test now checks for both scopes).

---

### Task 2: Add the `list_calendar_events` tool

**Files:**
- Modify: `backend/app/ai/tools.py:1-15` (imports), `:175-194` (append to `TOOL_DEFINITIONS`), append new function after `_tool_compose_email` (current lines 409-432), `:437-450` (`TOOL_REGISTRY`)

This tool calls the real Google Calendar API, so — consistent with how `get_news` and `web_search` (this file's other network-calling tools) are handled — it is not unit-tested; it's verified manually in Task 5.

- [ ] **Step 1: Add the new imports**

Modify `backend/app/ai/tools.py`, replacing the current import block (lines 1-13):
```python
from __future__ import annotations

import json
import platform
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services import google_auth
from app.services.memory import MemoryStore
```

- [ ] **Step 2: Add the tool definition**

Modify `backend/app/ai/tools.py`, adding this entry to `TOOL_DEFINITIONS` right before its closing `]` (currently right after the `compose_email` entry ends at line 193, before line 194's `]`):
```python
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List the user's upcoming Google Calendar events. Use when the user asks what's on their calendar, their schedule, or about upcoming meetings/appointments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": ["integer", "null"],
                        "description": "How many days ahead to look, starting from now. Defaults to 7 if not specified.",
                    }
                },
            },
        },
    },
```

- [ ] **Step 3: Add the tool implementation**

Modify `backend/app/ai/tools.py`, adding this function right after `_tool_compose_email` (which currently ends at line 432) and before the `# ── Tool registry ─────` comment:
```python


def _tool_list_calendar_events(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """List upcoming Google Calendar events for the connected account."""
    settings = get_settings()
    try:
        access_token = google_auth.get_valid_access_token(settings, store)
    except RuntimeError as exc:
        return {"connected": False, "events": [], "message": str(exc)}

    days = int(args.get("days") or 7)
    now = datetime.now(timezone.utc)
    params = urllib.parse.urlencode(
        {
            "timeMin": now.isoformat(),
            "timeMax": (now + timedelta(days=days)).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 20,
        }
    )
    request = urllib.request.Request(
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return {
                "connected": True,
                "events": [],
                "message": "Calendar access isn't authorized yet. Please reconnect Gmail to grant calendar permission.",
            }
        return {"connected": True, "events": [], "message": f"Calendar API error {exc.code}."}
    except Exception as exc:
        return {"connected": True, "events": [], "message": f"Could not reach Google Calendar: {exc}"}

    events = []
    for item in data.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        events.append(
            {
                "summary": item.get("summary", "(No title)"),
                "start": start,
                "location": item.get("location"),
            }
        )

    return {"connected": True, "days": days, "events": events}
```

- [ ] **Step 4: Register the tool**

Modify `backend/app/ai/tools.py`, replacing `TOOL_REGISTRY` (current lines 437-450):
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
}
```

- [ ] **Step 5: Verify the app still imports and the test suite still passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
python -c "from app.ai.tools import TOOL_REGISTRY; print('list_calendar_events' in TOOL_REGISTRY)"
```
Expected: all 19 tests pass; the script prints `True`.

---

### Task 3: Mention the new tool in the system prompt

**Files:**
- Modify: `backend/app/ai/provider.py:80` (tool bullet list in `SYSTEM_PROMPT`)

- [ ] **Step 1: Add the bullet**

Modify `backend/app/ai/provider.py`, adding one line directly after the existing `compose_email` bullet (current line 80, `• compose_email — Draft an email for the user to review and send.`):
```
• compose_email — Draft an email for the user to review and send.
• list_calendar_events — Check the user's upcoming Google Calendar events.
```

- [ ] **Step 2: Verify the test suite still passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: all 19 tests pass (none of them assert on exact `SYSTEM_PROMPT` content besides identity checks unaffected by this addition).

---

### Task 4: Update the Gmail button tooltip

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:862` (the `title` attribute on the `#gmail-toggle` button)

- [ ] **Step 1: Update the tooltip text**

Modify `frontend/components/jarvis-interface.tsx`, replacing the current `title` line (line 862):
```typescript
              title={
                gmailConnected
                  ? `Connected as ${gmailEmail ?? "unknown"} (Mail + Calendar)`
                  : "Connect Google to send email and read your calendar"
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

### Task 5: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart the backend (picks up the code changes) and confirm the frontend is running**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure `npm run dev` is still running in the frontend (start it if not, per earlier increments' instructions).

- [ ] **Step 2: Reconnect Gmail with the combined scope**

In the browser at `http://localhost:3000`, click the "Gmail" header button (or "Connect Gmail" if it shows disconnected). Expected: Google's consent screen now lists both mail-sending and calendar-viewing permissions. Approve it. The callback page confirms connection; back in JARVIS, hovering the header button should show the updated tooltip mentioning both Mail and Calendar.

- [ ] **Step 3: Ask about the calendar**

Type or say "What's on my calendar this week?" Expected: JARVIS calls `list_calendar_events` and lists real upcoming events from the connected Google account (create a test event in Google Calendar first if the calendar is currently empty, to have something to verify against).

- [ ] **Step 4: Test an explicit range**

Ask "What's on my calendar today?" or "in the next 3 days." Expected: the `days` argument is respected and the results reflect the narrower range.

- [ ] **Step 5: Confirm email sending still works**

Send a quick test email via "Send via Gmail" as in increment 2a's verification, to confirm the scope-widening reconnect didn't break the existing send capability.

- [ ] **Step 6 (optional): Verify the pre-authorization error path**

This confirms the 403 handling in `_tool_list_calendar_events` (Task 2) produces a clear message rather than a crash, for the case where someone asks about their calendar before ever reconnecting with calendar scope. Since you've already reconnected in Step 2, this requires deliberately revoking calendar access to test: go to `https://myaccount.google.com/permissions`, find the JARVIS app, and remove its access, then ask "what's on my calendar" without reconnecting first. Expected: a clear "please reconnect to grant calendar permission" message, not a raw error or crash. Reconnect afterward (repeat Step 2) to restore normal function. Skip this step if you're satisfied the code path is correct from review alone.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if you're continuing to use it).

---

## Post-plan: what's explicitly not in this increment

- 2c: Calendar write (create/edit events).
- 2d: Task/reminder redesign.
- A dedicated calendar UI panel.
- Everything else in `AGENT.md` beyond Section 1 and this productivity sub-sequence.

# Productivity Foundation — Increment 2d Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add due dates and priority to tasks, close the pre-existing gap where tasks could never be marked done or deleted, and add an opt-in browser-notification reminder poller.

**Architecture:** `MemoryStore`'s `tasks` table gains `due_at`/`priority` columns and two new methods (`complete_task`, `delete_task`); three matching AI-callable tools are added/extended, executing directly (no draft-confirm) since they only touch local, personal, reversible data. A new `GET /api/tasks` endpoint bypasses the chat loop entirely so the frontend can poll independently; a new `use-task-reminders.ts` hook (matching the `use-wake-word.ts` extraction pattern) owns notification permission and the polling interval.

**Tech Stack:** FastAPI, stdlib SQLite, pytest, Next.js/React, browser Notification API. No new dependencies.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/build/manual-verification step instead.

---

### Task 1: `due_at`/`priority` columns, `complete_task`/`delete_task` (TDD)

**Files:**
- Modify: `backend/app/services/memory.py:19-57` (`_init_db`), `:104-140` (`add_task`, `list_tasks`), append new methods after `get_google_tokens`
- Modify: `backend/tests/test_memory.py` (append)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_memory.py`, appending:
```python


def test_add_task_with_due_at_and_priority(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.add_task("default", "Call the dentist", due_at="2026-08-10T10:00:00+05:30", priority="high")

    assert result["due_at"] == "2026-08-10T10:00:00+05:30"
    assert result["priority"] == "high"


def test_add_task_defaults_priority_to_medium(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.add_task("default", "Buy milk")

    assert result["priority"] == "medium"
    assert result["due_at"] is None


def test_list_tasks_sorts_by_due_date_with_nulls_last(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.add_task("default", "No due date")
    store.add_task("default", "Due later", due_at="2026-08-15T10:00:00+05:30")
    store.add_task("default", "Due sooner", due_at="2026-08-10T10:00:00+05:30")

    tasks = store.list_tasks("default")

    assert [t["title"] for t in tasks] == ["Due sooner", "Due later", "No due date"]


def test_complete_task_marks_done(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    task = store.add_task("default", "Finish report")

    result = store.complete_task("default", task["id"])

    assert result is True
    tasks = store.list_tasks("default", include_done=True)
    assert tasks[0]["done"] is True


def test_complete_task_returns_false_for_unknown_id(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.complete_task("default", 999) is False


def test_delete_task_removes_row(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    task = store.add_task("default", "Temporary task")

    result = store.delete_task("default", task["id"])

    assert result is True
    assert store.list_tasks("default", include_done=True) == []


def test_delete_task_returns_false_for_unknown_id(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.delete_task("default", 999) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_memory.py -v
```
Expected: the 7 new tests fail — `add_task()` doesn't accept `due_at`/`priority` yet, and `complete_task`/`delete_task` don't exist.

- [ ] **Step 3: Add the new columns to the `tasks` table**

Modify `backend/app/services/memory.py`, replacing the `tasks` table creation inside `_init_db` (current lines 33-43):
```python
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    due_at TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
```

- [ ] **Step 4: Update `add_task` and `list_tasks`**

Modify `backend/app/services/memory.py`, replacing `add_task` and `list_tasks` (current lines 104-140):
```python
    def add_task(
        self, user_id: str, title: str, due_at: str | None = None, priority: str = "medium"
    ) -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required.")
        clean_priority = priority if priority in ("low", "medium", "high") else "medium"

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (user_id, title, due_at, priority) VALUES (?, ?, ?, ?)",
                (user_id, clean_title, due_at, clean_priority),
            )
            connection.commit()
            task_id = int(cursor.lastrowid)
        return {
            "id": task_id,
            "title": clean_title,
            "done": False,
            "due_at": due_at,
            "priority": clean_priority,
        }

    def list_tasks(self, user_id: str, include_done: bool = False) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if include_done:
                rows = connection.execute(
                    """
                    SELECT id, title, done, due_at, priority, created_at FROM tasks
                    WHERE user_id = ?
                    ORDER BY (due_at IS NULL), due_at ASC, created_at DESC
                    LIMIT 30
                    """,
                    (user_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, title, done, due_at, priority, created_at FROM tasks
                    WHERE user_id = ? AND done = 0
                    ORDER BY (due_at IS NULL), due_at ASC, created_at DESC
                    LIMIT 30
                    """,
                    (user_id,),
                ).fetchall()
        return [{**dict(row), "done": bool(row["done"])} for row in rows]
```

- [ ] **Step 5: Add `complete_task` and `delete_task`**

Modify `backend/app/services/memory.py`, appending these two methods after `get_google_tokens` (at the end of the class):
```python

    def complete_task(self, user_id: str, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_task(self, user_id: str, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            connection.commit()
        return cursor.rowcount > 0
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 29 passed (the 7 new tests plus the 22 from before).

---

### Task 2: Extend `add_task` and add `complete_task`/`delete_task` tools

**Files:**
- Modify: `backend/app/ai/tools.py:72-85` (`add_task` in `TOOL_DEFINITIONS`), append two new `TOOL_DEFINITIONS` entries before line 261's closing `]`, `:305-306` (`_tool_add_task`), append two new functions after `_tool_add_task`, `:607-623` (`TOOL_REGISTRY`)

These execute directly (no draft/confirm UI) since they only affect the user's own local task list — no external side effects, trivially reversible. Not unit-tested (they're thin wrappers around the already-tested `MemoryStore` methods), consistent with how `_tool_add_task`/`_tool_list_tasks` have never been unit-tested either.

- [ ] **Step 1: Extend the `add_task` tool definition**

Modify `backend/app/ai/tools.py`, replacing the `add_task` entry in `TOOL_DEFINITIONS` (current lines 72-85):
```python
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a local task or reminder-style note, optionally with a due date/time and priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title to save."},
                    "due_at": {
                        "type": ["string", "null"],
                        "description": "Optional due date/time in ISO 8601 format, e.g. 2026-08-10T10:00:00+05:30. Resolve relative dates like 'tomorrow' using get_time first.",
                    },
                    "priority": {
                        "type": ["string", "null"],
                        "description": "Optional priority: low, medium, or high. Defaults to medium if not specified.",
                    },
                },
                "required": ["title"],
            },
        },
    },
```

- [ ] **Step 2: Add the two new tool definitions**

Modify `backend/app/ai/tools.py`, adding these entries right before the closing `]` of `TOOL_DEFINITIONS` (current line 261, after the `propose_delete_calendar_event` entry):
```python
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as done. Use list_tasks first to find the task_id if you don't already know it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task to mark done."}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task permanently. Use list_tasks first to find the task_id if you don't already know it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task to delete."}
                },
                "required": ["task_id"],
            },
        },
    },
```

- [ ] **Step 3: Update `_tool_add_task` and add the two new tool functions**

Modify `backend/app/ai/tools.py`, replacing `_tool_add_task` (current lines 305-306):
```python
def _tool_add_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    due_at = args.get("due_at") or None
    priority = str(args.get("priority") or "medium")
    return store.add_task(user_id, str(args.get("title", "")), due_at=due_at, priority=priority)
```

Modify `backend/app/ai/tools.py`, appending these two functions directly after `_tool_add_task`:
```python


def _tool_complete_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    task_id = int(args.get("task_id", 0))
    ok = store.complete_task(user_id, task_id)
    if not ok:
        return {"ok": False, "message": f"I couldn't find a task with id {task_id}."}
    return {"ok": True, "message": "Task marked as done."}


def _tool_delete_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    task_id = int(args.get("task_id", 0))
    ok = store.delete_task(user_id, task_id)
    if not ok:
        return {"ok": False, "message": f"I couldn't find a task with id {task_id}."}
    return {"ok": True, "message": "Task deleted."}
```

- [ ] **Step 4: Register both tools**

Modify `backend/app/ai/tools.py`, replacing `TOOL_REGISTRY` (current lines 607-623):
```python
TOOL_REGISTRY: dict[str, ToolFunction] = {
    "get_time": _tool_get_time,
    "get_system_status": _tool_get_system_status,
    "save_memory": _tool_save_memory,
    "get_memory": _tool_get_memory,
    "add_task": _tool_add_task,
    "list_tasks": _tool_list_tasks,
    "complete_task": _tool_complete_task,
    "delete_task": _tool_delete_task,
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
python -c "from app.ai.tools import TOOL_REGISTRY; print('complete_task' in TOOL_REGISTRY, 'delete_task' in TOOL_REGISTRY)"
```
Expected: 29 tests pass; script prints `True True`.

---

### Task 3: `GET /api/tasks` endpoint

**Files:**
- Modify: `backend/app/schemas.py` (append after `DeleteEventResponse`)
- Create: `backend/app/routers/tasks.py`
- Modify: `backend/app/main.py` (full-file replacement)

- [ ] **Step 1: Add the task response schemas**

Modify `backend/app/schemas.py`, appending after the existing `DeleteEventResponse` class:
```python


class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool
    due_at: str | None = None
    priority: str = "medium"
    created_at: str


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
```

- [ ] **Step 2: Create the router**

Create `backend/app/routers/tasks.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import TaskListResponse

router = APIRouter(tags=["tasks"])


@router.get("/api/tasks", response_model=TaskListResponse)
async def list_tasks(request: Request, include_done: bool = False) -> TaskListResponse:
    store = request.app.state.memory_store
    tasks = store.list_tasks("default", include_done)
    return TaskListResponse(tasks=tasks)
```

- [ ] **Step 3: Register the router**

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
from app.routers.tasks import router as tasks_router
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
    app.include_router(tasks_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "jarvis-backend"}

    return app


app = create_app()
```

- [ ] **Step 4: Restart the backend and verify**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest "http://127.0.0.1:8000/api/tasks?include_done=false" -UseBasicParsing | Select-Object -ExpandProperty Content
python -m pytest tests/ -v
```
Expected: health check online; the tasks endpoint returns `{"tasks":[]}` (or existing tasks if any); all 29 tests pass.

---

### Task 4: Update the system prompt

**Files:**
- Modify: `backend/app/ai/provider.py:74` (tool bullet), `:104` (new rule 16)

- [ ] **Step 1: Update the tool bullets**

Modify `backend/app/ai/provider.py`, replacing the existing `add_task / list_tasks` bullet (current line 74):
```
• add_task / list_tasks — Manage the user's task list, including optional due dates and priority.
• complete_task / delete_task — Mark a task done or remove it.
```

- [ ] **Step 2: Add a new behavior rule**

Modify `backend/app/ai/provider.py`, adding a new rule 16 directly after the existing rule 15 (current line 104, immediately before the closing `"""`):
```
16. When adding a task with a due date, resolve relative dates and times (e.g. "tomorrow," "next Monday," "in an hour") using get_time first rather than guessing, the same way you already do for calendar events. Unlike calendar and email actions, complete_task and delete_task take effect immediately when called — they do not require a separate confirmation step, since they only affect the user's own local task list.
```

- [ ] **Step 3: Verify the test suite still passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 29 tests pass.

---

### Task 5: `frontend/lib/use-task-reminders.ts` (new hook)

**Files:**
- Create: `frontend/lib/use-task-reminders.ts`

Following the same extraction pattern as `use-wake-word.ts` (increment 1c) — a well-bounded, independent concern (permission handling, interval polling, notification firing) kept out of the already-large `jarvis-interface.tsx`.

- [ ] **Step 1: Create the hook**

Create `frontend/lib/use-task-reminders.ts`:
```typescript
"use client"

import { useCallback, useRef, useState } from "react"

const POLL_INTERVAL_MS = 60_000

interface ReminderTask {
  id: number
  title: string
  done: boolean
  due_at: string | null
}

export function useTaskReminders(backendUrl: string) {
  const [remindersEnabled, setRemindersEnabled] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const notifiedRef = useRef<Set<number>>(new Set())

  const checkDueTasks = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/api/tasks?include_done=false`)
      if (!res.ok) return
      const data = await res.json()
      const tasks: ReminderTask[] = data.tasks || []
      const now = Date.now()

      for (const task of tasks) {
        if (!task.due_at || notifiedRef.current.has(task.id)) continue
        const dueTime = new Date(task.due_at).getTime()
        if (Number.isNaN(dueTime) || dueTime > now) continue

        notifiedRef.current.add(task.id)
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification("JARVIS Reminder", { body: task.title })
        }
      }
    } catch {
      // Silent failure — the next poll will just retry
    }
  }, [backendUrl])

  const enableReminders = useCallback(async () => {
    if (typeof Notification === "undefined") return false
    const permission = await Notification.requestPermission()
    if (permission !== "granted") return false

    setRemindersEnabled(true)
    checkDueTasks()
    intervalRef.current = setInterval(checkDueTasks, POLL_INTERVAL_MS)
    return true
  }, [checkDueTasks])

  const disableReminders = useCallback(() => {
    setRemindersEnabled(false)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  return { remindersEnabled, enableReminders, disableReminders }
}
```

- [ ] **Step 2: Verify it type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no type errors.

---

### Task 6: Wire the "Reminders" button into `jarvis-interface.tsx`

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:4` (import), `:17` (new hook import), `:156-157` (destructure), `:413-415` (add toggle handler after `handleCancelCalendarDelete`), `:619-639` (add button after the Google button)

- [ ] **Step 1: Add the `BellRing` icon import and the hook import**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `lucide-react` import (current line 4):
```typescript
import { AudioLines, BellRing, Keyboard, Mail, Mic, Power, SendHorizonal, Volume2, VolumeX } from "lucide-react"
```

Modify `frontend/components/jarvis-interface.tsx`, adding this import directly after the existing `useWakeWord` import (current line 18):
```typescript
import { useTaskReminders } from "@/lib/use-task-reminders"
```

- [ ] **Step 2: Use the hook**

Modify `frontend/components/jarvis-interface.tsx`, adding this line directly after the existing `useWakeWord()` destructure (current lines 156-157, `const { wakeWordSupported, ... } = useWakeWord()`):
```typescript

  const { remindersEnabled, enableReminders, disableReminders } = useTaskReminders(BACKEND_URL)
```

- [ ] **Step 3: Add the toggle handler**

Modify `frontend/components/jarvis-interface.tsx`, adding this callback directly after `handleCancelCalendarDelete` (current lines 413-415):
```typescript

  const handleToggleReminders = useCallback(async () => {
    if (remindersEnabled) {
      disableReminders()
      pushSystemMessage("Reminders turned off.")
    } else {
      const ok = await enableReminders()
      pushSystemMessage(
        ok
          ? "Reminders are on — I'll notify you here in the browser when a task's due time arrives, as long as this tab stays open."
          : "Couldn't enable reminders — notification permission was denied or isn't available in this browser.",
      )
    }
  }, [remindersEnabled, enableReminders, disableReminders, pushSystemMessage])
```

- [ ] **Step 4: Add the header button**

Modify `frontend/components/jarvis-interface.tsx`, adding this button directly after the closing `</button>` of the Google button (current lines 621-639, right before the closing `</div>` of the header's button group):
```typescript

            <button
              id="reminders-toggle"
              onClick={handleToggleReminders}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                remindersEnabled
                  ? "border-accent/40 bg-accent/15 text-accent"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={remindersEnabled}
              title={
                remindersEnabled
                  ? "Reminders on — click to turn off"
                  : "Enable browser notifications for due tasks (only while this tab is open)"
              }
            >
              <BellRing className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Reminders</span>
            </button>
```

- [ ] **Step 5: Verify the frontend type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 7: End-to-end manual verification

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

- [ ] **Step 2: Add a task with a relative due date and priority**

Ask "Remind me to call the dentist tomorrow at 10am, high priority." Expected: it resolves the relative date correctly (confirming the `get_time`-first behavior). Ask "what are my tasks" to confirm it was saved with the right due date and priority.

- [ ] **Step 3: Complete and delete tasks**

Ask to mark that task done, and separately add and delete a different task. Expected: both actually change stored state — verify via "show my tasks" (should disappear/show as done accordingly).

- [ ] **Step 4: Enable reminders and verify a real notification**

Add a task with a due time a couple of minutes in the future. Click "Reminders" in the header — your browser should prompt for notification permission; allow it. Wait for the due time. Expected: a real browser notification appears while the tab is open.

- [ ] **Step 5: Verify no notification for undated or completed tasks**

Confirm a task with no due date never triggers a notification, and a task already marked done doesn't either.

- [ ] **Step 6: Disable reminders**

Click "Reminders" again to turn it off. Expected: no further notifications, even past a task's due time.

- [ ] **Step 7: Confirm nothing regressed**

Quickly re-verify a capability from an earlier increment — e.g. send a test email or ask about the calendar — to confirm this increment's changes didn't break anything prior.

- [ ] **Step 8: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- Editing an existing task's title/due date/priority in place (delete and re-add instead).
- Notification action buttons (would require a Service Worker).
- Cross-session "already notified" tracking — reopening the tab re-evaluates what's currently due/overdue.
- This closes out the productivity sequence (2a-2d). Next: a new area of `AGENT.md` entirely.

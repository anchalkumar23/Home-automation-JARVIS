# Productivity Foundation — Increment 2d: Task/Reminder Redesign

## Context

Increments 2a-2c (Gmail OAuth+send, Calendar read, Calendar write) are complete, closing out the Google-integrated half of the productivity sequence (Section 14 of `AGENT.md`). This final increment redesigns the local task system, which currently has no Google dependency at all — just a SQLite `tasks` table with `id`, `user_id`, `title`, `done`, `created_at`, and exactly two tools: `add_task(title)` and `list_tasks(include_done)`.

Confirmed by reading the code fresh: there is currently no way to mark a task done, edit it, or delete it through any tool — `done` exists as a column but nothing ever sets it. This is a real, pre-existing gap, not a deliberate scope boundary, and the user has confirmed closing it (add complete + delete) belongs in this increment. Editing an existing task's title/date is explicitly out of scope — delete-and-recreate covers that case.

The user also chose the more ambitious of two reminder options: real proactive browser notifications when a task's due time arrives, not just queryable due-date metadata. This has a real architectural consequence worth stating plainly: JARVIS is a browser-tab application with no persistent background service, so notifications only fire while the tab is actually open. This is an accepted tradeoff, not an oversight.

## Scope

**In scope:**
1. `due_at` (nullable datetime) and `priority` (`low`/`medium`/`high`, default `medium`) added to the `tasks` table and to `add_task`.
2. `complete_task(task_id)` and `delete_task(task_id)` — new AI-callable tools, added directly (no draft-confirm UI needed, unlike email/calendar) since they only affect purely local, personal, reversible data with no external side effects for anyone else.
3. `list_tasks` sorts by due date (soonest first, undated tasks last).
4. A new `GET /api/tasks` REST endpoint, bypassing the chat/AI tool-calling loop entirely — necessary because the frontend needs to check on tasks independently of a conversation turn for the notification poller to work.
5. A new opt-in "Reminders" header button (off by default, matching the existing Wake/Gmail button pattern) that requests notification permission and starts a 60-second poll of `GET /api/tasks`, firing a real browser notification for any task that's newly due and not yet completed.
6. A system-prompt addition covering the new/changed tools and reusing the established "resolve relative dates via `get_time` first" pattern from the calendar increments.

**Out of scope:**
- Editing an existing task's title, due date, or priority — delete and re-add instead.
- Notification action buttons (would require registering a Service Worker — real added complexity for a personal-use tool).
- Any "catch-up" mechanism for notifications missed while the tab was closed — reopening simply evaluates what's currently due/overdue at that moment, not a history of missed alerts.
- Persisting which tasks have already triggered a notification across sessions — tracked in-memory for the current session only, so reopening the tab after being away can re-notify for tasks that are still overdue.

## Design

### Backend: schema and storage

`backend/app/services/memory.py`'s `tasks` table gains two columns:
```sql
due_at TEXT,
priority TEXT NOT NULL DEFAULT 'medium'
```
`add_task` gains optional `due_at` (ISO 8601 datetime string or `None`) and `priority` parameters. Two new methods, `complete_task(user_id, task_id)` and `delete_task(user_id, task_id)`, both scoped to the given `user_id` (matching the existing scoping pattern on every other method in this class) so a task ID can't be manipulated across users. `list_tasks` changes its `ORDER BY` to sort by `due_at` ascending with `NULL`s last, then `created_at` as before.

### Backend: tools

`add_task`'s tool definition gains the two new optional parameters (nullable, matching the established pattern for optional tool args elsewhere in this file). Two new tools, `complete_task` and `delete_task`, each taking just `task_id`. Unlike `draft_calendar_event`/`propose_delete_calendar_event`, these execute directly — no draft/confirm step — since a wrong local task completion or deletion has no consequence beyond the user's own task list, is trivially correctable by re-adding, and doesn't notify or affect anyone else.

### Backend: `GET /api/tasks`

A new small router (`backend/app/routers/tasks.py`) exposing `GET /api/tasks?include_done=false`, calling `MemoryStore.list_tasks` directly and returning the result as JSON — a plain data read, not routed through the LLM. This is the piece that makes client-side notification polling possible at all, since polling can't reasonably go through a full chat turn every 60 seconds.

### Frontend: reminder polling

A new "Reminders" button in the header, following the same pattern as the existing Wake and Gmail buttons: off by default, click to enable. Enabling it requests `Notification.requestPermission()` (an explicit user action, consistent with how this app already gates microphone and Google access behind clicked buttons rather than auto-prompting) and, once granted, starts a `setInterval` polling `GET /api/tasks` every 60 seconds. For each returned task that has a `due_at` in the past (or exactly now) and is not `done`, the app fires `new Notification(...)` — tracked via an in-memory `Set` of already-notified task IDs for the current session, so the same task doesn't re-notify every poll cycle. Clicking the button again clears the interval and stops polling.

### System prompt

Bullet-list entries for `complete_task` and `delete_task`, an updated `add_task` bullet mentioning the new optional fields, and a rule reusing the calendar increments' established pattern: resolve relative dates ("tomorrow," "next Monday") via `get_time` before setting `due_at`, rather than guessing.

### Testing

`list_tasks`'s new sort behavior (due-date-ascending with nulls last) and the two new `MemoryStore` methods (`complete_task`, `delete_task`) are pure SQLite logic against a temp database — unit-tested the same way `save_google_tokens`/`get_google_tokens` were in increment 2b. The `GET /api/tasks` endpoint itself is a thin wrapper with no independent logic to test beyond what's already covered.

### Manual verification plan

1. Ask JARVIS to add a task with a relative due date ("remind me to call the dentist tomorrow at 10am, high priority") — confirm it resolves the date correctly (verifying the `get_time`-first behavior) and the task appears with the right due date/priority when listed.
2. Ask to mark a task done, and separately to delete a different task — confirm both actually change the stored state (verify via `list_tasks`).
3. Add a task with a due time a couple of minutes in the future, enable "Reminders," and confirm a real browser notification fires around that time while the tab is open.
4. Confirm no notification fires for a task with no due date, or for a task already marked done.
5. Disable "Reminders," confirm polling stops (no further notifications even past a task's due time).

## Explicitly deferred to future increments

- Editing existing tasks in place.
- Notification action buttons / Service Worker.
- Everything else in `AGENT.md` beyond Section 1 and the now-complete productivity sub-sequence (2a-2d).

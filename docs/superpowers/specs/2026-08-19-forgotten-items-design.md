# "What Am I Forgetting?" Mode — Increment 8a

## Context

This is the first of the client's explicitly-named "10 Core Functions" (documented in `AGENT.md`'s Guiding Philosophy section) to get built, chosen while Studio Automation (7a's live testing, and the planned lights/cameras) is blocked on client-provided device details. Built during a natural gap in the hardware-dependent work, using only existing infrastructure — no new integrations, no client input needed.

The client's original description covers a broad set of categories: pending projects, important dates, risks, commitments, documents, incomplete decisions, unresolved problems, opportunities, and cross-task dependencies. JARVIS has real, structured data for only a subset of these today — tasks, calendar events, and saved memories. There's no project tracker, document store, or decision log yet. This increment builds a genuinely useful v1 grounded in the data that actually exists, rather than a v1 that pretends to cover categories with nothing behind them; broader coverage (projects, documents, decisions) can follow once those data sources exist as their own increments (likely tied to Section 9's Long-Term Memory expansion).

## Scope

**In scope:**
1. A new `review_forgotten_items()` tool (no arguments) that gathers open tasks (categorized into overdue / upcoming / no-due-date), upcoming calendar events (next 7 days, gracefully noting if Calendar isn't connected), and all saved memories — returning the raw gathered data, not a pre-judged summary.
2. A pure, unit-tested helper categorizing tasks by due date relative to now.
3. A new system prompt rule: after calling `review_forgotten_items`, synthesize what's genuinely worth flagging and present it via the **existing** `create_business_report` tool (topic: "What You Might Be Forgetting") — reusing the card mechanism already built for business reports, rather than building a new one.
4. Honest "nothing to report" behavior: if nothing stands out, say so in a short spoken reply rather than calling `create_business_report` with manufactured filler — matching the client's own "Global Radar" principle from the Guiding Philosophy section that "nothing important today" is a valid, good answer.

**Out of scope:**
- Projects, documents, decisions, risks, or opportunities as their own tracked data — there's no data source for these yet. Only tasks, calendar, and memories are reviewed in this increment.
- Any new schema fields, new `ClientAction` type, or new frontend component — this increment reuses `create_business_report`'s existing card entirely.
- Proactive/scheduled triggering (e.g. running automatically every morning) — this is an on-command tool for now, matching the on-demand precedent set by every other feature built so far (search, news, business reports). A scheduled/background version could be a later increment once this on-demand version is tested.

## Design

### Tool: `review_forgotten_items`

`backend/app/ai/tools.py` gains `_tool_review_forgotten_items(args, user_id, store)`:

1. Calls the existing `_tool_list_tasks({"include_done": False}, user_id, store)` and `_tool_list_calendar_events({"days": 7}, user_id, store)` functions directly (as plain Python function calls, not through the LLM tool-calling loop) — reusing their exact existing logic rather than duplicating it, and staying automatically in sync if those tools' behavior changes later.
2. Calls `store.list_memories(user_id)` directly for the full memory list.
3. Categorizes the open tasks via a new pure helper, `_categorize_tasks_by_due_date(tasks, now)`, splitting them into `overdue`, `upcoming`, and `no_due_date` buckets by comparing each task's `due_at` (ISO 8601, offset-aware) against `now`.
4. Returns `{overdue_tasks, upcoming_tasks, no_due_date_tasks, upcoming_calendar_events, calendar_connected, saved_memories}` — raw data, no LLM-style judgment happens in the tool itself; that's the model's job per the new system prompt rule (consistent with how `web_search`/`get_news` results are synthesized by rule 9, not by the tool).

This is a read-only tool with no side effects — no confirmation gate needed, the same tier as `list_tasks`/`get_memory`.

### Tool definition

```
name: review_forgotten_items
description: "Gather open tasks, upcoming calendar events, and saved memories for a 'what am I forgetting' review."
parameters: {} (no arguments)
```

### Pure helper (TDD)

```
_categorize_tasks_by_due_date(tasks: list[dict], now: datetime) -> dict
```
Returns `{"overdue": [...], "upcoming": [...], "no_due_date": [...]}`. A task with no `due_at`, or one that fails to parse, goes into `no_due_date` rather than raising — this data originates from user-entered tasks, some of which legitimately have no due date by design (per the existing task feature).

### System prompt

A new numbered rule: when the user asks what they're forgetting, or wants an open-items check-in, call `review_forgotten_items`, then look at the returned overdue tasks, upcoming events, and memories, and decide what's genuinely worth flagging (not everything returned needs to be surfaced — most tasks/memories are unremarkable). Present anything worth flagging via `create_business_report` (topic "What You Might Be Forgetting", one section per flagged item). If nothing stands out, say so in a brief spoken reply instead of calling the report tool.

### Testing

`_categorize_tasks_by_due_date` gets unit tests: overdue vs. upcoming split relative to a fixed `now`, tasks with no due date, and tasks with an unparseable `due_at` falling back to `no_due_date` rather than crashing. `_tool_review_forgotten_items` itself is not unit-tested (it's a thin composition of already-tested/network-touching pieces), consistent with this project's established convention.

### Manual verification plan

1. With a mix of overdue tasks, upcoming tasks, tasks with no due date, at least one near-term calendar event, and a few saved memories in place, ask "what am I forgetting?" Confirm JARVIS calls `review_forgotten_items`, then produces a "What You Might Be Forgetting" report card with genuinely relevant flagged items — not a dump of every task/memory verbatim.
2. Clear out tasks/events/memories (or use a fresh state) and ask again. Confirm JARVIS says something like "nothing stands out" rather than fabricating a report.
3. Ask the same question while Google Calendar isn't connected. Confirm the tool doesn't error out — calendar data is simply absent/noted as unavailable, tasks and memories still get reviewed.
4. Confirm the spoken/text reply itself stays voice-safe (brief summary, no bullets), with the detail living in the report card, consistent with how business reports already work.
5. Quickly re-verify plain task listing, calendar listing, and business reports still work unaffected.

## Explicitly deferred to future increments

- Projects, documents, decisions, risks, opportunities as tracked data sources.
- Scheduled/proactive triggering (e.g. a daily automatic check-in).
- Other "10 Core Functions" (Early Warning System, Opportunity Engine, Second Brain, Error Detector, Decision Simulator, Global Radar, Time Manager, Autonomous Builder, Learning System) — each would need its own scoping pass given the same "what real data actually exists" honesty check applied here.

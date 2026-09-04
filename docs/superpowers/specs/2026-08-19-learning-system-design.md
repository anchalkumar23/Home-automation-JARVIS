# Learning System (lightweight v1) — Increment 8e

## Context

The ninth of the client's "10 Core Functions" (`AGENT.md`, item 9): "track which recommendations worked and which didn't, and use that history to weight future recommendations toward what has actually worked for this user." Built on-demand/conversationally, no new external service, no frontend change — feedback is inferred from the conversation rather than an explicit UI control (confirmed trade-off: less than 100% reliable, but zero frontend work, consistent with every increment since 8a).

## Scope

**In scope:**
1. A new `recommendation_feedback` table: `id, user_id, recommendation_type, topic, outcome, created_at`.
2. A new write-only tool, `record_recommendation_feedback(recommendation_type, topic, outcome)`, called when the user's message immediately following a report card (Opportunities/Stress-Test/Decision-Simulation/What You Might Be Forgetting) clearly signals acceptance or dismissal.
3. Recent feedback patterns folded into the existing `build_known_facts_block`-style context injection (a new sibling block, not a new tool call) — so the model sees a short summary of recent accept/dismiss patterns on every turn without spending a round trip.
4. A rule: when about to generate a recommendation of a type/topic recently dismissed, ask before re-surfacing it rather than repeating it blind; lean into angles that were previously accepted.

**Out of scope:**
- Any real weighting/scoring algorithm — v1 is "mention the pattern in context and let the model factor it in naturally," not a trained model or numeric score.
- An explicit thumbs up/down UI control — deferred; conversational inference only, per the confirmed feedback-signal decision.
- Feedback tracking for anything other than the four existing report-card types (create_content drafts, calendar actions, etc. are not "recommendations" in this sense and are out of scope).

## Design

### Schema (`backend/app/services/memory.py`)

```sql
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    topic TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

`recommendation_type` ∈ `{opportunity, stress_test, decision_simulation, forgotten_items}`. `outcome` ∈ `{accepted, dismissed}`. No migration helper needed — this is a brand-new table, `CREATE TABLE IF NOT EXISTS` alone is sufficient (unlike the `memories.category` column, which needed `ALTER TABLE` because it was added to an existing table).

### Store methods

- `record_recommendation_feedback(user_id, recommendation_type, topic, outcome) -> dict` — validates `outcome` is one of the two allowed values (default to `"neutral"`-free — invalid values are rejected the same way `add_task`'s `priority` falls back to a safe default today), inserts, returns the row.
- `recent_feedback_summary(user_id, limit=10) -> list[dict]` — last N feedback rows, most recent first. Used to build the context block, not exposed as an LLM tool.

### Tool definition (`backend/app/ai/tools.py`)

```
name: record_recommendation_feedback
description: "Log whether the user accepted or dismissed a prior recommendation."
parameters: recommendation_type (string), topic (string), outcome (string: accepted/dismissed)
```

### Context injection (`backend/app/ai/provider.py`)

A new function alongside `build_known_facts_block`, e.g. `build_feedback_patterns_block(feedback_rows) -> str`, producing something like:

```
Recent recommendation feedback (factor this in naturally, don't recite it):
- Dismissed: EV-market opportunities (x2)
- Accepted: studio-automation stress-tests
```

Appended to the system prompt in `build_messages`, same place `known_facts` is appended today.

### System prompt rule

Extends rule 14 (the existing reflective-requests rule) or adds a short new one: when generating a reflective-request recommendation, check the feedback pattern block first — if a similar type/topic was recently dismissed, ask before re-surfacing rather than repeating it; if a type was recently accepted, keep applying that lens. Also: after presenting one of the four report-card types, if the user's very next message clearly accepts or dismisses it, call `record_recommendation_feedback`.

### Token budget

Adds one small tool schema (~120-150 chars) plus a rule extension (~150-200 chars). Current headroom is 24 characters — this will need another trim pass, continuing the pattern from 8b-8d. If trimming alone can't cover it, another rule-merge (like the 8c consolidation) is the fallback, not raising the ceiling.

### Testing

- `MemoryStore.record_recommendation_feedback` / `recent_feedback_summary` get unit tests in `test_memory.py`: recording accepted/dismissed, retrieving in recency order, limiting to N rows.
- `build_feedback_patterns_block` gets unit tests in the provider test file (or wherever `build_known_facts_block` is tested — verify before writing): empty feedback returns empty string, dismissed items are summarized, accepted items are summarized.
- Existing token-budget guard tests must still pass.

### Manual verification plan

1. Ask for an opportunity search, then respond dismissively ("not relevant to me"). Confirm the feedback gets logged (verify via a direct memory-store check or by re-asking a related question later in the same session and observing JARVIS reference it).
2. Ask JARVIS about a similar/related opportunity topic again. Confirm it asks before re-surfacing rather than repeating the dismissed angle blind.
3. Ask for a stress-test and respond positively ("great catch, let's fix that"). Confirm it's logged as accepted.
4. Confirm the feedback-pattern block doesn't leak into JARVIS's spoken replies — no recitation of raw feedback data, only natural, occasional use of the pattern.
5. Quickly re-verify Opportunity Engine, Error Detector/Decision Simulator, and "What Am I Forgetting?" still work unaffected.

## Explicitly deferred to future increments

- Explicit thumbs up/down UI control (more reliable signal, needs frontend work).
- Real weighting/scoring rather than "mention the pattern and let the model factor it in."
- Feedback tracking for content drafts, calendar actions, or other non-report-card outputs.

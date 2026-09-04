# Second Brain (lightweight v1) — Increment 8d

## Context

The third of the client's "10 Core Functions" (`AGENT.md`, item 3): "automatically organize everything important into a personal knowledge map (people → projects → documents → decisions → goals → results), so past reasoning can be reconstructed on request." Built on-demand using the existing memory store — no new table, no knowledge graph, no new frontend.

## Scope

**In scope:**
1. A nullable `category` column on the existing `memories` table (`person` / `project` / `document` / `decision` / `goal` / unset → treated as `general`).
2. `save_memory` gains an optional `category` argument.
3. `get_memory` gains an optional `category` filter, combinable with the existing `query` text filter.
4. A prompt-rule addition: JARVIS tags a category when saving something that clearly fits one, and when asked "what do I know about X" or "why did we decide X," queries by category/text and synthesizes an organized answer rather than reciting a flat list.

**Out of scope:**
- A real graph/relationships between entries (e.g. linking a decision to the project it belongs to) — categories are a flat tag, not edges. If cross-references turn out to matter in practice, that's a future increment.
- A "results" category — outcomes are expected to live in the free-text `value` of a `decision`/`goal` entry rather than as a separate tracked type, avoiding a category that has no clear trigger for when to use it.
- Backfilling categories onto memories saved before this change — they simply have `category = NULL` (treated as `general`) going forward; no migration script needed for a handful of existing rows in a per-user local SQLite file.

## Design

### Schema (`backend/app/services/memory.py`)

`CREATE TABLE IF NOT EXISTS memories` gains `category TEXT` (nullable, no default needed — `NULL` is read back as `"general"` at the Python layer, not the SQL layer, keeping the migration trivial for existing rows).

Since this project doesn't use a migration framework, existing databases need the column added via `ALTER TABLE` guarded by a check (SQLite has no `ADD COLUMN IF NOT EXISTS`), run once at connection setup alongside the existing `CREATE TABLE IF NOT EXISTS` calls.

### `save_memory(user_id, key, value, category=None)`

`INSERT ... ON CONFLICT` extended to also set `category`. A `None`/empty category is stored as `NULL`.

### `list_memories(user_id, query=None, category=None)`

Extends the existing `WHERE` clause with an optional `AND category = ?` (or `AND category IS NULL` when the caller asks for `general` — decide by checking whether `category` is the literal string `"general"`, mapped to `IS NULL`, versus one of the other four values, mapped to `= ?`). Combinable with the existing text `query`.

### Tool definitions (`backend/app/ai/tools.py`)

- `save_memory`: add `category` to `parameters.properties`, type `["string", "null"]`, short description listing the five values.
- `get_memory`: add `category` to `parameters.properties`, same type/description, filters in addition to `query`.
- `_tool_save_memory` / `_tool_get_memory` pass the new arg through to the store methods.

### System prompt

Extend the existing `save_memory`/`get_memory` bullet (not rule 1, which is about facts already injected into context) to mention categorization, and note in the reflective-requests rule (rule 14, already covering forgetting/opportunities/stress-tests) that "what do I know about X" / "why did we decide X" questions also route through `get_memory` with category/query filters and get synthesized, not recited.

### Token budget

Adds two small param schemas (~90-120 chars each) plus a short bullet/rule extension. Current headroom is ~87 chars — this will need another trim pass, but the addition itself is small (no new tool, no new `TOOL_DEFINITIONS` entry).

### Testing

- `MemoryStore.save_memory`/`list_memories` category behavior gets unit tests in the existing `test_memory.py` (or wherever the current memory store tests live — verify exact file before writing): saving with a category, filtering by category, filtering by category="general" returning NULL-category rows, and combining category + text query.
- Existing token-budget guard tests in `test_provider.py` must still pass.

### Manual verification plan

1. Tell JARVIS something clearly about a person, project, and a decision in three separate messages (e.g. "Sarah is the lead on Project X," "we chose direct TV integration over Home Assistant for full source ownership," "Project X launches in October"). Confirm each gets saved (no visible category in the reply — this is an internal tag, not a spoken detail).
2. Ask "what do I know about Project X?" Confirm the answer pulls the person/project/goal entries related to Project X and synthesizes them, not a flat recitation of every saved memory.
3. Ask "why did we decide to skip Home Assistant?" Confirm JARVIS recalls the decision entry and explains the reasoning, using the timestamp to answer "when" if asked.
4. Save something generic with no clear category (e.g. "I prefer dark mode"). Confirm it still saves and is still recallable normally — uncategorized memories aren't broken or excluded from plain queries.
5. Quickly re-verify plain `save_memory`/`get_memory` behavior (no category involved) still works exactly as before.

## Explicitly deferred to future increments

- Relationships/links between entries (a real knowledge graph).
- A dedicated "results/outcomes" tracking type.
- Any UI for browsing the knowledge map visually (currently voice/chat-only, same as everything else).

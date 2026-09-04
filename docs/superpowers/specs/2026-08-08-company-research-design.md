# Business Intelligence — Increment 4b: Company/Competitor Research

## Context

This is the second sub-increment of Business Intelligence (§15), following 4a (real-time market data). Unlike 4a, this one needs no new backend tool — JARVIS already has `web_search`, `read_url_content`, and `get_news` from the Internet Intelligence sequence (3a-3d). The gap is behavioral: nothing currently tells the model to research a company thoroughly (multiple angles, then synthesis) rather than answering from a single shallow search.

- **4a (done)**: Real-time market data.
- **4b (this increment)**: Company/competitor research — reusing existing tools with a new system prompt rule.
- **Later**: Business reports (synthesis of data + research, once both exist and are tested).
- **Blocked, deferred**: Sales insights / customer analytics — no CRM or sales data source connected; needs client input first.

## Scope

**In scope:**
1. A new system prompt rule directing the model to run a multi-angle research pass (overview, recent news, funding/market position) when asked about a company or competitor, optionally reading the most relevant result in depth via `read_url_content`, then synthesizing a spoken briefing — reporting only what was actually retrieved, never fabricating facts or financials.
2. A real bug fix this surfaces: `jarvis-interface.tsx`'s `searchSources()` helper currently uses `.find()`, which only captures the **first** search-shaped tool call in a reply. Multi-angle research means the model may call `web_search` 2-3 times in one turn, so the Sources card would silently drop all but the first call's results. Fixed to aggregate results from every search-shaped tool call in a reply, deduplicated by URL.

**Out of scope:**
- Any new backend tool — this increment is prompt-only plus one frontend fix.
- Business reports (structured, saved, or exportable summaries) — a later sub-increment.
- Sales insights / customer analytics — blocked pending client input.

## Design

### System prompt rule

A new numbered rule (appended after rule 19 from 4a) instructs: when the user asks to research a company, competitor, or product, don't rely on a single generic search — run a few different search angles (what the company does, recent news/developments, funding or market position/competitors) using `web_search`, and if one result looks like the authoritative source (official site, a substantial recent article), read it in full with `read_url_content` before answering. Synthesize into a short spoken briefing covering what was actually found; if information on a specific angle (e.g. funding) isn't found, say so rather than guessing or fabricating numbers.

This directly reuses rule 18's existing "synthesize into spoken sentences, don't recite a list" guidance — no need to duplicate that instruction, just point research behavior at using multiple searches before synthesizing.

### Frontend fix: aggregate sources across multiple search calls

`searchSources(msg)` in `frontend/components/jarvis-interface.tsx` currently does:
```tsx
const call = msg.toolsUsed?.find((t) => SOURCE_TOOL_NAMES.has(t.name) && t.ok)
```
This returns only the first matching tool call's results. It's rewritten to `.filter()` across all matching calls in the reply, flatten their `results` arrays, and deduplicate by `url` (since different search angles might surface the same page, e.g. the company's official site appearing in more than one query). The `SearchSourcesCard` component itself is unchanged — it already renders whatever list it's given.

### Testing

No new backend logic, so no new backend tests. The frontend change is a small, pure array transformation — verified manually (ask a multi-angle research question, confirm the Sources list includes results from more than one underlying search, not just the first).

### Manual verification plan

1. Ask "Research `<a real, findable company>` for me" — confirm the reply covers more than a single generic fact: what they do, something recent, and (if findable) funding/market position — not a one-line shallow answer.
2. Confirm the Sources list under the reply includes links from more than one distinct search (not just whatever the first `web_search` call happened to return).
3. Ask about a company/topic where funding or a specific angle genuinely isn't findable — confirm JARVIS says it couldn't find that specific piece, rather than inventing a number.
4. Confirm the reply still reads as natural spoken sentences (no bullets, no recited list), consistent with rule 18.
5. Quickly re-verify a single plain `web_search` query (not company research) still shows its Sources correctly — confirming the aggregation fix didn't break the single-call case.

## Explicitly deferred to future increments

- Business reports.
- Sales insights / customer analytics (blocked pending client input on data source).

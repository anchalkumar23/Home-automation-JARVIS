# Internet Intelligence — Increment 3c: Upgraded News Monitoring

## Context

This is the third step in the Internet Intelligence sequence, following 3a (real web search via Tavily) and 3b (webpage/PDF reading). Today, `get_news` scrapes Google News RSS with a Reddit JSON fallback, returning a bare list of headline titles (with links, but no summaries or synthesis). Section 6-7 of `AGENT.md` calls for "cited summaries," not a raw title list.

- **3a (done)**: Real web search.
- **3b (done)**: Webpage/PDF reading.
- **3c (this increment)**: Upgraded news monitoring — richer, on-demand summaries with cited sources.
- **3d**: YouTube/research paper/patent search.

Per the confirmed decision, this stays **on-demand only** (triggered by asking, e.g. "what's the news on X") — proactive background monitoring/subscriptions with notifications is a larger feature explicitly deferred, not part of this increment.

## Scope

**In scope:**
1. `_tool_get_news` rewritten to call Tavily's `/search` endpoint with `topic: "news"` (and `days: 3` for recency), replacing the current Google News RSS + Reddit scraping entirely.
2. `_parse_tavily_response` (from 3a) gains a `published` field per result, since news results carry a publish date that general web results usually don't.
3. A new system prompt rule directing the model to synthesize multiple news results into a short spoken summary, not recite a list of titles.
4. A fix to `local_answer_from_tool`'s `get_news` branch, which currently reads the old `headlines` field — same fix pattern as 3a's `web_search` branch.
5. Reuse of the existing `SearchSourcesCard` frontend component (from 3a) for `get_news` replies too, since the response shape is now identical — a one-line change to the tool-name check that decides whether to show it.
6. Updated `get_news` tool description text.

**Out of scope:**
- Proactive background monitoring, saved topic subscriptions, or browser notifications for news — a larger feature, deferred.
- Any change to `web_search` or `read_url_content` themselves (beyond the shared `_parse_tavily_response` field addition).
- A dedicated news-only UI component — the reused `SearchSourcesCard` covers it.

## Design

### Tool rewrite

`_tool_get_news` in `backend/app/ai/tools.py` no longer parses XML or hits Reddit. It builds a Tavily query (`topic` argument if given, else `"top world news today"`) and calls `POST https://api.tavily.com/search` with `{"query": ..., "topic": "news", "days": 3, "max_results": 5, "include_answer": "basic"}`, using the same request pattern already established for `_tool_web_search` (not factored into a shared helper — per this project's convention, shared utilities are only extracted once something is reused 3+ times, and this is the second use). The response is parsed with the existing `_parse_tavily_response(data, query)` helper, returning the same `{query, answer, results, message}` shape `web_search` already returns. If no API key is configured or the request fails, a clear message is returned, matching `web_search`'s existing error-handling pattern.

### Shared helper: `published` field

`_parse_tavily_response` gains one additional field per result: `"published": item.get("published_date", "")`. General web search results (from `web_search`) simply won't have this populated; news results (from `get_news`) will. This is a backward-compatible addition to the existing helper — no consumer of the old shape breaks, since it's an added key, not a renamed or removed one.

### System prompt

A new numbered rule instructs the model: when `get_news` or `web_search` returns multiple results, synthesize them into a short spoken summary of what's happening, citing what each source says in plain sentences — not a recited list of titles. This reinforces the existing no-bullet-points voice rule (14) and directly implements AGENT.md's "cited summaries" requirement.

### Local-fallback mode

`local_answer_from_tool`'s `get_news` branch is updated to read `answer`/`results` instead of the old `headlines` field, mirroring the exact fix already applied to the `web_search` branch in 3a.

### Frontend

`jarvis-interface.tsx`'s `searchSources()` helper (which currently only matches `t.name === "web_search"` to decide whether to show the `SearchSourcesCard`) is updated to also match `t.name === "get_news"`. No new component is created — the existing "Sources" list already renders title/domain links correctly for either tool's results, since both now return the identical shape.

### Testing

The existing `_parse_tavily_response` unit tests (from 3a) are updated to assert the new `published` field is present (empty string when absent, populated when the source data includes `published_date`). No new test file is needed — this increment reuses already-tested code rather than adding new pure logic. The actual Tavily network call stays manually verified, consistent with every other tool in this codebase.

### Manual verification plan

1. Ask "What's the latest news on `<a real, currently active topic>`?" — confirm a real spoken summary (not a bare title list) with a "Sources" link list underneath showing real, recent articles.
2. Ask for general news with no topic ("what's happening in the news today") — confirm it still works and returns current headlines.
3. Confirm the reply doesn't contain bullet points or a recited list — it should read as natural spoken sentences.
4. Temporarily break `TAVILY_API_KEY` and ask for news — confirm a clear error message, not a crash, and no stale RSS fallback silently kicking in (since that code path no longer exists).
5. Confirm `web_search` (3a) and `read_url_content` (3b) still work unaffected.

## Explicitly deferred to future increments

- Proactive background news monitoring / topic subscriptions / notifications.
- 3d: YouTube/research paper/patent search.

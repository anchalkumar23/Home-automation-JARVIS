# Internet Intelligence — Increment 3d: YouTube/Research Paper/Patent Search

## Context

This is the fourth and final step in the Internet Intelligence sequence, following 3a (web search), 3b (webpage/PDF reading), and 3c (news monitoring). It closes out Sections 6-7 of `AGENT.md` by adding three more specialized search capabilities: YouTube videos, research papers, and patents.

- **3a (done)**: Real web search.
- **3b (done)**: Webpage/PDF reading.
- **3c (done)**: Upgraded news monitoring.
- **3d (this increment)**: YouTube video search, research paper search, patent search.

Prior-art research for each data source (matching this project's established practice of researching before building):

- **YouTube**: the official YouTube Data API v3 remains the best option — real video metadata (title, channel, publish date), free tier of 10,000 quota units/day, and a `search` call costs 100 units, giving roughly 100 free searches/day. No self-service way to raise this without a manual Google review, which is fine for personal use.
- **Research papers**: Semantic Scholar's Graph API is free with no API key or signup required for the search endpoint used here, covering ~200 million papers with abstracts, authors, and publication years across all disciplines — a good general-purpose fit for a personal research assistant.
- **Patents**: the USPTO's legacy free PatentsView API is mid-transition to a new Open Data Portal API that now requires a registered USPTO.gov account with ID.me identity verification to obtain a key — too heavy a setup for this narrow a use case. Per the confirmed decision, patent search instead reuses the already-configured Tavily API, scoped with `site:patents.google.com`.

## Scope

**In scope:**
1. `search_youtube` tool — calls YouTube Data API v3, returns real video results.
2. `search_papers` tool — calls Semantic Scholar's Graph API, returns real paper results.
3. `search_patents` tool — reuses Tavily, scoped to Google Patents.
4. A new `youtube_api_key` setting (manual one-time setup: enable YouTube Data API v3 and create a plain API key in the same Google Cloud project already used for Gmail/Calendar OAuth).
5. A shared `_call_tavily(settings, payload)` helper, extracted now that the Tavily request pattern is used a third time (`web_search`, `get_news`, `search_patents`) — crossing this project's own "extract at 3+ uses" threshold. `_tool_web_search` and `_tool_get_news` are updated to use it; their behavior and return shapes are unchanged.
6. All three new tools return the same `{query, answer, results: [{title, url, snippet, published}], message}` shape already used by `web_search`/`get_news`, so the existing `SearchSourcesCard` frontend component and `searchSources()` helper cover them with a small list extension — no new UI component.
7. System prompt: three new tool bullets, and the existing "synthesize into spoken sentences, don't recite a list" rule (rule 18, from 3c) extended to name all five search-shaped tools.

**Out of scope:**
- Any change to `web_search`'s or `get_news`'s external behavior (the shared-helper extraction is internal only).
- Local-fallback heuristic branches for these three new tools — given their narrower, more specific phrasing ("search YouTube for...", "find papers about...", "search patents for..."), they're reachable through the AI provider path; local (no-AI-provider) fallback for them is deferred rather than adding three more heuristic branches to an already-long dispatcher, consistent with this project's minimal-footprint approach. (`local_answer_from_tool` doesn't strictly need branches for tools that are never dispatched locally — if reached via a future path, it falls through to the existing generic `"Done."` fallback.)
- Video/paper/patent content reading (that's `read_url_content`'s job already, from 3b, if the user wants to dig into a specific result).

## Design

### `search_youtube`

Calls `GET https://www.googleapis.com/youtube/v3/search` with `part=snippet&type=video&maxResults=5&q=<query>&key=<youtube_api_key>`. The response-shaping logic is pulled into a pure function, `_parse_youtube_results(data) -> list[dict]`, mapping each item to `{title, url: f"https://www.youtube.com/watch?v={videoId}", snippet: channelTitle, published: publishedAt}`. If `youtube_api_key` isn't configured, the tool returns a clear "not configured" message rather than failing opaquely.

### `search_papers`

Calls `GET https://api.semanticscholar.org/graph/v1/paper/search` with `query=<query>&limit=5&fields=title,abstract,url,year,authors`. No API key needed. The response-shaping logic is pulled into `_parse_semantic_scholar_results(data) -> list[dict]`, mapping each paper to `{title, url, snippet: "<authors> · <year>" (or a trimmed abstract if authors/year are missing), published: str(year)}`.

### `search_patents`

Builds a Tavily query of `f"{query} site:patents.google.com"` and calls the new shared `_call_tavily` helper, then reuses `_parse_tavily_response` for the result shape — identical pattern to `web_search`/`get_news`, just with the query scoped to patents.

### Shared helper: `_call_tavily`

```
_call_tavily(settings: Settings, payload: dict) -> dict
```
Performs the `urllib` POST to `https://api.tavily.com/search` with the `Authorization: Bearer` header, returning the parsed JSON or raising on failure. `_tool_web_search`, `_tool_get_news`, and `_tool_search_patents` each build their own payload and error-handling messages around this shared call — the extraction only touches the network/parsing plumbing, not each tool's distinct query-building or error text.

### Configuration

`backend/app/config.py` gains `youtube_api_key: str`, read from `YOUTUBE_API_KEY`, following the exact pattern already used for `tavily_api_key`. `.env`/`.env.example` gain the corresponding entry. Getting the actual key is a manual, one-time step in the Google Cloud Console (same project as the existing Gmail/Calendar OAuth credentials) — enable "YouTube Data API v3," create an API key (not OAuth credentials), and paste it in.

### System prompt

Three new tool bullets (`search_youtube`, `search_papers`, `search_patents`) are added to the tool list. Rule 18 (from 3c: "synthesize multiple results into a short spoken summary, don't recite a list") is reworded to name all five search-shaped tools (`web_search`, `get_news`, `search_youtube`, `search_papers`, `search_patents`) instead of just the original two, since the same reasoning applies to all of them.

### Frontend

`jarvis-interface.tsx`'s `searchSources()` helper, which currently matches `t.name === "web_search" || t.name === "get_news"`, is updated to check membership in a small constant list of source-tool names instead of a growing chain of `||` comparisons — covering all five tools now. No new component; `SearchSourcesCard` already renders title/domain/link correctly for any of them.

### Testing

`_parse_youtube_results(data)` and `_parse_semantic_scholar_results(data)` get unit tests: correct extraction from a representative response, and graceful handling of an empty/missing-fields response. `_call_tavily` and the real network calls in all three tools are not unit-tested, consistent with this project's established convention — only pure parsing/shaping logic gets tests; live network calls are verified manually.

### Manual verification plan

1. Ask "Find some YouTube videos about `<a real topic>`." Confirm real video titles/channels come back, with a Sources list of clickable YouTube links.
2. Ask "Find research papers about `<a real topic>`." Confirm real paper titles/authors/years, with a Sources list of clickable links.
3. Ask "Search for patents on `<a real topic>`." Confirm plausible patent-related results (via the Google Patents-scoped Tavily search).
4. Confirm the reply for each reads as a short spoken summary, not a recited list of titles (per rule 18).
5. Temporarily remove/break `YOUTUBE_API_KEY` and ask for a YouTube search — confirm a clear "not configured" message, not a crash.
6. Confirm `web_search`, `get_news`, and `read_url_content` (3a-3c) all still work unaffected by the shared `_call_tavily` refactor.

## Explicitly deferred to future increments

- Local-fallback heuristic branches for these three tools.
- Anything beyond Sections 6-7 of `AGENT.md` — this closes out the Internet Intelligence sequence.

# Internet Intelligence — Increment 3a: Real Web Search

## Context

This begins Sections 6-7 of `AGENT.md` (Research Assistant / Internet Intelligence), following the now-complete productivity sequence (2a-2d). That phase is too broad for one increment — real web search, webpage/PDF reading, upgraded news monitoring, and YouTube/paper/patent search are distinct capabilities — so it's decomposed the same way Productivity became 2a-2d:

- **3a (this increment)**: Real web search, replacing the current DuckDuckGo instant-answer tool.
- **3b**: Read a specific webpage/PDF's actual content.
- **3c**: Upgraded, topic-based news monitoring with cited summaries.
- **3d**: YouTube/research paper/patent search.

Today, `web_search` calls DuckDuckGo's free instant-answer API — built for quick factual lookups ("capital of France"), not general web search, and frequently returns empty results for anything more complex. Research into current (2026) free web search APIs found: Brave killed its free tier in February 2026, Google's Custom Search JSON API is being fully deprecated by January 2027, SerpAPI's free tier (250/month) is too low for daily use, and Bing Search API was retired in August 2025. **Tavily** — an API purpose-built for LLM/agent use — offers 1,000 free searches/month, permanent, no card required, comfortably covering personal daily use, with a response format already shaped for feeding directly to an LLM (clean per-result `title`/`url`/`content`, plus an optional pre-summarized `answer` field).

## Scope

**In scope:**
1. A new `TAVILY_API_KEY` setting, following the existing env-var configuration pattern.
2. `_tool_web_search` rewritten to call Tavily's `/search` endpoint instead of DuckDuckGo, with the JSON-shaping logic split into a small, unit-tested pure helper.
3. A fix to the local-fallback mode's `web_search` result formatting, which currently reads DuckDuckGo-specific fields that won't exist in Tavily's response shape — left unfixed, local mode would silently break for search after this change.
4. An updated tool description so the model's understanding of the tool's capability (now real search, not an instant-answer lookup) stays accurate.

**Out of scope:**
- Reading the actual content of a found page (3b).
- Any change to `get_news` (Google News RSS + Reddit) — that's 3c.
- A fallback to DuckDuckGo if Tavily fails — per the confirmed decision, Tavily fully replaces it; a failed call reports a clear error instead of silently degrading to weaker results.

## Design

### Configuration

`backend/app/config.py` gains `tavily_api_key: str`, read from `TAVILY_API_KEY`, following the exact pattern already used for `google_client_id` etc. `backend/.env` and `.env.example` gain the corresponding blank/documented entry. Getting the actual key is a manual, one-time step (free signup at tavily.com, no card required) performed by the user, the same way the Google Cloud Console setup was handled in increment 2a.

### Tool rewrite

`_tool_web_search` in `backend/app/ai/tools.py` calls `POST https://api.tavily.com/search` with header `Authorization: Bearer <TAVILY_API_KEY>` and body `{"query": ..., "max_results": 5, "include_answer": "basic"}`. `"basic"` answer mode gives a concise summary without the extra cost/latency of `"advanced"`. The response-shaping logic — extracting `title`/`url`/`content` from Tavily's `results` array, and the top-level `answer` string — is pulled into a small pure function, `_parse_tavily_response(data, query) -> dict`, callable and testable independently of the network request itself. If no API key is configured, the tool returns a clear "not configured" message rather than failing opaquely; if the request itself fails (network, rate limit, auth error), the tool returns a clear error message describing what happened.

### Local-fallback fix

`backend/app/ai/provider.py`'s `local_answer_from_tool` function currently formats a `web_search` result by reading `data.get("abstract")`, `data.get("heading")`, and `data.get("related")` — all DuckDuckGo-specific fields absent from Tavily's response shape. This block is updated to read the new `answer`/`results` shape instead (prefer the pre-summarized `answer` if present, otherwise the first result's title and snippet), so local mode (used when no AI provider is reachable) continues to degrade gracefully rather than silently breaking.

### Testing

`_parse_tavily_response` gets unit tests: extracting results and the answer field correctly from a representative response, and handling an empty/missing-fields response without erroring. The actual `urllib` call to Tavily is not unit-tested, consistent with how every other network-calling tool in this codebase (`get_news`, `_tool_list_calendar_events`, etc.) has always been handled — verified manually instead.

### Manual verification plan

1. Ask a query DuckDuckGo's instant-answer API would typically fail on (something needing real ranked results, not a quick factual lookup) — confirm relevant results with real titles/URLs/snippets come back, plus a coherent summarized answer.
2. Ask a simple factual query too, to confirm the basic case still works well.
3. Temporarily use an invalid API key (or none) to confirm the "not configured" / error path produces a clear message rather than a crash or silent failure.

## Explicitly deferred to future increments

- 3b: Webpage/PDF reading.
- 3c: Upgraded news monitoring.
- 3d: YouTube/research paper/patent search.
- Everything else in `AGENT.md` beyond Section 1, the productivity sub-sequence, and this internet-intelligence sub-sequence.

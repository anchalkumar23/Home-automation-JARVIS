# Internet Intelligence — Increment 3b: Webpage/PDF Reading

## Context

This is the second step in the Internet Intelligence sequence, following 3a (real web search via Tavily). Today, `web_search` can find pages about a topic, but JARVIS has no way to read what a specific page or PDF the user already has a link to actually says — it can only guess from a search snippet. This increment closes that gap: given a URL, JARVIS fetches the real content and can summarize it, answer questions about it, or discuss it.

- **3a (done)**: Real web search.
- **3b (this increment)**: Read a specific webpage/PDF's actual content, by URL.
- **3c**: Upgraded, topic-based news monitoring with cited summaries.
- **3d**: YouTube/research paper/patent search.

## Scope

**In scope:**
1. A new `read_url_content` tool that fetches a URL and extracts its readable text, whether it's an HTML page or a PDF.
2. Two new, minimal dependencies: `beautifulsoup4` (HTML text extraction) and `pypdf` (pure-Python PDF text extraction, no system libraries).
3. A truncation strategy for long documents (~6,000 characters), with the model told explicitly that it's seeing a partial document.
4. A system prompt rule directing the model to use this tool only when the user references a specific URL and asks about its content — never for general search (that's `web_search`'s job) and never automatically just because a URL appears in the conversation.
5. A local-fallback heuristic branch (URL + keyword detection) for when no AI provider is reachable.
6. A small frontend "Read: `domain.com`" tag under replies that used this tool.

**Out of scope:**
- Local file upload (PDFs from the user's own computer, not a URL) — a future increment if needed.
- Chunked, multi-call summarization of arbitrarily long documents — truncation is the chosen strategy per the approved design.
- Any change to `web_search`, `get_news`, or existing tools.
- Non-PDF, non-HTML content types (images, videos, etc.) — these get a clear "can't read this type of content" message, not partial/garbled extraction.

## Design

### Tool: `read_url_content`

`backend/app/ai/tools.py` gains `_tool_read_url_content(args, user_id, store)`, following the existing tool pattern. It fetches the URL via `urllib.request` (same approach as every other network call in this codebase — no new HTTP client dependency), reading the `Content-Type` response header to branch:

- **`text/html`** → parsed with BeautifulSoup4 using the stdlib `html.parser` backend (no `lxml` needed, keeping the dependency footprint small). Strips `<script>`, `<style>`, `<nav>`, `<footer>`, and `<header>` tags before extracting text, then collapses repeated whitespace/blank lines.
- **`application/pdf`** → parsed with `pypdf.PdfReader`, extracting text from each page and joining with newlines.
- **Anything else** → returns `{"url": url, "error": "This doesn't look like a webpage or PDF I can read."}` rather than attempting extraction.

The extraction and truncation logic is pulled into a small pure function, `_extract_text(raw_bytes: bytes, content_type: str) -> dict`, callable and testable without a real network fetch — following the same TDD pattern established for `_parse_tavily_response` in 3a. It returns `{"text": str, "truncated": bool}`. The tool function itself wraps this with the actual `urllib` fetch, timeout, and error handling (network failure, non-200 status, timeout all produce a clear `error` message rather than raising).

Truncation: text longer than 6,000 characters is cut to that length, with `truncated: True` set so the tool's returned message can tell the model plainly ("this is the beginning of a longer document") — the model is instructed not to claim it read the whole thing when this flag is set.

### Tool definition

```
name: read_url_content
description: "Fetch and read the actual text content of a specific webpage or PDF the user links to, for summarizing or answering questions about it. Only use when the user gives a URL and asks you to read, summarize, or discuss it — not for general search."
parameters: { url: string, required }
```

### System prompt

A new numbered behavior rule (appended after the existing calendar/task rules) instructs: whenever the user references a specific link (pastes a URL, says "this article," "that PDF," etc.) and asks to read/summarize/discuss it, call `read_url_content` rather than answering from assumptions. If the tool result has `truncated: true`, the model should be aware it only saw the beginning of the document and should say so if asked whether it read everything.

### Local-fallback mode

`backend/app/ai/provider.py`'s heuristic dispatcher (the same `if/elif` chain that already handles `web_search`, tasks, etc.) gains a new branch: if the message contains a URL (detected via a simple regex, e.g. `https?://\S+`) alongside a keyword like "read," "summarize," or "what does this say," extract the URL and call `read_url_content`. `local_answer_from_tool` gains a matching branch that returns a short excerpt of the extracted text (first ~300 characters) if successful, or the tool's error message if not.

### Frontend

`message-cards.tsx` gains a small `ReadSourceTag` component — a single-line "Read: `domain.com`" link, visually consistent with 3a's `SearchSourcesCard` styling (same underline/accent-color treatment) but rendered as one line, not a list. `jarvis-interface.tsx` renders it under any assistant message whose `toolsUsed` includes a successful `read_url_content` call, the same way `searchSources()` already extracts `web_search` results.

### Dependencies

`backend/requirements.txt` gains `beautifulsoup4` and `pypdf`. Both are pure-Python (pypdf) or Python-with-stdlib-backend (beautifulsoup4 using `html.parser`, avoiding the heavier `lxml`), keeping with this project's minimal-dependency approach.

### Testing

`_extract_text(raw_bytes, content_type)` gets unit tests: HTML extraction strips tags and boilerplate correctly, PDF extraction returns real page text, truncation kicks in past 6,000 characters and sets the flag, and an unsupported content type is handled without crashing. The actual `urllib` fetch is not unit-tested, consistent with every other network-calling tool in this codebase.

### Manual verification plan

1. Ask JARVIS to summarize a real, ordinary article by URL — confirm the summary reflects the article's actual content, not a generic guess.
2. Ask JARVIS to read a real PDF by URL (e.g. a short public paper or report) and answer a specific question about its content.
3. Try a very long page/PDF — confirm the reply doesn't claim to have covered content beyond the truncation point if asked directly.
4. Try an unsupported link (e.g. a YouTube video URL or an image URL) — confirm a clear "can't read this" message, not garbled text.
5. Try a broken/unreachable URL — confirm a clear error message, not a crash.
6. Confirm plain web search (3a) and other existing tools still work unaffected.

## Explicitly deferred to future increments

- Local file upload (non-URL PDFs).
- Chunked/multi-call summarization for arbitrarily long documents.
- 3c: Upgraded news monitoring.
- 3d: YouTube/research paper/patent search.

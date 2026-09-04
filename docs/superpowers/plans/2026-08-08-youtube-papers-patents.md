# Internet Intelligence — Increment 3d Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YouTube video search, research paper search, and patent search — closing out the Internet Intelligence sequence (Sections 6-7 of `AGENT.md`).

**Architecture:** Three new tools (`search_youtube`, `search_papers`, `search_patents`) return the same `{query, answer, results: [{title, url, snippet, published}], message}` shape already established by `web_search`/`get_news`, so they plug into the existing `SearchSourcesCard` frontend component with a small list extension. A shared `_call_tavily` helper is extracted since the Tavily request pattern is now used a third time (`web_search`, `get_news`, `search_patents`).

**Tech Stack:** FastAPI, stdlib `urllib`, pytest, Next.js/React/TypeScript. No new dependencies (YouTube and Semantic Scholar are called directly via `urllib`, same as every other tool here).

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: YouTube API key configuration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_google_auth.py:6-22` (`_fake_settings`)

- [ ] **Step 1: Manual setup (done by the user)**

In the same Google Cloud project already used for Gmail/Calendar OAuth (console.cloud.google.com), enable "YouTube Data API v3" under APIs & Services, then create a new API key (Credentials → Create Credentials → API Key — a plain key, not OAuth client credentials). Copy the key.

- [ ] **Step 2: Add `youtube_api_key` to `Settings`**

Modify `backend/app/config.py`, replacing the `Settings` dataclass:
```python
@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    provider: str
    openai_api_key: str
    openai_model: str
    groq_api_key: str
    groq_model: str
    groq_whisper_model: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    tavily_api_key: str
    youtube_api_key: str
    database_path: Path
```

- [ ] **Step 3: Populate it in `get_settings`**

Modify `backend/app/config.py`, replacing the `get_settings` function's `return Settings(...)` call:
```python
    return Settings(
        host=os.getenv("JARVIS_HOST", "127.0.0.1"),
        port=int(os.getenv("JARVIS_PORT", "8000")),
        allowed_origins=parse_csv(origins),
        provider=os.getenv("JARVIS_PROVIDER", "auto").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_whisper_model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        database_path=DATA_DIR / "jarvis.db",
    )
```

- [ ] **Step 4: Add the env variable**

Modify `backend/.env`, appending after the existing `TAVILY_API_KEY=...` line:
```

# YouTube Data API v3 — see Task 1 for setup steps
YOUTUBE_API_KEY=
```
Fill in `YOUTUBE_API_KEY` with the key from Step 1.

Modify `backend/.env.example`, appending the same block with `YOUTUBE_API_KEY` left blank.

- [ ] **Step 5: Fix `test_google_auth.py`'s fake settings**

`Settings` is a dataclass with all-required fields, so adding `youtube_api_key` breaks any test that constructs one directly unless it's updated too. Modify `backend/tests/test_google_auth.py`, replacing `_fake_settings` (current lines 6-22):
```python
def _fake_settings() -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=[],
        provider="auto",
        openai_api_key="",
        openai_model="",
        groq_api_key="",
        groq_model="",
        groq_whisper_model="",
        google_client_id="test-client-id",
        google_client_secret="test-secret",
        google_redirect_uri="http://127.0.0.1:8000/api/gmail/callback",
        tavily_api_key="",
        youtube_api_key="",
        database_path=Path("unused.db"),
    )
```

- [ ] **Step 6: Verify settings load and tests pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -c "from app.config import get_settings; s = get_settings(); print(bool(s.youtube_api_key))"
python -m pytest tests/ -v
```
Expected: first command prints `True` (assuming Step 4's key was filled in); second command shows 37 passed, no regressions.

---

### Task 2: Shared `_call_tavily` helper + `search_patents` tool

**Files:**
- Modify: `backend/app/ai/tools.py:17` (import line)
- Modify: `backend/app/ai/tools.py:399-449` (`_parse_tavily_response`, `_tool_web_search`)
- Modify: `backend/app/ai/tools.py:534-570` (`_tool_get_news`)
- Modify: `backend/app/ai/tools.py:170-185` (`get_news` in `TOOL_DEFINITIONS`, to insert new entries after)
- Modify: `backend/app/ai/tools.py` (`TOOL_REGISTRY`)

- [ ] **Step 1: Import the `Settings` type**

Modify `backend/app/ai/tools.py`, replacing the config import line (current line 17):
```python
from app.config import Settings, get_settings
```

- [ ] **Step 2: Add `_call_tavily` and simplify `_tool_web_search`**

Modify `backend/app/ai/tools.py`, replacing from `def _parse_tavily_response(...)` through the end of `_tool_web_search` (current lines 399-449):
```python
def _call_tavily(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.tavily_api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_tavily_response(data: dict[str, Any], query: str) -> dict[str, Any]:
    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "published": item.get("published_date", ""),
        }
        for item in (data.get("results") or [])[:5]
    ]
    return {"query": query, "answer": data.get("answer", ""), "results": results}


def _tool_web_search(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "Web search isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(settings, {"query": query, "max_results": 5, "include_answer": "basic"})
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Web search failed: {exc}",
        }

    return _parse_tavily_response(data, query)
```

This keeps `_tool_web_search`'s behavior and return shape completely unchanged — only the network-call plumbing moved into `_call_tavily`.

- [ ] **Step 3: Simplify `_tool_get_news` and add `_tool_search_patents`**

Modify `backend/app/ai/tools.py`, replacing the full `_tool_get_news` function (current lines 534-570):
```python
def _tool_get_news(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic") or "").strip()
    query = topic or "top world news today"

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "News isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(
            settings, {"query": query, "topic": "news", "days": 3, "max_results": 5, "include_answer": "basic"}
        )
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"News search failed: {exc}",
        }

    return _parse_tavily_response(data, query)


def _tool_search_patents(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "Patent search isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(
            settings, {"query": f"{query} site:patents.google.com", "max_results": 5, "include_answer": "basic"}
        )
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Patent search failed: {exc}",
        }

    return _parse_tavily_response(data, query)
```

This again keeps `_tool_get_news`'s behavior unchanged, and adds the new patent tool right after it, reusing the exact same pattern.

- [ ] **Step 4: Register `search_patents` in `TOOL_DEFINITIONS`**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `get_news` entry closes (current lines 170-185, ending `},\n    },`) and before the `play_music` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "search_patents",
            "description": "Search patents on a topic and return real results (title, link). Use when the user asks to find patents or check if something is patented.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
```

- [ ] **Step 5: Register `search_patents` in `TOOL_REGISTRY`**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"get_news": _tool_get_news,`:
```python
    "search_patents": _tool_search_patents,
```

- [ ] **Step 6: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 37 passed, no regressions (the `_parse_tavily_response` tests still exercise the same function, now indirectly calling through `_call_tavily` for the network path only, which they don't invoke).

---

### Task 3: `search_youtube` tool (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_parse_youtube_results`, `_tool_search_youtube`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_parse_youtube_results_extracts_videos():
    from app.ai.tools import _parse_youtube_results

    data = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Intro to Solid-State Batteries",
                    "channelTitle": "Tech Explained",
                    "publishedAt": "2026-07-01T00:00:00Z",
                },
            }
        ]
    }

    results = _parse_youtube_results(data)

    assert results == [
        {
            "title": "Intro to Solid-State Batteries",
            "url": "https://www.youtube.com/watch?v=abc123",
            "snippet": "Tech Explained",
            "published": "2026-07-01T00:00:00Z",
        }
    ]


def test_parse_youtube_results_skips_items_without_video_id():
    from app.ai.tools import _parse_youtube_results

    data = {"items": [{"id": {}, "snippet": {"title": "No ID"}}]}

    assert _parse_youtube_results(data) == []


def test_parse_youtube_results_handles_missing_items():
    from app.ai.tools import _parse_youtube_results

    assert _parse_youtube_results({}) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_parse_youtube_results' from 'app.ai.tools'` on the 3 new tests.

- [ ] **Step 3: Add `_parse_youtube_results` and `_tool_search_youtube`**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_search_patents` ends and before `_tool_play_music` begins:
```python
def _parse_youtube_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in (data.get("items") or [])[:5]:
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet") or {}
        results.append(
            {
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "snippet": snippet.get("channelTitle", ""),
                "published": snippet.get("publishedAt", ""),
            }
        )
    return results


def _tool_search_youtube(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.youtube_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "YouTube search isn't configured — a YouTube API key is needed.",
        }

    params = urllib.parse.urlencode(
        {"part": "snippet", "type": "video", "maxResults": 5, "q": query, "key": settings.youtube_api_key}
    )
    request = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/search?{params}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"YouTube search failed: {exc}",
        }

    return {"query": query, "answer": "", "results": _parse_youtube_results(data), "message": ""}
```

- [ ] **Step 4: Register `search_youtube` in `TOOL_DEFINITIONS`**

Modify `backend/app/ai/tools.py`, inserting a new entry right after the `search_patents` entry (added in Task 2) and before `play_music`:
```python
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "Search YouTube for videos on a topic and return real results (title, channel, link). Use when the user asks to find or search for videos, tutorials, or talks — not for playing a specific song (use play_music for that).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
```

- [ ] **Step 5: Register `search_youtube` in `TOOL_REGISTRY`**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"search_patents": _tool_search_patents,`:
```python
    "search_youtube": _tool_search_youtube,
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 40 passed (37 from before + 3 new).

---

### Task 4: `search_papers` tool (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_parse_semantic_scholar_results`, `_tool_search_papers`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_parse_semantic_scholar_results_extracts_papers():
    from app.ai.tools import _parse_semantic_scholar_results

    data = {
        "data": [
            {
                "title": "Solid-State Battery Advances",
                "url": "https://www.semanticscholar.org/paper/abc123",
                "abstract": "A survey of recent progress in solid-state battery chemistry.",
                "year": 2026,
                "authors": [{"name": "Jane Doe"}, {"name": "John Smith"}],
            }
        ]
    }

    results = _parse_semantic_scholar_results(data)

    assert results == [
        {
            "title": "Solid-State Battery Advances",
            "url": "https://www.semanticscholar.org/paper/abc123",
            "snippet": "Jane Doe, John Smith · 2026",
            "published": "2026",
        }
    ]


def test_parse_semantic_scholar_results_falls_back_to_abstract_without_authors_or_year():
    from app.ai.tools import _parse_semantic_scholar_results

    long_abstract = "Some abstract text " * 20
    data = {"data": [{"title": "No metadata", "url": "https://example.com", "abstract": long_abstract}]}

    results = _parse_semantic_scholar_results(data)

    assert results[0]["snippet"] == long_abstract[:200]
    assert results[0]["published"] == ""


def test_parse_semantic_scholar_results_handles_missing_data():
    from app.ai.tools import _parse_semantic_scholar_results

    assert _parse_semantic_scholar_results({}) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_parse_semantic_scholar_results' from 'app.ai.tools'` on the 3 new tests.

- [ ] **Step 3: Add `_parse_semantic_scholar_results` and `_tool_search_papers`**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_search_youtube` ends and before `_tool_play_music` begins:
```python
def _parse_semantic_scholar_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for paper in (data.get("data") or [])[:5]:
        authors = ", ".join(author.get("name", "") for author in (paper.get("authors") or [])[:3])
        year = paper.get("year")
        parts = [part for part in [authors, str(year) if year else ""] if part]
        snippet = " · ".join(parts) or (paper.get("abstract") or "")[:200]
        results.append(
            {
                "title": paper.get("title", ""),
                "url": paper.get("url", ""),
                "snippet": snippet,
                "published": str(year) if year else "",
            }
        )
    return results


def _tool_search_papers(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    params = urllib.parse.urlencode({"query": query, "limit": 5, "fields": "title,abstract,url,year,authors"})
    request = urllib.request.Request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
        headers={"User-Agent": "JARVIS-Demo/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Paper search failed: {exc}",
        }

    return {"query": query, "answer": "", "results": _parse_semantic_scholar_results(data), "message": ""}
```

- [ ] **Step 4: Register `search_papers` in `TOOL_DEFINITIONS`**

Modify `backend/app/ai/tools.py`, inserting a new entry right after the `search_youtube` entry (added in Task 3) and before `play_music`:
```python
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search academic research papers on a topic and return real results (title, authors, year, link). Use when the user asks to find research papers, studies, or academic literature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
```

- [ ] **Step 5: Register `search_papers` in `TOOL_REGISTRY`**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"search_youtube": _tool_search_youtube,`:
```python
    "search_papers": _tool_search_papers,
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 43 passed (40 from before + 3 new).

---

### Task 5: System prompt updates

**Files:**
- Modify: `backend/app/ai/provider.py:81` (`SYSTEM_PROMPT` tool bullets)
- Modify: `backend/app/ai/provider.py:110` (rule 18)

- [ ] **Step 1: Add three new tool bullets**

Modify `backend/app/ai/provider.py`, inserting new lines right after the `get_news` bullet (current line 81):
```python
• search_youtube — Search YouTube for videos on a topic.
• search_papers — Search academic research papers on a topic.
• search_patents — Search patents on a topic.
```

- [ ] **Step 2: Reword rule 18**

Modify `backend/app/ai/provider.py`, replacing rule 18 (current line 110):
```python
18. When web_search, get_news, search_youtube, search_papers, or search_patents returns multiple results, synthesize them into a short spoken summary — weave in what the sources actually say in plain sentences, the way you'd brief someone out loud. Do not just recite a list of titles.
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 43 passed, no regressions.

---

### Task 6: Frontend — extend Sources rendering to the new tools

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:61` (add constant)
- Modify: `frontend/components/jarvis-interface.tsx:537-541` (`searchSources` helper)

- [ ] **Step 1: Add a module-level constant for source-tool names**

Modify `frontend/components/jarvis-interface.tsx`, inserting right after the `BACKEND_URL` constant (current line 61):
```tsx
const SOURCE_TOOL_NAMES = new Set([
  "web_search",
  "get_news",
  "search_youtube",
  "search_papers",
  "search_patents",
])
```

- [ ] **Step 2: Update `searchSources` to use it**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `searchSources` helper (current lines 537-541):
```tsx
  const searchSources = (msg: Message): SearchResult[] => {
    const call = msg.toolsUsed?.find((t) => SOURCE_TOOL_NAMES.has(t.name) && t.ok)
    const results = (call?.result as { results?: SearchResult[] } | undefined)?.results
    return Array.isArray(results) ? results : []
  }
```

- [ ] **Step 3: Typecheck**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no output (no type errors).

---

### Task 7: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart the backend**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
  $procId = $_
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 4
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too.

- [ ] **Step 2: YouTube search**

Ask "Find some YouTube videos about `<a real topic>`." Expected: real video titles/channels come back, spoken as a short summary (not a list), with a Sources list of clickable YouTube links.

- [ ] **Step 3: Paper search**

Ask "Find research papers about `<a real topic>`." Expected: real paper titles/authors/years, spoken as a short summary, with a Sources list of clickable links.

- [ ] **Step 4: Patent search**

Ask "Search for patents on `<a real topic>`." Expected: plausible patent-related results via the Google Patents-scoped search, with a Sources list.

- [ ] **Step 5: Verify the YouTube error path**

Temporarily blank out or break `YOUTUBE_API_KEY` in `backend\.env`, restart the backend, and ask for a YouTube search again. Expected: a clear "not configured" message, not a crash. Restore the real key and restart the backend afterward.

- [ ] **Step 6: Regression check**

Quickly re-verify `web_search`, `get_news`, and `read_url_content` (3a-3c) all still work unaffected by the `_call_tavily` refactor.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 8: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "YouTube, Paper & Patent Search" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 7's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Local-fallback heuristic branches for these three tools.
- Anything beyond Sections 6-7 of `AGENT.md` — this closes out the Internet Intelligence sequence.

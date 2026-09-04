# Internet Intelligence — Increment 3a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the weak DuckDuckGo instant-answer `web_search` tool with real ranked search results from Tavily.

**Architecture:** `_tool_web_search` calls Tavily's `/search` REST endpoint directly via stdlib `urllib` (no SDK), with the response-shaping logic split into a small pure helper function for unit testing. The local-fallback mode's search formatting, which currently depends on DuckDuckGo-specific response fields, is updated to match Tavily's shape so it doesn't silently break.

**Tech Stack:** FastAPI, stdlib `urllib`/`json`, pytest. No new dependencies.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/manual-verification step instead.

---

### Task 1: Tavily signup and configuration (manual + config)

**Files:**
- Modify: `backend/app/config.py:28-65` (`Settings` dataclass and `get_settings`)
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Sign up for Tavily (manual, done by the user)**

Go to `https://tavily.com`, create a free account (no card required). Copy the API key from the dashboard — it starts with `tvly-`.

- [ ] **Step 2: Add `tavily_api_key` to `Settings`**

Modify `backend/app/config.py`, replacing the `Settings` dataclass (current lines 28-42):
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
    database_path: Path
```

- [ ] **Step 3: Populate it in `get_settings`**

Modify `backend/app/config.py`, replacing the `get_settings` function (current lines 45-65):
```python
def get_settings() -> Settings:
    load_dotenv()
    origins = os.getenv(
        "JARVIS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
    )
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
        database_path=DATA_DIR / "jarvis.db",
    )
```

- [ ] **Step 4: Add the env variable**

Modify `backend/.env`, appending after the existing `GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/gmail/callback` line:
```

# Tavily web search — see Task 1 for setup steps
TAVILY_API_KEY=
```
Fill in `TAVILY_API_KEY` with the key from Step 1.

Modify `backend/.env.example`, appending the same block with `TAVILY_API_KEY` left blank.

- [ ] **Step 5: Verify settings load correctly**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -c "from app.config import get_settings; s = get_settings(); print(bool(s.tavily_api_key))"
```
Expected: prints `True` (assuming Step 4's key was filled in).

---

### Task 2: `_parse_tavily_response` helper and `_tool_web_search` rewrite (TDD)

**Files:**
- Create: `backend/tests/test_tools.py`
- Modify: `backend/app/ai/tools.py:122-134` (`web_search` in `TOOL_DEFINITIONS`), `:381-414` (`_tool_web_search`)

This is the first test file for `tools.py` — every other tool so far has either been a thin `MemoryStore` wrapper or a network call, neither of which had a pure function worth isolating until now.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_tools.py`:
```python
from app.ai.tools import _parse_tavily_response


def test_parse_tavily_response_extracts_results_and_answer():
    data = {
        "answer": "Paris is the capital of France.",
        "results": [
            {
                "title": "France",
                "url": "https://en.wikipedia.org/wiki/France",
                "content": "France is a country in Western Europe.",
            },
        ],
    }

    result = _parse_tavily_response(data, "capital of France")

    assert result["query"] == "capital of France"
    assert result["answer"] == "Paris is the capital of France."
    assert result["results"] == [
        {
            "title": "France",
            "url": "https://en.wikipedia.org/wiki/France",
            "snippet": "France is a country in Western Europe.",
        }
    ]


def test_parse_tavily_response_handles_missing_fields():
    result = _parse_tavily_response({}, "test query")

    assert result["query"] == "test query"
    assert result["answer"] == ""
    assert result["results"] == []


def test_parse_tavily_response_caps_at_five_results():
    data = {"results": [{"title": str(i), "url": "", "content": ""} for i in range(8)]}

    result = _parse_tavily_response(data, "many results")

    assert len(result["results"]) == 5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_parse_tavily_response'`.

- [ ] **Step 3: Update the `web_search` tool description**

Modify `backend/app/ai/tools.py`, replacing the `web_search` entry in `TOOL_DEFINITIONS` (current lines 122-134):
```python
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for real, ranked results on any topic. Use for factual lookups, current information, or anything requiring up-to-date web content.",
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

- [ ] **Step 4: Add `_parse_tavily_response` and rewrite `_tool_web_search`**

Modify `backend/app/ai/tools.py`, replacing `_tool_web_search` (current lines 381-414):
```python
def _parse_tavily_response(data: dict[str, Any], query: str) -> dict[str, Any]:
    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
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

    payload = json.dumps(
        {"query": query, "max_results": 5, "include_answer": "basic"}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.tavily_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Web search failed: {exc}",
        }

    return _parse_tavily_response(data, query)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 32 passed (the 3 new tests plus the 29 from before).

---

### Task 3: Fix the local-fallback `web_search` formatting

**Files:**
- Modify: `backend/app/ai/provider.py:333-339` (`local_answer_from_tool`'s `web_search` branch)

Left unfixed, this would silently break: it currently reads DuckDuckGo-specific fields (`abstract`, `heading`, `related`) that no longer exist in Tavily's response shape (`answer`, `results`), so local mode's search summary would degrade to a generic "could not find" message even when Tavily returned good results.

- [ ] **Step 1: Update the `web_search` branch**

Modify `backend/app/ai/provider.py`, replacing the `web_search` block inside `local_answer_from_tool` (current lines 333-339):
```python
    if name == "web_search":
        if data.get("answer"):
            return data["answer"]
        results = data.get("results") or []
        if results:
            return f"I found this: {results[0]['title']} — {results[0]['snippet']}"
        return data.get("message") or "I could not find useful search results for that."
```

- [ ] **Step 2: Run the test suite to confirm nothing broke**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 32 passed.

---

### Task 4: End-to-end manual verification

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

- [ ] **Step 2: Ask a query DuckDuckGo would typically fail on**

Ask something needing real ranked results, e.g. "Search for the latest developments in solid-state batteries." Expected: relevant results with real titles/URLs/snippets, plus a coherent summarized answer — not an empty or generic response.

- [ ] **Step 3: Ask a simple factual query**

Ask "Search what is the capital of France" or similar. Expected: still works well for simple lookups, not just complex ones.

- [ ] **Step 4: Verify the error path**

Temporarily blank out `TAVILY_API_KEY` in `backend/.env` (or set it to an obviously invalid value), restart the backend the same way as Step 1, and ask a search query. Expected: a clear "not configured" or "search failed" message, not a crash or silent failure. Afterward, restore the real key in `.env` and restart the backend once more so the app is left in a working state.

- [ ] **Step 5: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if you're continuing to use it).

---

## Post-plan: what's explicitly not in this increment

- 3b: Webpage/PDF reading.
- 3c: Upgraded news monitoring.
- 3d: YouTube/research paper/patent search.
- Everything else in `AGENT.md` beyond Section 1, the productivity sub-sequence, and this internet-intelligence sub-sequence.

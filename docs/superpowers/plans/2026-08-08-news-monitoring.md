# Internet Intelligence — Increment 3c Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `get_news`'s Google News RSS + Reddit scraping with Tavily's news search, so JARVIS gives a real spoken summary of what's happening with cited sources, instead of reciting a bare headline list.

**Architecture:** `_tool_get_news` is rewritten to call Tavily's `/search` endpoint with `topic: "news"`, reusing the existing `_parse_tavily_response` helper from 3a (which gains one new `published` field). A new system prompt rule tells the model to synthesize results into spoken sentences rather than a list. The frontend reuses 3a's `SearchSourcesCard` for news replies via a one-line change, since the response shape is now identical to `web_search`.

**Tech Stack:** FastAPI, stdlib `urllib`, pytest, Next.js/React/TypeScript. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: `published` field on `_parse_tavily_response` (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py:1-26` (`test_parse_tavily_response_extracts_results_and_answer`)
- Modify: `backend/app/ai/tools.py:399-408` (`_parse_tavily_response`)

- [ ] **Step 1: Update the existing test to expect the new field**

Modify `backend/tests/test_tools.py`, replacing `test_parse_tavily_response_extracts_results_and_answer` (current lines 4-26):
```python
def test_parse_tavily_response_extracts_results_and_answer():
    data = {
        "answer": "Paris is the capital of France.",
        "results": [
            {
                "title": "France",
                "url": "https://en.wikipedia.org/wiki/France",
                "content": "France is a country in Western Europe.",
                "published_date": "2026-08-01",
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
            "published": "2026-08-01",
        }
    ]


def test_parse_tavily_response_defaults_published_to_empty_string():
    data = {"results": [{"title": "No date", "url": "https://example.com", "content": "text"}]}

    result = _parse_tavily_response(data, "query")

    assert result["results"][0]["published"] == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_tools.py -v
```
Expected: the updated test and the new test both fail (`KeyError: 'published'` or an assertion mismatch), while `test_parse_tavily_response_handles_missing_fields` and `test_parse_tavily_response_caps_at_five_results` still pass.

- [ ] **Step 3: Add the `published` field**

Modify `backend/app/ai/tools.py`, replacing `_parse_tavily_response` (current lines 399-408):
```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 37 passed (36 from before + 1 new test; the updated test replaces one of the prior 36 without changing the total net-new count by more than 1).

---

### Task 2: Rewrite `_tool_get_news` to use Tavily

**Files:**
- Modify: `backend/app/ai/tools.py:533-599` (`_tool_get_news`)
- Modify: `backend/app/ai/tools.py:170-185` (`get_news` in `TOOL_DEFINITIONS`)

- [ ] **Step 1: Replace `_tool_get_news`**

Modify `backend/app/ai/tools.py`, replacing the full `_tool_get_news` function (current lines 533-599, from `def _tool_get_news(...)` through its closing `}`):
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

    payload = json.dumps(
        {"query": query, "topic": "news", "days": 3, "max_results": 5, "include_answer": "basic"}
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
            "message": f"News search failed: {exc}",
        }

    return _parse_tavily_response(data, query)
```

This removes the Google News RSS parsing and Reddit fallback entirely — `xml.etree.ElementTree` was only ever imported locally inside this function, so no other cleanup is needed.

- [ ] **Step 2: Update the tool description**

Modify `backend/app/ai/tools.py`, replacing the `get_news` entry's `description` in `TOOL_DEFINITIONS` (current line 174):
```python
            "description": "Get a summarized news briefing on a topic, with real, recent, cited sources. Use when the user asks for news, current events, or what's happening in the world.",
```

- [ ] **Step 3: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 37 passed, no regressions.

---

### Task 3: System prompt, local-fallback fix

**Files:**
- Modify: `backend/app/ai/provider.py:81` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:109` (append rule 18)
- Modify: `backend/app/ai/provider.py:349-354` (`local_answer_from_tool`'s `get_news` branch)

- [ ] **Step 1: Update the `get_news` bullet**

Modify `backend/app/ai/provider.py`, replacing the `get_news` bullet in `SYSTEM_PROMPT` (current line 81):
```python
• get_news — Get a summarized news briefing on a topic, with real cited sources.
```

- [ ] **Step 2: Add rule 18**

Modify `backend/app/ai/provider.py`, appending a new rule 18 right after rule 17 and before the closing `"""` (current lines 109-110):
```python
18. When get_news or web_search returns multiple results, synthesize them into a short spoken summary of what's happening — weave in what the sources actually say in plain sentences, the way you'd brief someone out loud. Do not just recite a list of titles.
"""
```

- [ ] **Step 3: Fix the `get_news` branch in `local_answer_from_tool`**

Modify `backend/app/ai/provider.py`, replacing the `get_news` block inside `local_answer_from_tool` (current lines 349-354):
```python
    if name == "get_news":
        if data.get("answer"):
            return data["answer"]
        results = data.get("results") or []
        if results:
            return "Here's what's happening: " + "; ".join(r["title"] for r in results[:4]) + "."
        return data.get("message") or "I couldn't fetch the news right now."
```

- [ ] **Step 4: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 37 passed, no regressions.

---

### Task 4: Frontend — reuse `SearchSourcesCard` for news

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:537-541` (`searchSources` helper)

- [ ] **Step 1: Match `get_news` too**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `searchSources` helper (current lines 537-541):
```tsx
  const searchSources = (msg: Message): SearchResult[] => {
    const call = msg.toolsUsed?.find((t) => (t.name === "web_search" || t.name === "get_news") && t.ok)
    const results = (call?.result as { results?: SearchResult[] } | undefined)?.results
    return Array.isArray(results) ? results : []
  }
```

- [ ] **Step 2: Typecheck**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no output (no type errors).

---

### Task 5: End-to-end manual verification

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

- [ ] **Step 2: Ask for news on a topic**

Ask "What's the latest news on `<a real, currently active topic>`?" Expected: a real spoken summary (not a bare title list) with a "Sources" link list underneath showing real, recent articles.

- [ ] **Step 3: Ask for general news**

Ask "What's happening in the news today?" (no topic). Expected: still works, returns current general headlines summarized the same way.

- [ ] **Step 4: Confirm no bullets/lists leak through**

Check the reply text itself — it should read as natural spoken sentences, not a recited list or bullet points.

- [ ] **Step 5: Verify the error path**

Temporarily blank out or break `TAVILY_API_KEY` in `backend\.env`, restart the backend, and ask for news again. Expected: a clear error/not-configured message, not a crash. Restore the real key and restart the backend afterward.

- [ ] **Step 6: Regression check**

Quickly re-verify `web_search` (3a) and `read_url_content` (3b) still work unaffected.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 6: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "News Monitoring" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 5's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Proactive background news monitoring / topic subscriptions / notifications.
- 3d: YouTube/research paper/patent search.

# Internet Intelligence — Increment 3b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let JARVIS fetch and read the actual text content of a specific webpage or PDF the user links to, so it can summarize or answer questions about real content instead of guessing from a search snippet.

**Architecture:** A new tool, `read_url_content`, fetches a URL via `urllib` and branches on the response's `Content-Type` header — HTML is parsed with BeautifulSoup4, PDF with pypdf. The extraction/truncation logic lives in a small pure function, `_extract_text(raw_bytes, content_type)`, unit-tested independently of the network fetch. The model is told (via a new system prompt rule) to use this tool only when the user references a specific link and asks about its content.

**Tech Stack:** FastAPI, stdlib `urllib`, `beautifulsoup4` (new), `pypdf` (new), pytest, Next.js/React/TypeScript.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Add dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the two new dependencies**

Modify `backend/requirements.txt`, replacing its full content:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
tzdata>=2024.1
pytest==8.3.4
python-multipart==0.0.32
google-auth>=2.35.0
google-auth-oauthlib>=1.2.1
beautifulsoup4>=4.12.3
pypdf>=5.1.0
```

- [ ] **Step 2: Install them into the venv**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "import bs4, pypdf; print('ok')"
```
Expected: last line prints `ok`.

---

### Task 2: `_extract_text` helper and `read_url_content` tool (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add imports, helper, tool function, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the existing file (keep the existing `_parse_tavily_response` tests as-is, just add these below):
```python


def test_extract_text_strips_html_tags_and_boilerplate():
    from app.ai.tools import _extract_text

    html = b"""
    <html><head><script>var x=1;</script><style>.a{color:red}</style></head>
    <body><nav>Menu</nav><header>Site Header</header>
    <article><h1>Title</h1><p>Real content here.</p></article>
    <footer>Copyright 2026</footer></body></html>
    """
    result = _extract_text(html, "text/html; charset=utf-8")

    assert "Real content here." in result["text"]
    assert "Menu" not in result["text"]
    assert "Site Header" not in result["text"]
    assert "Copyright 2026" not in result["text"]
    assert result["truncated"] is False


def test_extract_text_truncates_long_html():
    from app.ai.tools import _extract_text

    html = b"<html><body><p>" + b"word " * 3000 + b"</p></body></html>"
    result = _extract_text(html, "text/html")

    assert len(result["text"]) <= 6000
    assert result["truncated"] is True


def test_extract_text_extracts_pdf_content_without_crashing():
    from pypdf import PdfWriter
    import io

    from app.ai.tools import _extract_text

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)

    result = _extract_text(buffer.getvalue(), "application/pdf")

    assert result["truncated"] is False
    assert isinstance(result["text"], str)


def test_extract_text_rejects_unsupported_content_type():
    from app.ai.tools import _extract_text

    result = _extract_text(b"binary-data", "image/png")

    assert result["error"] == "This doesn't look like a webpage or PDF I can read."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_extract_text' from 'app.ai.tools'` on the new tests (the 3 existing `_parse_tavily_response` tests still pass).

- [ ] **Step 3: Add imports**

Modify `backend/app/ai/tools.py`, replacing the top import block (current lines 1-15):
```python
from __future__ import annotations

import io
import json
import platform
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import get_settings
from app.services import google_auth
from app.services.memory import MemoryStore
```

- [ ] **Step 4: Add `_extract_text` and `_tool_read_url_content`**

Modify `backend/app/ai/tools.py`, inserting immediately after the end of `_tool_web_search` (after its closing `return _parse_tavily_response(data, query)` line and before the `# ── New tool implementations ──` comment):
```python
MAX_READ_CONTENT_CHARS = 6000


def _extract_text(raw_bytes: bytes, content_type: str) -> dict[str, Any]:
    content_type = (content_type or "").lower()

    if "html" in content_type:
        soup = BeautifulSoup(raw_bytes, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    elif "pdf" in content_type:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
    else:
        return {"text": "", "truncated": False, "error": "This doesn't look like a webpage or PDF I can read."}

    truncated = len(text) > MAX_READ_CONTENT_CHARS
    return {"text": text[:MAX_READ_CONTENT_CHARS], "truncated": truncated}


def _tool_read_url_content(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("A URL is required.")

    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Demo/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        return {"url": url, "error": f"I couldn't fetch that page: {exc}"}

    extracted = _extract_text(raw_bytes, content_type)
    if extracted.get("error"):
        return {"url": url, "error": extracted["error"]}
    if not extracted["text"]:
        return {"url": url, "error": "I fetched the page but couldn't find any readable text on it."}

    return {
        "url": url,
        "text": extracted["text"],
        "truncated": extracted["truncated"],
        "message": (
            "I've read this page. Note: this is only the beginning of a longer document."
            if extracted["truncated"]
            else "I've read this page."
        ),
    }
```

- [ ] **Step 5: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `web_search` entry closes (current lines 121-134, ending `},\n    },`) and before the `generate_image` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "read_url_content",
            "description": "Fetch and read the actual text content of a specific webpage or PDF the user links to, for summarizing or answering questions about it. Only use when the user gives a URL and asks you to read, summarize, or discuss it — not for general search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL of the webpage or PDF to read."}
                },
                "required": ["url"],
            },
        },
    },
```

- [ ] **Step 6: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` (current lines 677-695), right after `"web_search": _tool_web_search,`:
```python
    "read_url_content": _tool_read_url_content,
```

- [ ] **Step 7: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 36 passed (32 from before + 4 new).

---

### Task 3: System prompt, local-fallback dispatcher, and local answer formatting

**Files:**
- Modify: `backend/app/ai/provider.py`

- [ ] **Step 1: Add the tool to the system prompt's bullet list**

Modify `backend/app/ai/provider.py`, in `SYSTEM_PROMPT`, inserting a new line right after the `web_search` bullet (current line 78: `• web_search — Search the web for factual answers.`):
```python
• read_url_content — Read the actual text content of a specific webpage or PDF the user links to.
```

- [ ] **Step 2: Add a new numbered behavior rule**

Modify `backend/app/ai/provider.py`, appending a new rule 17 at the end of the numbered list, right after rule 16 and before the closing `"""` (current lines 107-108):
```python
17. Any time the user references a specific link (pastes a URL, says "this article," "that PDF," "the page I sent") and asks you to read, summarize, or discuss it, call read_url_content rather than answering from assumptions about what it says. If the tool result has truncated: true, you only saw the beginning of the document — say so plainly if asked whether you read the whole thing, rather than claiming full coverage.
"""
```

- [ ] **Step 3: Add the local-fallback dispatcher branch**

Modify `backend/app/ai/provider.py`, inside `run_single_local_command`, inserting a new branch right after the existing "Web search" branch (current lines 432-437) and before the "Tasks" branch:
```python
    # Read a specific URL's content
    url = extract_url(text)
    if url and re.search(r"\b(read|summarize|summarise)\b", lowered):
        result = runner.run("read_url_content", {"url": url}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("read_url_content", result), tool_results
```

- [ ] **Step 4: Add the `local_answer_from_tool` branch**

Modify `backend/app/ai/provider.py`, inside `local_answer_from_tool`, inserting a new branch right after the existing `web_search` branch (current lines 333-339) and before the `generate_image` branch:
```python
    if name == "read_url_content":
        if data.get("error"):
            return data["error"]
        excerpt = (data.get("text") or "")[:300]
        return f"Here's what I found: {excerpt}"
```

- [ ] **Step 5: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 36 passed, no regressions.

---

### Task 4: Frontend — show which URL was read

**Files:**
- Modify: `frontend/components/message-cards.tsx`
- Modify: `frontend/components/jarvis-interface.tsx`

- [ ] **Step 1: Add the `ReadSourceTag` component**

Modify `frontend/components/message-cards.tsx`, inserting a new component right after `SearchSourcesCard` ends (current lines 331-351) and before the `/* ── Calendar Event Draft Card (create or edit) ─────────────────────────── */` comment:
```tsx
export function ReadSourceTag({ url }: { url: string | null }) {
  if (!url) return null
  return (
    <div className="mt-3 border-t border-primary/15 pt-2">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
      >
        Read: {hostname(url)}
      </a>
    </div>
  )
}
```

- [ ] **Step 2: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-17):
```tsx
import {
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  EmailDraftCard,
  ImageModal,
  InlineImage,
  ReadSourceTag,
  type SearchResult,
  SearchSourcesCard,
  TypewriterText,
} from "@/components/message-cards"
```

- [ ] **Step 3: Add a `readSourceUrl` helper**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new helper right after `searchSources` (current lines 536-539):
```tsx
  const readSourceUrl = (msg: Message): string | null => {
    const call = msg.toolsUsed?.find((t) => t.name === "read_url_content" && t.ok)
    const url = (call?.result as { url?: string } | undefined)?.url
    return typeof url === "string" ? url : null
  }
```

- [ ] **Step 4: Render the tag**

Modify `frontend/components/jarvis-interface.tsx`, inserting the render call right after the `SearchSourcesCard` render block (current lines 823-826), before the "Provider + tools metadata" comment:
```tsx
                  {/* Which URL was read, if this reply used read_url_content */}
                  {message.role === "assistant" && (
                    <ReadSourceTag url={readSourceUrl(message)} />
                  )}
```

- [ ] **Step 5: Typecheck**

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

- [ ] **Step 2: Summarize a real article**

Ask something like "Summarize this article: <a real, ordinary news or blog article URL>." Expected: the reply reflects the article's actual content (specific to that page), and a "Read: `domain.com`" link appears under the reply, opening the same URL in a new tab.

- [ ] **Step 3: Read a real PDF**

Ask something like "What does this PDF say about X: <a real, short, public PDF URL>?" Expected: a specific answer drawn from the PDF's actual text.

- [ ] **Step 4: Try a very long page**

Ask to read a long page, then ask "did you read the whole thing?" Expected: JARVIS acknowledges it only saw the beginning, not a false claim of full coverage.

- [ ] **Step 5: Try an unsupported link**

Ask JARVIS to read a YouTube video URL or a direct image URL. Expected: a clear "can't read this type of content" message, not garbled text.

- [ ] **Step 6: Try a broken URL**

Ask JARVIS to read an unreachable or invalid URL (e.g. a typo'd domain). Expected: a clear error message, not a crash.

- [ ] **Step 7: Regression check**

Quickly re-verify plain web search (3a) still works normally.

- [ ] **Step 8: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 6: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 5's manual verification steps above (summarizing an article, reading a PDF, long-document truncation honesty, unsupported content type, broken URL, regression check).

---

## Post-plan: what's explicitly not in this increment

- Local file upload (non-URL PDFs).
- Chunked/multi-call summarization for arbitrarily long documents.
- 3c: Upgraded news monitoring.
- 3d: YouTube/research paper/patent search.

# Business Intelligence — Increment 4c Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `create_business_report` tool that packages already-gathered research into a structured visual report card, closing out the buildable part of Business Intelligence (§15).

**Architecture:** The tool has no external side effect — it validates and packages `{topic, sections, sources}` into a `business_report` `ClientAction`, following the exact pattern already used by `compose_email`/`draft_calendar_event`. The frontend renders a new `BusinessReportCard`, which can use real headings/structure since it's a visual card, not spoken TTS text.

**Tech Stack:** FastAPI, Pydantic, Next.js/React/TypeScript. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-46` (`ClientAction`)
- Modify: `backend/app/services/tool_runner.py:26-63` (`extract_action`)

- [ ] **Step 1: Add the new action type and report fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-46):
```python
class ClientAction(BaseModel):
    type: Literal[
        "open_url",
        "compose_email",
        "calendar_event_draft",
        "calendar_event_delete_confirm",
        "business_report",
    ]
    url: str | None = None
    email_to: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    mailto_link: str | None = None
    event_id: str | None = None
    event_summary: str | None = None
    event_start: str | None = None
    event_end: str | None = None
    event_description: str | None = None
    event_location: str | None = None
    event_attendees: list[str] | None = None
    report_topic: str | None = None
    report_sections: list[dict[str, str]] | None = None
    report_sources: list[str] | None = None
```

- [ ] **Step 2: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `calendar_event_delete_confirm` branch (current lines 56-62) and before `return None`:
```python
            if action_type == "business_report":
                return ClientAction(
                    type="business_report",
                    report_topic=action.get("report_topic") or "",
                    report_sections=action.get("report_sections") or [],
                    report_sources=action.get("report_sources") or [],
                )
```

- [ ] **Step 3: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions.

---

### Task 2: `create_business_report` tool

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_create_business_report`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add the tool implementation**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_get_market_quote` ends (current line 780, `return _parse_finnhub_quote(data, symbol)`) and before `_tool_play_music` begins:
```python
def _tool_create_business_report(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip()
    if not topic:
        raise ValueError("A report topic is required.")

    raw_sections = args.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("At least one report section is required.")

    sections = [
        {"heading": str(section.get("heading", "")).strip(), "content": str(section.get("content", "")).strip()}
        for section in raw_sections
        if isinstance(section, dict)
        and str(section.get("heading", "")).strip()
        and str(section.get("content", "")).strip()
    ]
    if not sections:
        raise ValueError("At least one report section with a heading and content is required.")

    sources = [str(source) for source in (args.get("sources") or []) if isinstance(source, str)]

    return {
        "action": {
            "type": "business_report",
            "report_topic": topic,
            "report_sections": sections,
            "report_sources": sources,
        },
        "message": f"I've put together a business report on {topic}.",
    }
```

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `get_market_quote` entry closes (current lines 186-199, ending `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "create_business_report",
            "description": "Compile a structured business report after researching a topic (a company, market, or investment idea) using web_search, get_market_quote, and/or read_url_content. Only call this with sections backed by what you actually found — never fabricate content. Still give a brief spoken summary in your reply; this tool produces a visual card, it doesn't replace speaking to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The report's subject, e.g. a company or market name."},
                    "sections": {
                        "type": "array",
                        "description": "Report sections built from real research, e.g. Overview, Market Position, Financials, Recent News.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["heading", "content"],
                        },
                    },
                    "sources": {
                        "type": ["array", "null"],
                        "description": "Optional list of source URLs used to compile the report.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["topic", "sections"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"get_market_quote": _tool_get_market_quote,`:
```python
    "create_business_report": _tool_create_business_report,
```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions (no new tests in this task — see the spec's testing rationale: this tool has no pure logic distinct from the existing untested `compose_email`/`draft_calendar_event` pattern).

---

### Task 3: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:82` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:117` (append rule 21)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `get_market_quote` bullet (current line 82):
```python
• create_business_report — Compile a structured business report card after researching a topic.
```

- [ ] **Step 2: Add rule 21**

Modify `backend/app/ai/provider.py`, appending a new rule 21 right after rule 20 and before the closing `"""` (current lines 116-117):
```python
21. When the user asks for a report, summary document, or overview of a company, market, or investment idea, research it first (per rule 20), then call create_business_report with sections drawn only from what you actually found — if a section has nothing to report (e.g. no financial data for a private company), omit that section rather than inventing content. Always pair the tool call with a brief spoken summary in your reply — the report card supplements what you say, it doesn't replace it.
"""
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions.

---

### Task 4: Frontend — `BusinessReportCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx:4` (icon import)
- Modify: `frontend/components/message-cards.tsx:9-23` (`ClientAction` interface)
- Modify: `frontend/components/message-cards.tsx` (append `BusinessReportCard` at end of file)
- Modify: `frontend/components/jarvis-interface.tsx:7-18` (import block)
- Modify: `frontend/components/jarvis-interface.tsx` (render branch)

- [ ] **Step 1: Add the `FileText` icon import**

Modify `frontend/components/message-cards.tsx`, replacing the lucide-react import (current line 4):
```tsx
import { CalendarClock, Check, ClipboardCopy, Download, FileText, Loader2, Mail, Maximize2, X } from "lucide-react"
```

- [ ] **Step 2: Add report fields to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, replacing the `ClientAction` interface (current lines 9-23):
```tsx
export interface ClientAction {
  type:
    | "open_url"
    | "compose_email"
    | "calendar_event_draft"
    | "calendar_event_delete_confirm"
    | "business_report"
  url?: string
  email_to?: string
  email_subject?: string
  email_body?: string
  mailto_link?: string
  event_id?: string
  event_summary?: string
  event_start?: string
  event_end?: string
  event_description?: string
  event_location?: string
  event_attendees?: string[]
  report_topic?: string
  report_sections?: { heading: string; content: string }[]
  report_sources?: string[]
}
```

- [ ] **Step 3: Add `BusinessReportCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `CalendarEventDeleteConfirm` closes (current lines 513-514):
```tsx

/* ── Business Report Card ──────────────────────────────────────────────── */

export function BusinessReportCard({ action }: { action: ClientAction }) {
  const sections = action.report_sections || []
  const sources = action.report_sources || []
  if (!sections.length) return null

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Business Report{action.report_topic ? `: ${action.report_topic}` : ""}
      </div>
      <div className="space-y-2.5">
        {sections.map((section, i) => (
          <div key={`${section.heading}-${i}`}>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
              {section.heading}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-foreground">{section.content}</p>
          </div>
        ))}
      </div>
      {sources.length > 0 && (
        <div className="space-y-1.5 border-t border-accent/15 pt-2">
          <p className="font-mono text-[9px] uppercase tracking-[0.28em] text-muted-foreground/70">
            Sources
          </p>
          {sources.map((url, i) => (
            <a
              key={`${url}-${i}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate text-[11px] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
            >
              {url}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-18):
```tsx
import {
  BusinessReportCard,
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

- [ ] **Step 5: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `calendar_event_delete_confirm` block (current lines 836-844), before the "Web search sources" comment:
```tsx
                  {/* Business report: structured research summary */}
                  {message.action?.type === "business_report" && (
                    <BusinessReportCard action={message.action} />
                  )}
```

- [ ] **Step 6: Typecheck**

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

- [ ] **Step 2: Business report on a real company**

Ask "Give me a business report on `<a real, findable company>`." Expected: JARVIS researches it (tool calls visible in the metadata line), speaks a brief summary, and a structured report card appears with real, non-generic section content.

- [ ] **Step 3: Card structure vs. spoken text**

Confirm the report card shows real headings/sections (this is fine — it's a card, not spoken text), while the chat reply text itself stays voice-safe (no bullets/headers in what's actually spoken/displayed as the message body).

- [ ] **Step 4: Market data section**

Ask for a report on a public company. Expected: a section reflects real `get_market_quote` data (an actual current price), not invented numbers.

- [ ] **Step 5: Honest omission**

Ask for a report on something where a section genuinely has nothing to report (e.g. financials for a private company). Expected: that section is omitted, not filled with fabricated content.

- [ ] **Step 6: Sources**

Confirm the report card's sources are real, clickable links.

- [ ] **Step 7: Regression check**

Quickly re-verify 4a (market data) and 4b (research) still work unaffected.

- [ ] **Step 8: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 6: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Business Reports" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 5's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Saved/retrievable report history.
- Report export (PDF, copy, etc.).
- Sales insights / customer analytics (blocked pending client input on data source).

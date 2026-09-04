# AI Content Creation — Increment 5a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `create_content` tool that drafts social captions, YouTube/podcast scripts, and marketing copy — always researched first and grounded in what was actually found, rendered as a card the user can copy.

**Architecture:** The tool has no external side effect — like `create_business_report`, it validates and packages `{topic, content_type, platform, content, sources}` into a `content_draft` `ClientAction`. The frontend renders a new `ContentDraftCard` with a copy button. A new system prompt rule enforces research-first, grounded generation, reusing the economy limit already established for company research.

**Tech Stack:** FastAPI, Pydantic, Next.js/React/TypeScript. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-50` (`ClientAction`)
- Modify: `backend/app/services/tool_runner.py:26-70` (`extract_action`)

- [ ] **Step 1: Add the new action type and content fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-50):
```python
class ClientAction(BaseModel):
    type: Literal[
        "open_url",
        "compose_email",
        "calendar_event_draft",
        "calendar_event_delete_confirm",
        "business_report",
        "content_draft",
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
    content_topic: str | None = None
    content_format: str | None = None
    content_platform: str | None = None
    content_body: str | None = None
    content_sources: list[str] | None = None
```

- [ ] **Step 2: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `business_report` branch (current lines 63-69) and before `return None`:
```python
            if action_type == "content_draft":
                return ClientAction(
                    type="content_draft",
                    content_topic=action.get("content_topic") or "",
                    content_format=action.get("content_format") or "",
                    content_platform=action.get("content_platform"),
                    content_body=action.get("content_body") or "",
                    content_sources=action.get("content_sources") or [],
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

### Task 2: `create_content` tool

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_create_content`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add the tool implementation**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_create_business_report` ends (current line 849, `"message": f"I've put together a business report on {topic}.",\n    }`) and before `_tool_play_music` begins:
```python
CONTENT_FORMAT_LABELS = {
    "social_caption": "a social caption",
    "script": "a script",
    "marketing_copy": "marketing copy",
}


def _tool_create_content(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip()
    if not topic:
        raise ValueError("A content topic is required.")

    content_type = str(args.get("content_type", "")).strip()
    if content_type not in CONTENT_FORMAT_LABELS:
        raise ValueError("content_type must be one of: social_caption, script, marketing_copy.")

    content = str(args.get("content", "")).strip()
    if not content:
        raise ValueError("Drafted content is required.")

    platform = str(args.get("platform") or "").strip() or None
    sources = [str(source) for source in (args.get("sources") or []) if isinstance(source, str)]

    return {
        "action": {
            "type": "content_draft",
            "content_topic": topic,
            "content_format": content_type,
            "content_platform": platform,
            "content_body": content,
            "content_sources": sources,
        },
        "message": f"I've drafted {CONTENT_FORMAT_LABELS[content_type]} on {topic}.",
    }
```

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `create_business_report` entry closes (current lines 206-233, ending `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "create_content",
            "description": (
                "Draft social media captions, video/podcast scripts, or marketing copy — always after "
                "researching the topic with web_search/get_news first (at most 2 calls, per rule 10's "
                "economy guidance), and always grounded in what was actually found. Never invent "
                "statistics, quotes, or claims not backed by the research.\n\n"
                "Style per content_type:\n"
                "- social_caption: platform-aware. instagram: short, punchy hook in the first line, "
                "emoji-friendly, 3-5 relevant hashtags at the end. linkedin: professional tone, no "
                "emoji-heavy style, a clear insight or takeaway, 1-2 hashtags. x: concise, fits a single "
                "post, at most 1-2 hashtags.\n"
                "- script: spoken-word structure — an opening hook (first 5-10 seconds), 2-4 body "
                "segments, a closing call-to-action. Written to be read aloud, not as a formal document.\n"
                "- marketing_copy: short, benefit-focused, one clear call-to-action, no filler."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "What the content is about."},
                    "content_type": {
                        "type": "string",
                        "description": "One of: social_caption, script, marketing_copy.",
                    },
                    "platform": {
                        "type": ["string", "null"],
                        "description": "For social_caption only: instagram, linkedin, or x. Leave empty for other content types.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The actual drafted content text, written per the style rules above.",
                    },
                    "sources": {
                        "type": ["array", "null"],
                        "description": "Optional list of source URLs the content was grounded in.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["topic", "content_type", "content"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"create_business_report": _tool_create_business_report,`:
```python
    "create_content": _tool_create_content,
```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions (no new tests in this task, same rationale as `create_business_report`: no pure logic distinct from that existing, untested pattern).

---

### Task 3: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:81` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:97-98` (insert new rule 11, renumber personality rule to 12)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `create_business_report` bullet (current line 81):
```python
• create_content — draft social captions, scripts, or marketing copy, always researched first and grounded in what you found; never invent facts or stats
```

- [ ] **Step 2: Insert the new rule and renumber the personality rule**

Modify `backend/app/ai/provider.py`, replacing rule 11 and the closing `"""` (current lines 98-99):
```python
11. When asked for social captions, a script, or marketing copy, research the topic first (per rule 10), then call create_content with the actual drafted text — grounded in what you found, matching the style rules in the tool's description for that content type/platform. Speak a one-line summary alongside the tool call; the card is the deliverable.
12. Be warm and professional, like JARVIS from Iron Man — occasional wit, always helpful.
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

### Task 4: Frontend — `ContentDraftCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx:9-30` (`ClientAction` interface)
- Modify: `frontend/components/message-cards.tsx` (append `ContentDraftCard` at end of file)
- Modify: `frontend/components/jarvis-interface.tsx:7-19` (import block)
- Modify: `frontend/components/jarvis-interface.tsx` (render branch)

- [ ] **Step 1: Add content fields to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, replacing the `ClientAction` interface (current lines 9-30):
```tsx
export interface ClientAction {
  type:
    | "open_url"
    | "compose_email"
    | "calendar_event_draft"
    | "calendar_event_delete_confirm"
    | "business_report"
    | "content_draft"
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
  content_topic?: string
  content_format?: string
  content_platform?: string
  content_body?: string
  content_sources?: string[]
}
```

- [ ] **Step 2: Add `ContentDraftCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `BusinessReportCard` closes (current lines 526-567):
```tsx

/* ── Content Draft Card ────────────────────────────────────────────────── */

const CONTENT_FORMAT_LABELS: Record<string, string> = {
  social_caption: "Social Caption",
  script: "Script",
  marketing_copy: "Marketing Copy",
}

export function ContentDraftCard({ action }: { action: ClientAction }) {
  const body = action.content_body || ""
  if (!body) return null
  const formatLabel = (action.content_format && CONTENT_FORMAT_LABELS[action.content_format]) || "Content"
  const sources = action.content_sources || []

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
          <FileText className="h-3 w-3" />
          {formatLabel}
          {action.content_platform ? ` · ${action.content_platform}` : ""}
          {action.content_topic ? `: ${action.content_topic}` : ""}
        </div>
        <CopyButton text={body} label="Copy" />
      </div>
      <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-foreground">{body}</p>
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
`CopyButton` is already defined earlier in this same file (used internally by `EmailDraftCard`) — no new import needed, it's just reused directly since `ContentDraftCard` lives in the same module.

- [ ] **Step 3: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-19):
```tsx
import {
  BusinessReportCard,
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  ContentDraftCard,
  EmailDraftCard,
  ImageModal,
  InlineImage,
  ReadSourceTag,
  type SearchResult,
  SearchSourcesCard,
  TypewriterText,
} from "@/components/message-cards"
```

- [ ] **Step 4: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `business_report` block (current lines 847-850), before the "Web search sources" comment:
```tsx
                  {/* Drafted content: social caption, script, or marketing copy */}
                  {message.action?.type === "content_draft" && (
                    <ContentDraftCard action={message.action} />
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

- [ ] **Step 2: Instagram caption**

Ask "Write an Instagram caption about `<a real, current topic>`." Expected: JARVIS researches it first (visible in tool-call metadata), speaks a one-line summary, and a content card appears with a real, Instagram-styled caption (punchy hook, 3-5 hashtags) grounded in something findable about the topic — not generic filler.

- [ ] **Step 3: Platform style differences**

Ask for a LinkedIn caption and an X post on the same topic. Expected: each reflects that platform's distinct style — LinkedIn professional/insight-driven with 1-2 hashtags, X concise with at most 1-2 hashtags.

- [ ] **Step 4: YouTube/podcast script**

Ask "Write a YouTube script about `<a real topic>`." Expected: a hook, body segments, and a call-to-action, written to be read aloud (not a formal document).

- [ ] **Step 5: Marketing copy**

Ask for marketing copy for a product or service. Expected: short and benefit-focused with a clear call-to-action.

- [ ] **Step 6: Copy button and voice-safe reply**

Confirm the content card's copy button actually copies the text, and that JARVIS's spoken/text reply itself stays voice-safe — no hashtags or bullets in the actual spoken text, those belong only in the card.

- [ ] **Step 7: Honest gaps**

Ask about a topic where little real information exists. Expected: JARVIS either says so or keeps the content generic/honest rather than inventing specific claims.

- [ ] **Step 8: Regression check**

Quickly re-verify business reports (4c) and company research (4b) still work unaffected.

- [ ] **Step 9: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 6: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Content Creation" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 5's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Blog articles.
- Presentations.
- Actual video/audio production (Section 5, AI Video Editing).
- Saved content history.
- Standalone trend-discovery/browsing feature.

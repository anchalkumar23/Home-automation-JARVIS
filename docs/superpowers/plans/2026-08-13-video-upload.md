# AI Video Editing — Increment 6b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user upload a video/audio file directly in the chat instead of typing a local file path — JARVIS prompts for it conversationally, shows upload progress, and automatically continues (e.g. generating subtitles) once the file lands.

**Architecture:** A new, generic `POST /api/uploads` endpoint saves files to `backend/data/uploads/`. A new `request_file_upload` tool produces a `file_upload_request` action, rendered as a `FileUploadCard` with real upload progress (via `XMLHttpRequest`, since plain `fetch` doesn't expose upload progress). On success, the card's callback feeds a synthetic message back through the existing chat pipeline (`handleSend`), so the model sees the uploaded file's path in a normal turn and calls `generate_subtitles` on it — no new backend orchestration needed for that part.

**Tech Stack:** FastAPI, Pydantic, Next.js/React/TypeScript. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-59` (`ClientAction`)
- Modify: `backend/app/schemas.py:73-75` (add `UploadResponse` after `TranscribeResponse`)
- Modify: `backend/app/services/tool_runner.py:79-85` (`extract_action`)

- [ ] **Step 1: Add the new action type and upload fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-59):
```python
class ClientAction(BaseModel):
    type: Literal[
        "open_url",
        "compose_email",
        "calendar_event_draft",
        "calendar_event_delete_confirm",
        "business_report",
        "content_draft",
        "subtitle_result",
        "file_upload_request",
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
    subtitle_file_path: str | None = None
    subtitle_content: str | None = None
    upload_purpose: str | None = None
```

- [ ] **Step 2: Add `UploadResponse`**

Modify `backend/app/schemas.py`, inserting a new model right after `TranscribeResponse` (current lines 73-75):
```python
class UploadResponse(BaseModel):
    file_path: str
    file_name: str
```

- [ ] **Step 3: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `subtitle_result` branch (current lines 79-84) and before `return None`:
```python
            if action_type == "file_upload_request":
                return ClientAction(
                    type="file_upload_request",
                    upload_purpose=action.get("upload_purpose") or "",
                )
```

- [ ] **Step 4: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 51 passed, no regressions.

---

### Task 2: Upload endpoint

**Files:**
- Create: `backend/app/routers/uploads.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the uploads router**

Create `backend/app/routers/uploads.py`:
```python
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import DATA_DIR
from app.schemas import UploadResponse

router = APIRouter(prefix="/api", tags=["uploads"])

UPLOADS_DIR = DATA_DIR / "uploads"


@router.post("/uploads", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}-{Path(file.filename).name}"
    destination = UPLOADS_DIR / safe_name

    with destination.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            out_file.write(chunk)

    return UploadResponse(file_path=str(destination), file_name=file.filename)
```
`Path(file.filename).name` strips any directory components from the original filename before it's used, so a malicious or malformed filename can't write outside `UPLOADS_DIR`. Streaming in 1MB chunks avoids holding an entire large video in memory while copying it to its final location.

- [ ] **Step 2: Register the router**

Modify `backend/app/main.py`, adding the import and registration:
```python
from app.routers.uploads import router as uploads_router
```
(inserted alphabetically among the other router imports, i.e. right after `from app.routers.transcribe import router as transcribe_router`)
```python
    app.include_router(uploads_router)
```
(inserted right after `app.include_router(tasks_router)`)

- [ ] **Step 3: Verify the endpoint works**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 4
"test content" | Out-File -Encoding utf8 "$env:TEMP\upload-test.txt"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/uploads" -Method Post -Form @{ file = Get-Item "$env:TEMP\upload-test.txt" }
```
Expected: a JSON response with `file_path` pointing into `backend\data\uploads\` and `file_name` = `upload-test.txt`. Confirm the file actually exists at that path afterward, then stop the test server (Ctrl+C in its window).

---

### Task 3: `request_file_upload` tool and system prompt

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_request_file_upload`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)
- Modify: `backend/app/ai/provider.py:83` (`SYSTEM_PROMPT` tool bullets)
- Modify: `backend/app/ai/provider.py:101` (extend rule 12)

- [ ] **Step 1: Add the tool implementation**

Modify `backend/app/ai/tools.py`, inserting right before `_tool_generate_subtitles` begins (current line 1019):
```python
def _tool_request_file_upload(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    purpose = str(args.get("purpose", "")).strip()
    if not purpose:
        raise ValueError("A purpose is required.")

    return {
        "action": {
            "type": "file_upload_request",
            "upload_purpose": purpose,
        },
        "message": f"Please upload the file for {purpose}.",
    }


```

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately before the `generate_subtitles` entry begins (current lines 270-287, starting with `{\n        "type": "function",\n        "function": {\n            "name": "generate_subtitles",`):
```python
    {
        "type": "function",
        "function": {
            "name": "request_file_upload",
            "description": "Prompt the user to upload a video/audio file when they want something done with one but haven't given a file path or uploaded a file yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "Short description of what the file will be used for, e.g. 'generating subtitles'.",
                    }
                },
                "required": ["purpose"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right before `"generate_subtitles": _tool_generate_subtitles,`:
```python
    "request_file_upload": _tool_request_file_upload,
```

- [ ] **Step 4: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right before the `generate_subtitles` bullet (current line 83):
```python
• request_file_upload — prompt the user to upload a video/audio file when they want something done with one but haven't given a path or uploaded yet
```

- [ ] **Step 5: Extend rule 12**

Modify `backend/app/ai/provider.py`, replacing rule 12 (current line 101, after Step 4's insertion shifts it down by one — locate it by content, not line number, since the bullet insertion in Step 4 shifts everything below it):
```python
12. When the user gives a local file path and asks for subtitles, captions, or a transcript file, call generate_subtitles — pass target_language only if they've asked for a translated version. If they want this done but haven't given a file path or uploaded a file yet, call request_file_upload first instead of just asking. Confirm what was generated and where it was saved.
```

- [ ] **Step 6: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 51 passed, no regressions. Confirm the token-budget regression guards in `test_provider.py` still pass — if either fails, trim the new tool's description rather than raising the ceiling.

---

### Task 4: Frontend — `FileUploadCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx:4` (icon import)
- Modify: `frontend/components/message-cards.tsx:9-40` (`ClientAction` interface)
- Modify: `frontend/components/message-cards.tsx` (append `FileUploadCard` at end of file)
- Modify: `frontend/components/jarvis-interface.tsx:7-21` (import block)
- Modify: `frontend/components/jarvis-interface.tsx` (render branch)

- [ ] **Step 1: Add the `UploadCloud` icon import**

Modify `frontend/components/message-cards.tsx`, replacing the lucide-react import (current line 4):
```tsx
import { CalendarClock, Check, ClipboardCopy, Download, FileText, Loader2, Mail, Maximize2, UploadCloud, X } from "lucide-react"
```

- [ ] **Step 2: Add the new action type and field to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, replacing the `type` union and adding a field in the `ClientAction` interface (current lines 9-40) — add `"file_upload_request"` to the union and `upload_purpose?: string` at the end:
```tsx
export interface ClientAction {
  type:
    | "open_url"
    | "compose_email"
    | "calendar_event_draft"
    | "calendar_event_delete_confirm"
    | "business_report"
    | "content_draft"
    | "subtitle_result"
    | "file_upload_request"
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
  subtitle_file_path?: string
  subtitle_content?: string
  upload_purpose?: string
}
```

- [ ] **Step 3: Add `FileUploadCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `SubtitleResultCard` closes:
```tsx

/* ── File Upload Card ──────────────────────────────────────────────────── */

export function FileUploadCard({
  action,
  backendUrl,
  onUploaded,
}: {
  action: ClientAction
  backendUrl: string
  onUploaded: (filePath: string, fileName: string) => void
}) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (file: File) => {
    setUploading(true)
    setProgress(0)
    setError(null)

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${backendUrl}/api/uploads`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      setUploading(false)
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          setDone(true)
          onUploaded(data.file_path, data.file_name)
        } catch {
          setError("Upload succeeded but the response was invalid.")
        }
      } else {
        setError(`Upload failed (${xhr.status}).`)
      }
    }
    xhr.onerror = () => {
      setUploading(false)
      setError("Upload failed — check your connection to the backend.")
    }

    const formData = new FormData()
    formData.append("file", file)
    xhr.send(formData)
  }

  if (done) {
    return (
      <div className="mt-3 rounded-lg border border-accent/30 bg-accent/5 p-3 text-[11px] text-accent">
        Upload complete — continuing…
      </div>
    )
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
      }}
      className="mt-3 space-y-2 rounded-lg border border-dashed border-accent/40 bg-accent/5 p-4 text-center"
    >
      <div className="flex items-center justify-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <UploadCloud className="h-3 w-3" />
        Upload for {action.upload_purpose || "processing"}
      </div>
      {uploading ? (
        <div className="space-y-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-accent/15">
            <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="font-mono text-[10px] text-muted-foreground">Uploading… {progress}%</p>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-accent-foreground transition-opacity hover:opacity-90"
        >
          Choose File
        </button>
      )}
      {error && <p className="text-[10px] text-destructive">{error}</p>}
      <input
        ref={inputRef}
        type="file"
        accept="video/*,audio/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
    </div>
  )
}
```

- [ ] **Step 4: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-21) to add `FileUploadCard`:
```tsx
import {
  BusinessReportCard,
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  ContentDraftCard,
  EmailDraftCard,
  FileUploadCard,
  ImageModal,
  InlineImage,
  ReadSourceTag,
  type SearchResult,
  SearchSourcesCard,
  SubtitleResultCard,
  TypewriterText,
} from "@/components/message-cards"
```

- [ ] **Step 5: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `subtitle_result` block (current lines 859-862), before the "Web search sources" comment:
```tsx
                  {/* File upload prompt for video-editing tools */}
                  {message.action?.type === "file_upload_request" && (
                    <FileUploadCard
                      action={message.action}
                      backendUrl={BACKEND_URL}
                      onUploaded={(filePath, fileName) =>
                        handleSend(`Uploaded video: ${fileName} at ${filePath}`)
                      }
                    />
                  )}
```
`handleSend` and `BACKEND_URL` are already in scope at this point in the component — no new imports or props needed.

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
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too — check with a quick request to `http://127.0.0.1:3000` and restart it if not.

- [ ] **Step 2: Trigger the upload prompt**

Ask "I want to add subtitles to my video" with no file path given. Expected: JARVIS responds with an upload prompt card (not a plain text question, not a failed tool call).

- [ ] **Step 3: Upload and auto-continue**

Click "Choose File" (or drag a file onto the card) and pick a real video file, ideally a few hundred MB to actually observe progress. Expected: a progress bar advances during upload; once complete, JARVIS automatically proceeds to generate subtitles for the uploaded file without any further typing — a `.srt` appears next to the uploaded copy in `backend\data\uploads\`, and the subtitle preview card appears in chat.

- [ ] **Step 4: Path-based flow still works**

Ask "generate subtitles for `C:\path\to\some\other\clip.mp4`" (a direct path, not an upload). Expected: works exactly as it did before this increment — both input modes coexist.

- [ ] **Step 5: Unsupported file**

Upload a non-media file (e.g. a `.txt` renamed to look plausible, or just any non-video file). Expected: a clear error surfaces (from the ffmpeg-extraction stage, consistent with 6a's existing error handling) rather than a silent hang.

- [ ] **Step 6: Regression check**

Quickly re-verify voice input (mic button, `/api/transcribe`) still works unaffected.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 6: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Update the Subtitle Generation section**

Modify `docs/testing-guide.md`, updating the existing "Subtitle Generation" section (added in 6a) to mention the new upload flow as an alternative to typing a path — add the upload-trigger and upload-progress steps from Task 5 above, keeping the existing path-based steps intact underneath as the still-supported alternative flow.

---

## Post-plan: what's explicitly not in this increment

- Automatic cleanup of `backend/data/uploads/`.
- In-browser audio pre-extraction before upload.
- Wiring `request_file_upload` into other video-editing tools (as those get built).
- Always-visible attach button.

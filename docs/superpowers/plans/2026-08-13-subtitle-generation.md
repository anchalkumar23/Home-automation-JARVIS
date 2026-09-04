# AI Video Editing — Increment 6a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `generate_subtitles` tool that extracts audio from a local video/audio file via `ffmpeg`, transcribes it with Groq (segment timestamps), optionally translates it, and saves a real `.srt` file next to the source — the first JARVIS capability that processes actual media files.

**Architecture:** The tool is entirely self-contained in `backend/app/ai/tools.py` — its own multipart-request builder (a small, deliberate duplication of `transcribe.py`'s pattern rather than a cross-module import, since reusing it would create a backwards `tools → routers` dependency, and this project's own convention is not to extract shared utilities until something is reused 3+ times). No confirmation gate: writing a new sidecar `.srt` file is local and reversible, the same tier as `add_task`.

**Tech Stack:** FastAPI, stdlib `urllib`/`subprocess`/`tempfile`/`shutil`, pytest, Next.js/React/TypeScript. `ffmpeg` is a new **system-level** dependency (not a Python package) — the user installs it once, confirmed in brainstorming.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-55` (`ClientAction`)
- Modify: `backend/app/services/tool_runner.py:63-70` (`extract_action`)

- [ ] **Step 1: Add the new action type and subtitle fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class:
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
```

- [ ] **Step 2: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `content_draft` branch and before `return None`:
```python
            if action_type == "subtitle_result":
                return ClientAction(
                    type="subtitle_result",
                    subtitle_file_path=action.get("subtitle_file_path") or "",
                    subtitle_content=action.get("subtitle_content") or "",
                )
```

- [ ] **Step 3: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 48 passed, no regressions.

---

### Task 2: `_build_srt` helper (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_srt_timestamp`, `_build_srt`)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_build_srt_formats_single_segment():
    from app.ai.tools import _build_srt

    segments = [{"start": 0.0, "end": 2.5, "text": "Hello world"}]

    assert _build_srt(segments) == "1\n00:00:00,000 --> 00:00:02,500\nHello world\n"


def test_build_srt_numbers_sequentially_and_formats_hours():
    from app.ai.tools import _build_srt

    segments = [
        {"start": 0.0, "end": 1.0, "text": "First"},
        {"start": 3661.25, "end": 3662.75, "text": "Second, after an hour"},
    ]
    srt = _build_srt(segments)

    assert "1\n00:00:00,000 --> 00:00:01,000\nFirst\n" in srt
    assert "2\n01:01:01,250 --> 01:01:02,750\nSecond, after an hour\n" in srt


def test_build_srt_handles_empty_segments():
    from app.ai.tools import _build_srt

    assert _build_srt([]) == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_build_srt' from 'app.ai.tools'` on the 3 new tests.

- [ ] **Step 3: Add `_srt_timestamp` and `_build_srt`**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_create_content` ends (current line 916, `"message": f"I've drafted {CONTENT_FORMAT_LABELS[content_type]} on {topic}.",\n    }`) and before `_tool_play_music` begins:
```python
def _srt_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, ms = divmod(remainder_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _build_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for i, segment in enumerate(segments, start=1):
        start = _srt_timestamp(float(segment.get("start", 0)))
        end = _srt_timestamp(float(segment.get("end", 0)))
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 51 passed (48 from before + 3 new).

---

### Task 3: `generate_subtitles` tool

**Files:**
- Modify: `backend/app/ai/tools.py:1-19` (imports)
- Modify: `backend/app/ai/tools.py` (add `_build_groq_audio_multipart`, `_translate_segments`, `_tool_generate_subtitles`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add new imports**

Modify `backend/app/ai/tools.py`, replacing the top import block (current lines 1-19):
```python
from __future__ import annotations

import io
import json
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import Settings, get_settings
from app.services import google_auth
from app.services.memory import MemoryStore
```

- [ ] **Step 2: Add the tool's implementation**

Modify `backend/app/ai/tools.py`, inserting right after `_build_srt` ends (from Task 2) and before `_tool_play_music` begins:
```python
def _build_groq_audio_multipart(
    filename: str, file_bytes: bytes, model: str, extra_fields: dict[str, str]
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
    ]
    for field_name, field_value in extra_fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"\r\n\r\n{field_value}\r\n'.encode(
                "utf-8"
            )
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: audio/mpeg\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _translate_segments(
    segments: list[dict[str, Any]], target_language: str, settings: Settings
) -> list[dict[str, Any]]:
    if not settings.groq_api_key:
        return segments

    numbered_lines = "\n".join(f"{i}: {seg.get('text', '').strip()}" for i, seg in enumerate(segments))
    prompt = (
        f"Translate each numbered line into {target_language}. Reply with ONLY the same "
        f"numbered format, one translated line per number, no extra commentary.\n\n{numbered_lines}"
    )
    payload = {"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        translated_text = data["choices"][0]["message"]["content"]
    except Exception:
        return segments

    translated_map: dict[int, str] = {}
    for line in translated_text.splitlines():
        index_str, sep, text = line.partition(":")
        if sep and index_str.strip().isdigit():
            translated_map[int(index_str.strip())] = text.strip()

    return [{**seg, "text": translated_map.get(i, seg.get("text", ""))} for i, seg in enumerate(segments)]


def _tool_generate_subtitles(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        raise ValueError("A file path is required.")

    video_path = Path(file_path)
    if not video_path.is_file():
        return {"error": f"I couldn't find a file at {file_path}."}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"error": "ffmpeg isn't installed on this machine. Install it and try again."}

    settings = get_settings()
    if not settings.groq_api_key:
        return {"error": "Subtitle generation needs a Groq API key configured."}

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "audio.mp3"
        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to extract audio: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": "Audio extraction timed out — the file may be too long."}

        audio_bytes = audio_path.read_bytes()

    body, content_type = _build_groq_audio_multipart(
        "audio.mp3",
        audio_bytes,
        settings.groq_whisper_model,
        {"response_format": "verbose_json", "timestamp_granularities[]": "segment"},
    )
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": content_type,
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Transcription failed: {exc}"}

    segments = payload.get("segments") or []
    if not segments:
        return {"error": "No speech was detected in that file."}

    target_language = str(args.get("target_language") or "").strip()
    if target_language:
        segments = _translate_segments(segments, target_language, settings)

    srt_content = _build_srt(segments)

    output_path = video_path.with_suffix(".srt")
    suffix_index = 2
    while output_path.exists():
        output_path = video_path.with_name(f"{video_path.stem}-{suffix_index}.srt")
        suffix_index += 1

    output_path.write_text(srt_content, encoding="utf-8")

    return {
        "action": {
            "type": "subtitle_result",
            "subtitle_file_path": str(output_path),
            "subtitle_content": srt_content,
        },
        "message": f"I've generated subtitles and saved them to {output_path.name}.",
    }
```

- [ ] **Step 3: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `create_content` entry closes (current lines 237-264, ending `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "generate_subtitles",
            "description": "Generate a .srt subtitle file for a local video/audio file, saved next to the source file. Requires ffmpeg to be installed on this machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "target_language": {
                        "type": ["string", "null"],
                        "description": "If given, translates subtitles into this language (e.g. Spanish). Leave empty to keep the original spoken language.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
```

- [ ] **Step 4: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"create_content": _tool_create_content,`:
```python
    "generate_subtitles": _tool_generate_subtitles,
```

- [ ] **Step 5: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 51 passed, no regressions. If `test_system_prompt_and_tool_definitions_stay_within_token_budget` or `test_no_single_tool_description_is_excessively_verbose` (added in an earlier increment) fail, trim the new tool's description further before proceeding — do not raise the budget ceiling to make it pass.

---

### Task 4: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:82` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:99-100` (insert new rule 12, renumber personality rule to 13)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `create_content` bullet (current line 82):
```python
• generate_subtitles — generate a .srt file for a local video/audio file, optionally translated; requires ffmpeg
```

- [ ] **Step 2: Insert the new rule and renumber the personality rule**

Modify `backend/app/ai/provider.py`, replacing rule 12 and the closing `"""` (current lines 99-100, which currently read rule 12 as the personality rule):
```python
12. When the user gives a local file path and asks for subtitles, captions, or a transcript file, call generate_subtitles — pass target_language only if they've asked for a translated version. Confirm what was generated and where it was saved.
13. Be warm and professional, like JARVIS from Iron Man — occasional wit, always helpful.
"""
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 51 passed, no regressions.

---

### Task 5: Frontend — `SubtitleResultCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx` (`ClientAction` interface, append new component)
- Modify: `frontend/components/jarvis-interface.tsx` (import block, render branch)

- [ ] **Step 1: Add subtitle fields to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, adding `"subtitle_result"` to the `type` union in the exported `ClientAction` interface, and adding two new optional fields at the end of the interface:
```tsx
  subtitle_file_path?: string
  subtitle_content?: string
```

- [ ] **Step 2: Add `SubtitleResultCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `ContentDraftCard` closes:
```tsx

/* ── Subtitle Result Card ──────────────────────────────────────────────── */

export function SubtitleResultCard({ action }: { action: ClientAction }) {
  const content = action.subtitle_content || ""
  if (!content) return null

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
          <FileText className="h-3 w-3" />
          Subtitles{action.subtitle_file_path ? `: ${action.subtitle_file_path}` : ""}
        </div>
        <CopyButton text={content} label="Copy" />
      </div>
      <pre className="max-h-[240px] overflow-y-auto whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-foreground">
        {content}
      </pre>
    </div>
  )
}
```
This reuses the existing internal `CopyButton` and the `FileText` icon already imported at the top of the file — no new imports needed for this component.

- [ ] **Step 3: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, adding `SubtitleResultCard` to the `@/components/message-cards` import list (alongside `ContentDraftCard`).

- [ ] **Step 4: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `content_draft` render block:
```tsx
                  {/* Subtitle generation result */}
                  {message.action?.type === "subtitle_result" && (
                    <SubtitleResultCard action={message.action} />
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

### Task 6: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Confirm ffmpeg is installed**

Run:
```powershell
ffmpeg -version
```
Expected: version info prints. If not installed, install it first (e.g. `winget install ffmpeg` or from ffmpeg.org) before continuing.

- [ ] **Step 2: Restart the backend**

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

- [ ] **Step 3: Generate subtitles for a real file**

Ask JARVIS to generate subtitles for a real local video/audio file by path (e.g. "generate subtitles for `C:\path\to\clip.mp4`"). Expected: a `.srt` file appears next to the source file, with real, accurately-timed captions, and a preview card with a working copy button appears in the chat.

- [ ] **Step 4: Non-clobbering re-run**

Ask for the same file again. Expected: it doesn't overwrite the first `.srt` — a distinctly-named file appears instead (e.g. `clip-2.srt`).

- [ ] **Step 5: Translation**

Ask for subtitles with a target language (e.g. "...and translate them to Spanish"). Expected: the subtitle text is genuinely translated while timing stays intact.

- [ ] **Step 6: Missing file**

Ask for subtitles for a nonexistent path. Expected: a clear "couldn't find that file" message, not a crash.

- [ ] **Step 7: Unsupported file**

Try a path to a non-media file (e.g. a `.txt` file). Expected: a clear ffmpeg-extraction error, not garbled output or a hang.

- [ ] **Step 8: Regression check**

Quickly re-verify voice input (mic button) still works — it uses the same Groq transcription API, just a different endpoint call.

- [ ] **Step 9: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 7: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Subtitle Generation" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 6's manual verification steps above. Mention the `ffmpeg` prerequisite explicitly as a first-time setup step.

---

## Post-plan: what's explicitly not in this increment

- Silence removal / automatic rough cuts.
- Thumbnail generation.
- Highlight detection / automatic Shorts-Reels generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration, multi-format export.
- Burning subtitles into the video itself.
- Browser-based file upload.

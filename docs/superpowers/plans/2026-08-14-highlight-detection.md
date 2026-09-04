# AI Video Editing — Increment 6e Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `detect_highlights` tool that transcribes a local video/audio file, asks the LLM to identify the most compelling moments, and cuts each into its own clip — reusing the file-input flow (path or upload) and transcription approach already built in 6a/6b.

**Architecture:** Transcription reuses 6a's `ffmpeg` audio-extraction + Groq `verbose_json` pattern (duplicated inline, not extracted into a shared helper yet — this is only the second use of that flow, and this project's convention is to extract shared utilities at 3+ uses, not 2). Highlight selection is a self-contained Groq chat-completion call within the tool (same pattern as `_translate_segments`, avoiding a circular import with `app.ai.provider`). Two new pure helpers — building the timestamped transcript and parsing/validating the LLM's JSON response — get TDD unit tests, following 6a/6c's precedent.

**Tech Stack:** FastAPI, stdlib `subprocess`/`json`/`urllib`, pytest, Next.js/React/TypeScript. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-67` (`ClientAction`)
- Modify: `backend/app/services/tool_runner.py:90-98` (`extract_action`)

- [ ] **Step 1: Add the new action type and highlight-clips field**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-67):
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
        "silence_removal_result",
        "highlight_detection_result",
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
    silence_output_path: str | None = None
    silence_original_duration: float | None = None
    silence_new_duration: float | None = None
    silence_removed_seconds: float | None = None
    silence_segment_count: int | None = None
    highlight_clips: list[dict[str, Any]] | None = None
```

- [ ] **Step 2: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `silence_removal_result` branch (current lines 90-98) and before `return None`:
```python
            if action_type == "highlight_detection_result":
                return ClientAction(
                    type="highlight_detection_result",
                    highlight_clips=action.get("highlight_clips") or [],
                )
```

- [ ] **Step 3: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 62 passed, no regressions.

---

### Task 2: Pure helpers — timestamped transcript and highlight-response parsing (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_build_timestamped_transcript`, `_parse_highlight_response`)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_build_timestamped_transcript_formats_segments():
    from app.ai.tools import _build_timestamped_transcript

    segments = [{"start": 0.0, "text": "Hello"}, {"start": 12.345, "text": "world"}]

    assert _build_timestamped_transcript(segments) == "[0.0s] Hello\n[12.3s] world"


def test_build_timestamped_transcript_handles_empty_segments():
    from app.ai.tools import _build_timestamped_transcript

    assert _build_timestamped_transcript([]) == ""


def test_parse_highlight_response_extracts_valid_highlights():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([
        {"start": 10.0, "end": 25.0, "reason": "Great opening hook"},
        {"start": 60.0, "end": 90.0, "reason": "Key insight about the topic"},
    ])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [
        {"start": 10.0, "end": 25.0, "reason": "Great opening hook"},
        {"start": 60.0, "end": 90.0, "reason": "Key insight about the topic"},
    ]


def test_parse_highlight_response_clamps_out_of_range_timestamps():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([{"start": -5.0, "end": 200.0, "reason": "Whole thing"}])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [{"start": 0.0, "end": 120.0, "reason": "Whole thing"}]


def test_parse_highlight_response_drops_invalid_entries():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([
        {"start": 10.0, "end": 5.0, "reason": "end before start"},
        {"start": "not-a-number", "end": 20.0, "reason": "bad start"},
        {"start": 30.0, "end": 40.0, "reason": ""},
        {"start": 50.0, "end": 60.0, "reason": "valid one"},
    ])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [{"start": 50.0, "end": 60.0, "reason": "valid one"}]


def test_parse_highlight_response_truncates_to_max_highlights():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps(
        [{"start": i * 10.0, "end": i * 10.0 + 5.0, "reason": f"clip {i}"} for i in range(5)]
    )

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=2)

    assert len(highlights) == 2


def test_parse_highlight_response_handles_unparseable_json():
    from app.ai.tools import _parse_highlight_response

    assert _parse_highlight_response("not json", duration=120.0, max_highlights=5) == []


def test_parse_highlight_response_handles_non_list_json():
    from app.ai.tools import _parse_highlight_response

    assert _parse_highlight_response('{"not": "a list"}', duration=120.0, max_highlights=5) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError` on all 8 new tests.

- [ ] **Step 3: Add the two pure helpers**

Modify `backend/app/ai/tools.py`, inserting right before `_tool_request_file_upload` begins (find it by searching for `def _tool_request_file_upload`):
```python
def _build_timestamped_transcript(segments: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[{float(seg.get('start', 0)):.1f}s] {str(seg.get('text', '')).strip()}" for seg in segments
    )


def _parse_highlight_response(raw_json: str, duration: float, max_highlights: int) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        return []

    highlights: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        reason = str(item.get("reason", "")).strip()
        if not reason:
            continue

        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))
        if end <= start:
            continue

        highlights.append({"start": start, "end": end, "reason": reason})

    return highlights[:max_highlights]


```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 70 passed (62 from before + 8 new).

---

### Task 3: `detect_highlights` tool

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_detect_highlights`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add the tool implementation**

Modify `backend/app/ai/tools.py`, inserting right after `_parse_highlight_response` ends (from Task 2) and before `_tool_request_file_upload` begins:
```python
def _tool_detect_highlights(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
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
        return {"error": "Highlight detection needs a Groq API key configured."}

    max_highlights = int(args.get("max_highlights") or 5)

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

    duration = float(segments[-1].get("end", 0))

    transcript = _build_timestamped_transcript(segments)
    prompt = (
        f"Here is a timestamped transcript of a video. Identify up to {max_highlights} distinct, "
        "genuinely compelling moments for short-form highlight clips (funny lines, key insights, "
        "strong hooks, surprising statements). Reply with ONLY a JSON array, no other text, in this "
        'exact shape: [{"start": <seconds>, "end": <seconds>, "reason": "<short reason>"}]. '
        f"Each clip should be roughly 15 to 60 seconds long.\n\n{transcript}"
    )
    chat_payload = {"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}]}
    chat_request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(chat_payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(chat_request, timeout=60) as response:
            chat_data = json.loads(response.read().decode("utf-8"))
        raw_highlights = chat_data["choices"][0]["message"]["content"]
    except Exception as exc:
        return {"error": f"Highlight selection failed: {exc}"}

    highlights = _parse_highlight_response(raw_highlights, duration, max_highlights)
    if not highlights:
        return {"error": "I couldn't identify any clear highlights in that file."}

    clips: list[dict[str, Any]] = []
    for i, highlight in enumerate(highlights, start=1):
        output_path = video_path.with_name(f"{video_path.stem}-highlight-{i}{video_path.suffix}")
        suffix_index = 2
        while output_path.exists():
            output_path = video_path.with_name(
                f"{video_path.stem}-highlight-{i}-{suffix_index}{video_path.suffix}"
            )
            suffix_index += 1

        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-ss", str(highlight["start"]),
                    "-t", str(highlight["end"] - highlight["start"]),
                    "-i", str(video_path),
                    "-c:v", "libx264", "-c:a", "aac",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to cut highlight {i}: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": f"Cutting highlight {i} timed out."}

        clips.append(
            {
                "path": str(output_path),
                "start": round(highlight["start"], 1),
                "end": round(highlight["end"], 1),
                "reason": highlight["reason"],
            }
        )

    return {
        "action": {
            "type": "highlight_detection_result",
            "highlight_clips": clips,
        },
        "message": f"I've found {len(clips)} highlight{'s' if len(clips) != 1 else ''} and saved them as clips.",
    }


```
Note: `duration` is derived from the last transcribed segment's end time rather than a separate `ffprobe`/duration-parsing call — close enough for clamping purposes, and avoids an extra subprocess call. This differs from `remove_silence`, which needs the *exact* file duration (to know how much trailing silence exists past the last segment); highlight clamping only needs an upper bound.

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `remove_silence` entry closes (find it by searching for `"name": "remove_silence"` and its closing `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "detect_highlights",
            "description": "Find the most compelling moments in a local video/audio file and clip them out, saved next to the source. Requires ffmpeg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "max_highlights": {
                        "type": ["number", "null"],
                        "description": "Maximum number of highlight clips to produce. Defaults to 5.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"remove_silence": _tool_remove_silence,`:
```python
    "detect_highlights": _tool_detect_highlights,
```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 70 passed, no regressions. Confirm the token-budget regression guards in `test_provider.py` still pass — if either fails, trim the new tool's description rather than raising the ceiling.

---

### Task 4: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:85` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:103` (extend rule 12)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `remove_silence` bullet (current line 85):
```python
• detect_highlights — find compelling moments in a local video/audio file and clip them out; requires ffmpeg
```

- [ ] **Step 2: Extend rule 12**

Modify `backend/app/ai/provider.py`, replacing rule 12 (locate by its current content, since line numbers shift after Step 1's insertion):
```python
12. When the user gives a local file path (or has uploaded a file) and asks for subtitles, captions, a transcript, silence removal, a rough cut, or highlight/Shorts clips, call generate_subtitles, remove_silence, or detect_highlights accordingly — pass target_language/min_silence_seconds/max_highlights only if specified. If they want this done but haven't given a file path or uploaded a file yet, call request_file_upload first instead of just asking. Confirm what was generated and where it was saved.
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 70 passed, no regressions.

---

### Task 5: Frontend — `HighlightDetectionResultCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx:9-47` (`ClientAction` interface)
- Modify: `frontend/components/message-cards.tsx` (append `HighlightDetectionResultCard` at end of file)
- Modify: `frontend/components/jarvis-interface.tsx:7-22` (import block)
- Modify: `frontend/components/jarvis-interface.tsx` (render branch)

- [ ] **Step 1: Add the new action type and field to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, replacing the `ClientAction` interface (current lines 9-47) to add `"highlight_detection_result"` to the `type` union and one new field at the end:
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
    | "silence_removal_result"
    | "highlight_detection_result"
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
  silence_output_path?: string
  silence_original_duration?: number
  silence_new_duration?: number
  silence_removed_seconds?: number
  silence_segment_count?: number
  highlight_clips?: { path: string; start: number; end: number; reason: string }[]
}
```

- [ ] **Step 2: Add `HighlightDetectionResultCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `SilenceRemovalResultCard` closes:
```tsx

/* ── Highlight Detection Result Card ───────────────────────────────────── */

export function HighlightDetectionResultCard({ action }: { action: ClientAction }) {
  const clips = action.highlight_clips || []
  if (!clips.length) return null

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Highlights
      </div>
      <div className="space-y-2.5">
        {clips.map((clip, i) => (
          <div key={`${clip.path}-${i}`}>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
              {clip.start.toFixed(1)}s – {clip.end.toFixed(1)}s
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-foreground">{clip.reason}</p>
            <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{clip.path}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
```
Reuses the already-imported `FileText` icon — no new icon import needed.

- [ ] **Step 3: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-22) to add `HighlightDetectionResultCard`:
```tsx
import {
  BusinessReportCard,
  CalendarEventDeleteConfirm,
  CalendarEventDraftCard,
  type ClientAction,
  ContentDraftCard,
  EmailDraftCard,
  FileUploadCard,
  HighlightDetectionResultCard,
  ImageModal,
  InlineImage,
  ReadSourceTag,
  type SearchResult,
  SearchSourcesCard,
  SilenceRemovalResultCard,
  SubtitleResultCard,
  TypewriterText,
```
(remaining lines of the import block unchanged)

- [ ] **Step 4: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `silence_removal_result` block and before the `file_upload_request` block:
```tsx
                  {/* Highlight detection result */}
                  {message.action?.type === "highlight_detection_result" && (
                    <HighlightDetectionResultCard action={message.action} />
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
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too. If any PowerShell command hangs unexpectedly, fall back to starting the server directly via a bash-compatible shell (`nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 &`) rather than waiting indefinitely.

- [ ] **Step 2: Find highlights in a real file**

Upload or point to a real video/audio file with clearly distinct moments (e.g. a podcast with a few notable quotes or jokes). Ask JARVIS to find highlights. Confirm multiple clips are produced, each corresponding to a genuinely distinct, sensible moment — not arbitrary/repeated slices.

- [ ] **Step 3: Verify the result card and playback**

Confirm the result card lists each clip's time range, reason, and file path accurately. Play back a generated clip and confirm it actually contains the highlighted moment, correctly timed.

- [ ] **Step 4: Custom max_highlights**

Ask again with a custom count (e.g. "just find the best 2 highlights") and confirm the count is respected.

- [ ] **Step 5: Low-content case**

Try a very short or low-content file where genuine highlights are hard to identify. Confirm a clear "couldn't identify any highlights" message rather than fabricated/nonsensical clips.

- [ ] **Step 6: Non-clobbering output**

Run it twice on the same file. Confirm the second run's clips don't overwrite the first (independently non-clobbering per clip).

- [ ] **Step 7: Upload-triggered flow**

Ask "find highlights in my podcast" with no file given. Confirm the upload prompt card appears, and `detect_highlights` is what runs after uploading — not `generate_subtitles` or `remove_silence`.

- [ ] **Step 8: Regression check**

Quickly re-verify subtitle generation (6a) and silence removal (6c) still work unaffected.

- [ ] **Step 9: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 7: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Highlight Detection" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 6's manual verification steps above. Mention that it reuses the same upload/path flow as subtitle generation and silence removal.

---

## Post-plan: what's explicitly not in this increment

- Vertical (9:16) reformatting for Shorts/Reels.
- Thumbnail generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration.

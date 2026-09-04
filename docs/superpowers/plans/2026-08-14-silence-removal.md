# AI Video Editing — Increment 6c Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `remove_silence` tool that detects and cuts silent gaps from a local video/audio file via `ffmpeg`, saving a new edited copy — reusing the file-input flow (path or upload) already built in 6a/6b.

**Architecture:** Silence detection (`ffmpeg silencedetect`) and duration parsing are pure-logic helpers with unit tests, following 6a's `_build_srt` precedent. Cutting uses a two-phase approach: re-encode each non-silent "keep" segment to a temp file, then stitch them together via ffmpeg's concat demuxer — avoiding one giant, fragile filter graph for videos with many silence gaps.

**Tech Stack:** FastAPI, stdlib `subprocess`/`re`/`tempfile`, pytest, Next.js/React/TypeScript. No new dependencies (reuses the `ffmpeg` dependency already required by 6a).

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Schema and action-extraction changes

**Files:**
- Modify: `backend/app/schemas.py:28-61` (`ClientAction`)
- Modify: `backend/app/services/tool_runner.py:85-89` (`extract_action`)

- [ ] **Step 1: Add the new action type and silence-removal fields**

Modify `backend/app/schemas.py`, replacing the `ClientAction` class (current lines 28-61):
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
```

- [ ] **Step 2: Add the extraction branch**

Modify `backend/app/services/tool_runner.py`, inserting a new branch in `extract_action` right after the `file_upload_request` branch (current lines 85-89) and before `return None`:
```python
            if action_type == "silence_removal_result":
                return ClientAction(
                    type="silence_removal_result",
                    silence_output_path=action.get("silence_output_path") or "",
                    silence_original_duration=action.get("silence_original_duration"),
                    silence_new_duration=action.get("silence_new_duration"),
                    silence_removed_seconds=action.get("silence_removed_seconds"),
                    silence_segment_count=action.get("silence_segment_count"),
                )
```

- [ ] **Step 3: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 51 passed, no regressions.

---

### Task 2: Pure helpers — silence parsing, duration parsing, keep-segment computation (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_parse_silencedetect_output`, `_parse_ffmpeg_duration`, `_compute_keep_segments`)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_parse_silencedetect_output_extracts_intervals():
    from app.ai.tools import _parse_silencedetect_output

    stderr_text = (
        "[silencedetect @ 0x1] silence_start: 2.5\n"
        "[silencedetect @ 0x1] silence_end: 4.2 | silence_duration: 1.7\n"
        "[silencedetect @ 0x1] silence_start: 8.0\n"
        "[silencedetect @ 0x1] silence_end: 9.1 | silence_duration: 1.1\n"
    )

    assert _parse_silencedetect_output(stderr_text) == [(2.5, 4.2), (8.0, 9.1)]


def test_parse_silencedetect_output_handles_no_silence():
    from app.ai.tools import _parse_silencedetect_output

    assert _parse_silencedetect_output("no silence markers here") == []


def test_parse_ffmpeg_duration_extracts_seconds():
    from app.ai.tools import _parse_ffmpeg_duration

    stderr_text = "  Duration: 00:05:23.40, start: 0.000000, bitrate: 128 kb/s"

    assert _parse_ffmpeg_duration(stderr_text) == 323.4


def test_parse_ffmpeg_duration_handles_missing_duration():
    from app.ai.tools import _parse_ffmpeg_duration

    assert _parse_ffmpeg_duration("no duration here") == 0.0


def test_compute_keep_segments_removes_padded_silence():
    from app.ai.tools import _compute_keep_segments

    segments = _compute_keep_segments([(2.0, 4.0)], duration=10.0, padding=0.15)

    assert segments == [(0.0, 2.15), (3.85, 10.0)]


def test_compute_keep_segments_skips_silence_too_short_after_padding():
    from app.ai.tools import _compute_keep_segments

    # silence is 0.2s long; padding*2 = 0.3s > 0.2s, so nothing gets cut here
    segments = _compute_keep_segments([(5.0, 5.2)], duration=10.0, padding=0.15)

    assert segments == [(0.0, 10.0)]


def test_compute_keep_segments_handles_no_silence():
    from app.ai.tools import _compute_keep_segments

    assert _compute_keep_segments([], duration=10.0) == [(0.0, 10.0)]


def test_compute_keep_segments_handles_multiple_silences():
    from app.ai.tools import _compute_keep_segments

    segments = _compute_keep_segments([(2.0, 3.0), (6.0, 7.0)], duration=10.0, padding=0.1)

    assert segments == [(0.0, 2.1), (2.9, 6.1), (6.9, 10.0)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError` on all 7 new tests (the functions don't exist yet).

- [ ] **Step 3: Add the three pure helpers**

Modify `backend/app/ai/tools.py`, inserting right before `_tool_request_file_upload` begins (find it by searching for `def _tool_request_file_upload`):
```python
def _parse_silencedetect_output(stderr_text: str) -> list[tuple[float, float]]:
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", stderr_text)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", stderr_text)]
    return list(zip(starts, ends))


def _parse_ffmpeg_duration(stderr_text: str) -> float:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _compute_keep_segments(
    silence_intervals: list[tuple[float, float]], duration: float, padding: float = 0.15
) -> list[tuple[float, float]]:
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in silence_intervals:
        cut_start = start + padding
        cut_end = end - padding
        if cut_end <= cut_start:
            continue
        if cut_start > cursor:
            keep.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if cursor < duration:
        keep.append((cursor, duration))
    return keep


```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 58 passed (51 from before + 7 new).

---

### Task 3: `remove_silence` tool

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_remove_silence`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add the tool implementation**

Modify `backend/app/ai/tools.py`, inserting right after `_compute_keep_segments` ends (from Task 2) and before `_tool_request_file_upload` begins:
```python
def _tool_remove_silence(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        raise ValueError("A file path is required.")

    video_path = Path(file_path)
    if not video_path.is_file():
        return {"error": f"I couldn't find a file at {file_path}."}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"error": "ffmpeg isn't installed on this machine. Install it and try again."}

    min_silence_seconds = float(args.get("min_silence_seconds") or 0.5)

    try:
        detect_result = subprocess.run(
            [
                ffmpeg_path, "-i", str(video_path),
                "-af", f"silencedetect=noise=-30dB:d={min_silence_seconds}",
                "-f", "null", "-",
            ],
            capture_output=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"error": "Silence detection timed out — the file may be too long."}

    stderr_text = detect_result.stderr.decode("utf-8", errors="replace")

    duration = _parse_ffmpeg_duration(stderr_text)
    if duration <= 0:
        return {"error": "Couldn't determine the file's duration."}

    silence_intervals = _parse_silencedetect_output(stderr_text)
    if not silence_intervals:
        return {"error": "No meaningful silence was detected in that file."}

    keep_segments = _compute_keep_segments(silence_intervals, duration)
    if len(keep_segments) <= 1 and keep_segments and keep_segments[0] == (0.0, duration):
        return {"error": "No meaningful silence was detected in that file."}

    with tempfile.TemporaryDirectory() as tmp_dir:
        segment_paths: list[Path] = []
        for i, (start, end) in enumerate(keep_segments):
            segment_path = Path(tmp_dir) / f"segment_{i}.mp4"
            try:
                subprocess.run(
                    [
                        ffmpeg_path, "-y", "-ss", str(start), "-t", str(end - start), "-i", str(video_path),
                        "-c:v", "libx264", "-c:a", "aac",
                        str(segment_path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=1800,
                )
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
                return {"error": f"ffmpeg failed to cut a segment: {detail}"}
            except subprocess.TimeoutExpired:
                return {"error": "Cutting timed out — the file may be too long."}
            segment_paths.append(segment_path)

        list_path = Path(tmp_dir) / "concat_list.txt"
        list_path.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in segment_paths), encoding="utf-8"
        )

        output_path = video_path.with_name(f"{video_path.stem}-edited{video_path.suffix}")
        suffix_index = 2
        while output_path.exists():
            output_path = video_path.with_name(f"{video_path.stem}-edited-{suffix_index}{video_path.suffix}")
            suffix_index += 1

        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
                    "-c", "copy", str(output_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to stitch segments together: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": "Stitching timed out."}

    new_duration = sum(end - start for start, end in keep_segments)
    removed_seconds = duration - new_duration

    return {
        "action": {
            "type": "silence_removal_result",
            "silence_output_path": str(output_path),
            "silence_original_duration": round(duration, 1),
            "silence_new_duration": round(new_duration, 1),
            "silence_removed_seconds": round(removed_seconds, 1),
            "silence_segment_count": len(keep_segments),
        },
        "message": (
            f"I've removed {round(removed_seconds, 1)} seconds of silence and saved the result to "
            f"{output_path.name}."
        ),
    }


```
Note: `-ss` is placed before `-i` (input seeking) with `-t <duration>` (relative duration) rather than `-to <absolute-end>` — this avoids a well-known ffmpeg ambiguity where `-to` combined with `-ss`-before-`-i` has had inconsistent semantics across versions; `-t` (duration) behaves consistently. Because segments are re-encoded (not stream-copied), input seeking here is still frame-accurate — the accuracy trade-off only applies to stream-copy seeking.

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `generate_subtitles` entry closes (find it by searching for `"name": "generate_subtitles"` and its closing `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "remove_silence",
            "description": "Detect and remove silent gaps from a local video/audio file, saving a new edited copy. Requires ffmpeg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "min_silence_seconds": {
                        "type": ["number", "null"],
                        "description": "Minimum silence duration to remove, in seconds. Defaults to 0.5.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"generate_subtitles": _tool_generate_subtitles,`:
```python
    "remove_silence": _tool_remove_silence,
```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 58 passed, no regressions. Confirm the token-budget regression guards in `test_provider.py` still pass — if either fails, trim the new tool's description rather than raising the ceiling.

---

### Task 4: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:84` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:102` (extend rule 12)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `generate_subtitles` bullet (current line 84):
```python
• remove_silence — detect and remove silent gaps from a local video/audio file, saving a new edited copy; requires ffmpeg
```

- [ ] **Step 2: Extend rule 12**

Modify `backend/app/ai/provider.py`, replacing rule 12 (locate by its current content, since line numbers shift after Step 1's insertion):
```python
12. When the user gives a local file path (or has uploaded a file) and asks for subtitles, captions, a transcript, silence removal, or a rough cut, call generate_subtitles or remove_silence accordingly — pass target_language/min_silence_seconds only if specified. If they want this done but haven't given a file path or uploaded a file yet, call request_file_upload first instead of just asking. Confirm what was generated and where it was saved.
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 58 passed, no regressions.

---

### Task 5: Frontend — `SilenceRemovalResultCard`

**Files:**
- Modify: `frontend/components/message-cards.tsx:9-42` (`ClientAction` interface)
- Modify: `frontend/components/message-cards.tsx` (append `SilenceRemovalResultCard` at end of file)
- Modify: `frontend/components/jarvis-interface.tsx:7-21` (import block)
- Modify: `frontend/components/jarvis-interface.tsx` (render branch)

- [ ] **Step 1: Add the new action type and fields to `ClientAction`**

Modify `frontend/components/message-cards.tsx`, replacing the `ClientAction` interface (current lines 9-42) to add `"silence_removal_result"` to the `type` union and five new fields at the end:
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
}
```

- [ ] **Step 2: Add `SilenceRemovalResultCard`**

Modify `frontend/components/message-cards.tsx`, appending to the end of the file, after `FileUploadCard` closes:
```tsx

/* ── Silence Removal Result Card ───────────────────────────────────────── */

export function SilenceRemovalResultCard({ action }: { action: ClientAction }) {
  if (!action.silence_output_path) return null

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <FileText className="h-3 w-3" />
        Silence Removed
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-foreground">
        <span className="text-muted-foreground">Original</span>
        <span>{action.silence_original_duration?.toFixed(1)}s</span>
        <span className="text-muted-foreground">New</span>
        <span>{action.silence_new_duration?.toFixed(1)}s</span>
        <span className="text-muted-foreground">Removed</span>
        <span>{action.silence_removed_seconds?.toFixed(1)}s</span>
        <span className="text-muted-foreground">Segments kept</span>
        <span>{action.silence_segment_count}</span>
      </div>
      <p className="truncate font-mono text-[10px] text-muted-foreground">{action.silence_output_path}</p>
    </div>
  )
}
```
Reuses the already-imported `FileText` icon — no new icon import needed.

- [ ] **Step 3: Import it in `jarvis-interface.tsx`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `message-cards` import block (current lines 7-21) to add `SilenceRemovalResultCard`:
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
  SilenceRemovalResultCard,
  SubtitleResultCard,
  TypewriterText,
```
(remaining lines of the import block unchanged)

- [ ] **Step 4: Render the card**

Modify `frontend/components/jarvis-interface.tsx`, inserting a new render block right after the `subtitle_result` block and before the `file_upload_request` block:
```tsx
                  {/* Silence removal result */}
                  {message.action?.type === "silence_removal_result" && (
                    <SilenceRemovalResultCard action={message.action} />
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
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too — check with a request to `http://127.0.0.1:3000` and restart it if not. If any PowerShell command hangs unexpectedly, fall back to starting the server directly (e.g. `nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 &` from a bash-compatible shell) rather than waiting indefinitely.

- [ ] **Step 2: Remove silence from a real file**

Upload or point to a real video/audio file with clear pauses (e.g. a podcast clip). Ask JARVIS to remove the silence. Confirm a new `-edited` file is produced, is shorter than the original, and the pauses are genuinely gone when played back.

- [ ] **Step 3: Verify the result card**

Confirm the result card shows accurate original/new duration and seconds-removed stats matching what was actually produced.

- [ ] **Step 4: Custom threshold**

Ask again with a custom `min_silence_seconds` (e.g. "only remove silences longer than 2 seconds") and confirm fewer/different cuts are made than the default pass.

- [ ] **Step 5: No silence case**

Try a file with no meaningful silence (or a very short clip). Confirm a clear "nothing to remove" message rather than a needless duplicate file.

- [ ] **Step 6: Non-clobbering output**

Run it twice on the same file. Confirm the second run produces `clip-edited-2.mp4` (or similar) rather than overwriting the first result.

- [ ] **Step 7: Upload-triggered flow**

Ask "remove the silence from my podcast" with no file given. Confirm the upload prompt card appears (per 6b), and that after uploading, `remove_silence` is what gets called next — not `generate_subtitles`.

- [ ] **Step 8: Regression check**

Quickly re-verify subtitle generation (6a) and the upload flow (6b) still work unaffected.

- [ ] **Step 9: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 7: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Silence Removal / Rough Cuts" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 6's manual verification steps above. Mention that it reuses the same upload/path flow as subtitle generation.

---

## Post-plan: what's explicitly not in this increment

- Embedded video preview in the result card.
- Filler-word removal.
- Thumbnail generation.
- Highlight detection / automatic Shorts-Reels generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration.

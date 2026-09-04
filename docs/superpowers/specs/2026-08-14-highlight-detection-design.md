# AI Video Editing — Increment 6e: Highlight Detection / Automatic Shorts

## Context

This is the fourth sub-increment of AI Video Editing (§5), following 6a (subtitle generation), 6b (video upload), and 6c (silence removal). It adds automatic highlight detection — finding the most compelling moments in a video and clipping them out — directly matching AGENT.md's "Highlight detection" and "Automatic Shorts/Reels generation" bullets. It reuses the transcription infrastructure from 6a and the file-input flow from 6b.

- **6a (done)**: Subtitle generation.
- **6b (done)**: Video upload, feeding into any video-editing tool via `request_file_upload`.
- **6c (done)**: Silence removal / rough cuts.
- **6e (this increment)**: Highlight detection — clipping the most compelling moments from a video.
- **Later**: Vertical (9:16) reformatting for Shorts/Reels — confirmed as out of scope here; thumbnail generation; the heavier items (multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration).

## Scope

**In scope:**
1. A new `detect_highlights(file_path, max_highlights)` tool.
2. Transcription with segment timestamps, reusing 6a's Groq transcription approach (audio extraction via `ffmpeg`, then Groq's `verbose_json` transcription).
3. A compact, timestamped transcript representation (pure, testable helper) fed to Groq's chat-completion endpoint to identify up to `max_highlights` (default 5) compelling moments, each with a start time, end time, and a short reason.
4. Defensive parsing/validation of the LLM's JSON response (pure, testable helper) — malformed entries dropped, timestamps clamped to the actual video duration.
5. Per-highlight clip extraction via `ffmpeg` (frame-accurate single-segment cuts, cheap since it's a handful of clips, not the many-segment case that made silence removal slow before its fix).
6. Output: multiple clip files saved next to the source, each independently non-clobbering (`<name>-highlight-1.mp4`, `-highlight-2.mp4`, etc.).
7. A result card listing each clip's time range, reason, and file path.
8. Reuse of the existing `request_file_upload` flow if no file/path has been given yet.

**Out of scope:**
- Vertical (9:16) reformatting/cropping for Shorts/Reels — confirmed deferred; original aspect ratio only for this increment.
- Thumbnail generation.
- Any UI control over highlight count/length beyond the `max_highlights` parameter.
- Caching/reusing a transcript across multiple tool calls on the same file (e.g. if the user already ran `generate_subtitles` on it) — this tool does its own independent transcription call, since there's no cross-tool state-sharing mechanism in this architecture.

## Design

### Tool: `detect_highlights`

`backend/app/ai/tools.py` gains `_tool_detect_highlights(args, user_id, store)`:

1. Validates `file_path` exists, `ffmpeg` is available, and a Groq API key is configured (same checks as `generate_subtitles`).
2. Extracts audio and transcribes with segment timestamps (same approach as `generate_subtitles`).
3. Builds a compact timestamped transcript string from the segments via a new pure helper.
4. Sends that transcript to Groq's chat-completion endpoint with a prompt asking for up to `max_highlights` distinct, genuinely compelling moments as JSON — a self-contained call within the tool (not importing from `app.ai.provider`, which would create a circular import; the same pattern already used for `_translate_segments` in 6a).
5. Parses and validates the JSON response via a new pure helper — drops malformed entries, clamps timestamps to `[0, duration]`, discards entries where `end <= start`.
6. If no valid highlights survive, returns a clear "couldn't identify any highlights" message.
7. For each valid highlight, runs one `ffmpeg -ss <start> -t <duration> -i <input> -c:v libx264 -c:a aac <output>` extraction (frame-accurate re-encode, same pattern as 6c's original per-segment approach — appropriate here since the count is small, unlike silence removal's many-segment case).
8. Each output path is independently non-clobbering (same loop-until-free pattern as 6a/6c).
9. Returns the list of generated clips (path, start, end, reason) for the result card.

### Tool definition

```
name: detect_highlights
description: "Find the most compelling moments in a local video/audio file and clip them out, saved next to the source. Requires ffmpeg."
parameters:
  file_path: string, required — local path to the video/audio file.
  max_highlights: number, optional — maximum number of highlight clips to produce (default 5).
```

### Pure helpers (TDD)

```
_build_timestamped_transcript(segments: list[dict]) -> str
```
Formats segments as `[12.3s] <text>` lines, one per segment, for feeding to the highlight-selection prompt.

```
_parse_highlight_response(raw_json: str, duration: float, max_highlights: int) -> list[dict]
```
Parses the LLM's JSON response (expected shape: a list of `{start, end, reason}` objects), validates each entry (numeric start/end, `0 <= start < end <= duration`, non-empty reason), clamps out-of-range values rather than discarding on minor overshoot, drops entries that are still invalid after clamping, and truncates to `max_highlights`. Returns `[]` on unparseable JSON rather than raising — the caller decides how to respond to an empty result.

### Schema and action-extraction changes

`backend/app/schemas.py`'s `ClientAction` gains `"highlight_detection_result"` to its `type` Literal, plus a field holding the list of generated clips (`highlight_clips: list[dict] | None`, each `{path, start, end, reason}`). `backend/app/services/tool_runner.py`'s `extract_action()` gains a matching branch.

### Frontend

`frontend/components/message-cards.tsx` gains `HighlightDetectionResultCard` — lists each clip's time range, reason, and file path, styled consistently with the other video-tool result cards. `frontend/components/jarvis-interface.tsx` adds a render branch, following the same pattern as every other action type.

### System prompt

A new tool bullet, and rule 12 (already covering `generate_subtitles`, `remove_silence`, `request_file_upload`) is extended to also cover `detect_highlights`.

### Testing

`_build_timestamped_transcript` and `_parse_highlight_response` get unit tests — the genuinely pure logic in this tool, following the established convention from every prior video-editing sub-increment. The actual Groq transcription/chat-completion calls and `ffmpeg` subprocess calls stay manually verified.

### Manual verification plan

1. Upload or point to a real video/audio file with clearly distinct moments (e.g. a podcast with a few notable quotes or jokes). Ask JARVIS to find highlights. Confirm multiple clips are produced, each corresponding to a genuinely distinct, sensible moment — not arbitrary/repeated slices.
2. Confirm the result card lists each clip's time range, reason, and file path accurately.
3. Play back a generated clip and confirm it actually contains the highlighted moment, correctly timed.
4. Ask again with a custom `max_highlights` (e.g. "just find the best 2 highlights") and confirm the count is respected.
5. Try a very short or low-content file where genuine highlights are hard to identify. Confirm a clear "couldn't identify any highlights" message rather than fabricated/nonsensical clips.
6. Run it twice on the same file. Confirm the second run's clips don't overwrite the first (independently non-clobbering per clip).
7. Ask "find highlights in my podcast" with no file given. Confirm the upload prompt card appears, and `detect_highlights` is what runs after uploading.
8. Quickly re-verify subtitle generation (6a) and silence removal (6c) still work unaffected.

## Explicitly deferred to future increments

- Vertical (9:16) reformatting for Shorts/Reels.
- Thumbnail generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration.

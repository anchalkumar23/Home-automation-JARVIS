# AI Video Editing — Increment 6c: Silence Removal / Rough Cuts

## Context

This is the third sub-increment of AI Video Editing (§5), following 6a (subtitle generation) and 6b (video upload). It adds automatic rough cuts — detecting and removing silent gaps from a video — directly matching AGENT.md's "Automatic rough cuts" and "Remove silence" bullets, and reuses the file-input flow (local path or upload) already built in 6a/6b rather than inventing a new one.

- **6a (done)**: Subtitle generation.
- **6b (done)**: Video upload, feeding into any video-editing tool via `request_file_upload`.
- **6c (this increment)**: Silence removal / rough cuts.
- **Later**: Thumbnail generation, highlight detection / auto Shorts-Reels, and the heavier items (multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration).

Prior-art research (done during 6a's brainstorming, reused here): mature open-source silence-removal tools (Remsi, SilenceRemover, jumpcutter, auto-editor) all follow the same two-step pattern — detect silence intervals via ffmpeg's `silencedetect` filter, then cut/reassemble the video around them. `silencedetect` only identifies silence; a separate cutting step (trim/concat or select/aselect filters) does the actual removal, since ffmpeg has no single filter that removes silence from both audio and video together.

## Scope

**In scope:**
1. A new `remove_silence(file_path, min_silence_seconds)` tool.
2. Silence detection via ffmpeg's `silencedetect` filter (default: below -30dB, lasting 0.5s+; `min_silence_seconds` is an optional override).
3. A two-phase cutting approach: re-encode each non-silent "keep" segment (padded ~150ms per edge to avoid clipping words) to a temp file, then stitch them together via ffmpeg's concat demuxer — chosen over a single giant filter-graph invocation, which becomes unwieldy for videos with many silence gaps.
4. Output saved next to the source/uploaded file with a `-edited` suffix, non-clobbering (same pattern as 6a's `.srt` output).
5. A result card showing original duration, new duration, how much was cut, and the output path.
6. Reuse of the existing `request_file_upload` flow — the model calls it first if no file/path has been given yet, exactly as `generate_subtitles` already does.

**Out of scope:**
- An embedded video player/preview in the result card — text stats and a file path only, for now.
- Filler-word removal (only silence, not "um"/"uh" detection — that needs transcription-based analysis, a different mechanism).
- Any UI control over the silence threshold/padding beyond the optional `min_silence_seconds` parameter.
- Thumbnail generation, highlight detection, and the other deferred Section 5 items.

## Design

### Tool: `remove_silence`

`backend/app/ai/tools.py` gains `_tool_remove_silence(args, user_id, store)`:

1. Validates `file_path` exists (same pattern as `generate_subtitles`), and that `ffmpeg` is available.
2. Runs `ffmpeg -i <input> -af silencedetect=noise=-30dB:d=<min_silence_seconds> -f null -` and parses the `silence_start`/`silence_end` lines from stderr into a list of silence intervals.
3. Gets the total duration of the input (via ffmpeg's own `-i` stderr output, parsing the `Duration: HH:MM:SS.ss` line — no separate `ffprobe` call needed).
4. Computes "keep" segments: the complement of the silence intervals (each padded inward by ~150ms) within `[0, duration]`. If no silence is found, returns a clear "no meaningful silence detected" message rather than producing a needless copy.
5. For each keep segment, runs `ffmpeg -y -ss <start> -to <end> -i <input> -c:v libx264 -c:a aac <temp_segment>.mp4` (re-encoded, not stream-copied, for frame-accurate cuts) into a temp directory.
6. Writes an ffmpeg concat-demuxer list file and runs `ffmpeg -y -f concat -safe 0 -i <list> -c copy <output>` to stitch the segments together without re-encoding again.
7. Computes and returns stats: original duration, new duration, seconds removed, segment count.
8. Cleans up the temp directory.

Generous subprocess timeouts (longer than 6a's 600s, since this does multiple re-encode passes) are used, with a clear timeout error message rather than a silent hang — long recordings with many silence gaps can genuinely take a while, the same category of limitation as subtitle generation on long files.

### Tool definition

```
name: remove_silence
description: "Detect and remove silent gaps from a local video/audio file, saving a new edited copy. Requires ffmpeg."
parameters:
  file_path: string, required — local path to the video/audio file.
  min_silence_seconds: number, optional — minimum gap length to remove (default 0.5s).
```

### Schema and action-extraction changes

`backend/app/schemas.py`'s `ClientAction` gains `"silence_removal_result"` to its `type` Literal, plus fields for the output path and the stats (original duration, new duration, seconds removed, segment count). `backend/app/services/tool_runner.py`'s `extract_action()` gains a matching branch.

### Frontend

`frontend/components/message-cards.tsx` gains `SilenceRemovalResultCard` — a stats card (original/new duration, seconds removed, segment count, output path), styled consistently with `SubtitleResultCard`. `frontend/components/jarvis-interface.tsx` adds a render branch, following the same pattern as every other action type.

### System prompt

A new tool bullet, and rule 12 (from 6a/6b, currently covering `generate_subtitles` + `request_file_upload`) is extended to also cover `remove_silence`: when the user asks to remove silence, tighten up a recording, or do a rough cut, and no file/path has been given, call `request_file_upload` first; otherwise call `remove_silence` directly.

### Testing

The silence-interval-to-keep-segments computation (parsing `silencedetect` output, applying padding, computing the complement) is genuinely pure logic distinct from any network/subprocess call, so it gets a dedicated helper function with unit tests — the same TDD treatment `_build_srt` got in 6a. The actual `ffmpeg` subprocess calls stay manually verified, consistent with this project's established convention.

### Manual verification plan

1. Upload or point to a real video/audio file with clear pauses (e.g. a podcast clip). Ask JARVIS to remove the silence. Confirm a new `-edited` file is produced, is shorter than the original, and the pauses are genuinely gone when played back.
2. Confirm the result card shows accurate original/new duration and seconds-removed stats.
3. Ask again with a custom `min_silence_seconds` (e.g. "only remove silences longer than 2 seconds") and confirm fewer/different cuts are made.
4. Try a file with no meaningful silence. Confirm a clear "nothing to remove" message rather than a needless duplicate file.
5. Confirm the non-clobbering behavior (running it twice produces `clip-edited.mp4` then `clip-edited-2.mp4` or similar, not an overwrite).
6. Confirm the conversational upload flow still triggers correctly when no file has been given (per 6b), and that this new tool is what gets called afterward, not `generate_subtitles`.
7. Quickly re-verify subtitle generation (6a) and upload (6b) still work unaffected.

## Explicitly deferred to future increments

- Embedded video preview in the result card.
- Filler-word removal.
- Thumbnail generation.
- Highlight detection / automatic Shorts-Reels generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration.

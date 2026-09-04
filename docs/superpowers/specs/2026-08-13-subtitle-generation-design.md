# AI Video Editing — Increment 6a: Subtitle Generation

## Context

This begins Section 5 of `AGENT.md` (AI Video Editing), started at the user's request while other tracks (Home Automation, blocked on client input; further Content Creation sub-increments) are also viable next steps. Section 5 covers a wide range of real media-processing capabilities (rough cuts, silence removal, multi-cam sync, audio enhancement, color correction, subtitles, translation, AI dubbing, thumbnails, highlight detection, Shorts/Reels generation, multi-format export) — too broad for one increment, and architecturally different from everything built so far, since it's the first section requiring JARVIS to actually process media files rather than just calling APIs or generating text.

- **6a (this increment)**: Subtitle generation, with optional translation.
- **Later**: Silence removal / rough cuts (ffmpeg-based, no external API), thumbnail generation (reuses `generate_image`), highlight detection (needs transcription + content scoring), and the heavier items (multi-cam sync, AI dubbing, DaVinci/Premiere integration) — likely best served by integrating with the client's existing professional tools (he already owns DaVinci Resolve Studio, which has a real Python scripting API) rather than rebuilding equivalent functionality from scratch.

Prior-art research: several mature open-source projects already solve subtitle generation this way — extract audio via `ffmpeg`, transcribe with Whisper (word/segment timestamps), generate `.srt`/`.vtt`, optionally translate. Notable references: `whisper-subtitle-generator`, `whisper_autosrt` (translated subtitles via Google Translate), `subgen`. For silence removal specifically, `auto-editor` is the most mature tool (also exports FCPXML for DaVinci Resolve), though its pip distribution has become inconsistent — worth reconsidering as a wrapped dependency vs. an in-house `ffmpeg silencedetect`-based implementation when that sub-increment comes up, not decided now.

Groq's own transcription API (already used in this project for voice input, via `POST /api/transcribe`) directly supports what's needed here: `response_format=verbose_json` with `timestamp_granularities=["segment"]` returns per-segment timestamps at no extra latency cost, and the endpoint accepts video files (mp4, m4a, etc.) directly, not just audio. The one real constraint: Groq's free tier caps uploads at 25MB, which raw video blows past almost immediately — the standard fix (used by every project referenced above) is extracting just the audio track at a low bitrate first, which is why `ffmpeg` is needed as a new local dependency.

## Scope

**In scope:**
1. A new `generate_subtitles(file_path, target_language)` tool.
2. Audio extraction via `ffmpeg` (subprocess call, not a Python package) — low-bitrate mono output, sized to comfortably fit long-form content (a 90-minute podcast) under Groq's 25MB limit.
3. Transcription via Groq's existing Whisper integration, using `verbose_json` + segment timestamps (new usage of an already-configured API; no new credential/setup needed).
4. Optional translation of subtitle text via the existing chat-completion LLM, preserving segment timing.
5. A pure `_build_srt(segments)` function generating real `.srt` content, unit-tested.
6. Writing the `.srt` file next to the source video, with non-clobbering behavior if one already exists there.
7. A chat card showing the subtitle content with a copy button, alongside the saved file.
8. A clear "ffmpeg not installed" error path if the dependency is missing from the machine, rather than a crash.

**Out of scope:**
- Silence removal / automatic rough cuts, thumbnail generation, highlight detection, multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration, multi-format export — later sub-increments of Section 5.
- File upload via the browser — confirmed as local file path input for this increment, matching this app's local-first, single-user architecture. The backend already runs on the same machine as the video files.
- Burning subtitles into the video (hardcoding them onto the picture) — this increment produces a sidecar `.srt` file for import into editing software, not a rendered output video.

## Design

### Tool: `generate_subtitles`

`backend/app/ai/tools.py` gains `_tool_generate_subtitles(args, user_id, store)`:

1. Validates `file_path` is provided and the file exists on disk; returns a clear error if not.
2. Checks `ffmpeg` is available (e.g. `shutil.which("ffmpeg")`); returns a clear "ffmpeg not installed" message if missing, rather than letting a subprocess call fail opaquely.
3. Runs `ffmpeg` via `subprocess` to extract the audio track into a compressed mono file (low bitrate, sufficient for speech) in a temp location.
4. Sends the extracted audio to Groq's transcription endpoint with `response_format=verbose_json` and `timestamp_granularities=["segment"]`, reusing the same Groq API key already configured for voice transcription (`GROQ_API_KEY`) — no new setting needed.
5. If `target_language` is provided, sends the segment texts to the existing chat-completion LLM for translation, preserving one segment per line so timing stays intact.
6. Builds `.srt` content from the (possibly translated) segments via the pure `_build_srt(segments)` helper.
7. Determines the output path (`<video_name>.srt` next to the source file); if that path already exists, picks a non-clobbering variant (e.g. `<video_name>.srt` → `<video_name>-2.srt`) rather than silently overwriting an existing subtitle file.
8. Writes the file, then returns both the file path and the subtitle content for the chat card.

This is a **direct-execution tool, no confirmation gate** — writing a new sidecar file next to a video is local and reversible (it never modifies or deletes the source video, and the non-clobbering behavior means it never destroys an existing subtitle file either), the same tier of action as `add_task`/`complete_task`, unlike the send-email/calendar-write actions that require a human click because they have real external consequences.

### `_build_srt` helper (pure, testable)

```
_build_srt(segments: list[dict]) -> str
```
Takes a list of `{start: float, end: float, text: str}` segments (Groq's `verbose_json` segment shape, or the translated equivalent) and produces standard `.srt` format: sequential numbering, `HH:MM:SS,mmm --> HH:MM:SS,mmm` timestamp lines, and the segment text, separated by blank lines.

### Tool definition

```
name: generate_subtitles
description: "Generate a .srt subtitle file for a local video/audio file, saved next to the source file. Requires ffmpeg to be installed. Use when the user gives a file path and asks for subtitles, captions, or a transcript."
parameters:
  file_path: string, required — local path to the video/audio file.
  target_language: string, optional — if given, translates the subtitles into this language (e.g. "Spanish"); otherwise subtitles are in the original spoken language.
```

### System prompt

A new tool bullet and a short rule: when the user gives a local file path and asks for subtitles, captions, or a transcript file, call `generate_subtitles` — passing `target_language` if they've asked for a translated version. Confirm what was generated and where it was saved in the spoken reply, per the existing pattern for file/action-producing tools.

### Configuration

No new settings — this reuses the existing `GROQ_API_KEY` (already required for the chat provider and voice transcription) and the existing `groq_whisper_model` setting for the transcription call. `ffmpeg` itself is a system-level dependency (not a Python package), installed once by the user; `backend/requirements.txt` is unaffected.

### Testing

`_build_srt(segments)` gets unit tests: correct sequential numbering, correct timestamp formatting (including sub-second precision and the comma-separator SRT convention), and correct handling of a single segment vs. multiple segments. The `ffmpeg` subprocess call and the Groq transcription call are not unit-tested, consistent with this project's established convention — only pure logic gets tests, live external calls are verified manually.

### Manual verification plan

1. Confirm `ffmpeg` is installed and on PATH (`ffmpeg -version` in a terminal); if not, install it first (one-time setup).
2. Ask JARVIS to generate subtitles for a real local video/audio file by path (e.g. "generate subtitles for `C:\path\to\clip.mp4`"). Confirm a `.srt` file appears next to the source file, with real, accurately-timed captions, and a preview card with a working copy button appears in the chat.
3. Ask for the same file again — confirm it doesn't silently overwrite the first `.srt`, producing a distinctly-named file instead.
4. Ask for subtitles with a target language (e.g. "...and translate them to Spanish"). Confirm the subtitle text is genuinely translated while timing stays intact.
5. Try a nonexistent file path. Confirm a clear "file not found" message, not a crash.
6. Try a file path with an unsupported/non-media extension. Confirm a clear error, not garbled output.
7. (If feasible) Temporarily rename/hide `ffmpeg` from PATH and retry — confirm a clear "ffmpeg not installed" message. Restore PATH afterward.
8. Quickly re-verify voice input (which also uses Groq's transcription endpoint) still works unaffected.

## Explicitly deferred to future increments

- Silence removal / automatic rough cuts.
- Thumbnail generation.
- Highlight detection / automatic Shorts-Reels generation.
- Multi-cam sync, AI dubbing, color correction, DaVinci/Premiere integration, multi-format export.
- Burning subtitles into the video itself.
- Browser-based file upload.

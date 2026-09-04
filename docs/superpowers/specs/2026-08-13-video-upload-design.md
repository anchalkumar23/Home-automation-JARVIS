# AI Video Editing — Increment 6b: Video Upload for Subtitle Generation

## Context

Increment 6a (subtitle generation) required the user to type a local file path in chat. This increment adds a conversational upload flow: the user expresses intent ("add subtitles to my video"), JARVIS recognizes it has no file yet and prompts for an upload, the user picks a file, and once it's uploaded, JARVIS automatically continues and generates the subtitles — without the user typing a path.

This is built as a **general-purpose** upload mechanism, not subtitle-specific, since later sub-increments of Section 5 (AI Video Editing) — silence removal, thumbnail generation, highlight detection — will need the same "get a media file from the user" capability. Wiring it into `generate_subtitles` now, in a way that's trivially reusable later, avoids redoing this work per sub-increment.

## Scope

**In scope:**
1. A new, generic `POST /api/uploads` endpoint (multipart, reusing the `UploadFile` pattern already established in `/api/transcribe`) that streams an uploaded file to a managed `backend/data/uploads/` folder and returns its saved path.
2. A new `request_file_upload(purpose)` tool — called when the model needs a file the user hasn't provided a path for or uploaded yet. Returns a `file_upload_request` action.
3. A new frontend `FileUploadCard` component: a dropzone/button rendered from the `file_upload_request` action, with an uploading state showing byte-progress (via `XMLHttpRequest` upload progress events — a large video upload isn't instant, and silent waiting isn't good UX).
4. Closing the loop: once upload completes, the frontend automatically sends a follow-up chat message on the user's behalf containing the uploaded file's path, so the existing tool-calling loop picks it up and the model calls `generate_subtitles` (or whatever it was trying to do) with that path — no manual typing needed.
5. `generate_subtitles`'s system prompt rule updated: if the user asks for subtitles without a path or upload yet, call `request_file_upload` first.

**Out of scope:**
- Automatic cleanup of uploaded files in `backend/data/uploads/` — they accumulate; manual cleanup for now, single local user.
- In-browser audio pre-extraction to shrink upload size before sending — the full video file is uploaded, same as any standard file picker.
- Wiring `request_file_upload` into any other video-editing tool — this increment only connects it to `generate_subtitles`; future sub-increments reuse the same mechanism as they're built.
- A persistent always-visible attach button — confirmed as conversational-only triggering for this increment.

## Design

### Upload endpoint

`backend/app/routers/uploads.py` (new file) gains `POST /api/uploads`, accepting a single `UploadFile` (same FastAPI pattern as `/api/transcribe`, which already streams large files to a spooled temp file rather than loading them fully into memory). The file is saved to `backend/data/uploads/<uuid>-<original_filename>` (a UUID prefix avoids collisions between uploads with the same original name) and the endpoint returns `{"file_path": "...", "file_name": "..."}`.

### Tool: `request_file_upload`

`backend/app/ai/tools.py` gains `_tool_request_file_upload(args, user_id, store)`. Like `create_business_report`/`create_content`, this has no external side effect — it just packages a prompt for the frontend:
```python
{
    "action": {
        "type": "file_upload_request",
        "upload_purpose": purpose,
    },
    "message": f"Please upload the file for {purpose}.",
}
```

### Tool definition

```
name: request_file_upload
description: "Prompt the user to upload a video/audio file when they want something done with one but haven't given a file path or uploaded a file yet."
parameters:
  purpose: string, required — a short description of what the file will be used for, e.g. "generating subtitles".
```

### Schema and action-extraction changes

`backend/app/schemas.py`'s `ClientAction` gains `"file_upload_request"` to its `type` Literal, plus `upload_purpose: str | None`. `backend/app/services/tool_runner.py`'s `extract_action()` gains a matching branch.

### Frontend: `FileUploadCard`

`frontend/components/message-cards.tsx` gains `FileUploadCard`, rendered from a `file_upload_request` action — shows the `upload_purpose` text, a file picker button (and drag-and-drop target), and during upload, a progress indicator driven by `XMLHttpRequest`'s `upload.onprogress` (chosen over plain `fetch` specifically because `fetch` doesn't expose upload progress natively, and silently waiting through a multi-hundred-MB upload is bad UX). On success, it calls a callback (passed down from `jarvis-interface.tsx`, following the same prop-callback pattern already used by `EmailDraftCard`'s `onSend` and `CalendarEventDraftCard`'s `onSave`) with the uploaded file's path and name.

### Closing the loop back into the chat

`jarvis-interface.tsx`'s upload-success callback constructs a synthetic user message (e.g. `"Uploaded video: podcast.mp4"` with the real path included so the model can reference it, following the same shape as any normal typed message) and sends it through the existing `handleSend` flow — the model then sees the file path in a normal turn and calls `generate_subtitles` on it automatically, per the existing (updated) system prompt rule. No new backend orchestration is needed for this part; it's purely a frontend UX convenience that reuses the existing chat pipeline.

### System prompt

Rule 12 (from 6a: "when the user gives a local file path and asks for subtitles... call generate_subtitles") is extended: if the user asks for subtitles/captions but hasn't given a file path or uploaded a file yet, call `request_file_upload` first instead of asking a plain clarifying question — consistent with how `compose_email` is called with an empty `to` field rather than skipped when the recipient is unknown.

### Testing

No new pure logic distinct from the existing `create_business_report`/`create_content` pattern (validate and package a prompt into an action) — verified manually. The upload endpoint itself is a straightforward file-write, consistent with this project's convention of not unit-testing real I/O/network paths.

### Manual verification plan

1. Ask "I want to add subtitles to my video" with no file path given. Confirm JARVIS responds with an upload prompt card, not a plain text question and not a failed tool call.
2. Click/drag a real video file into the upload card. Confirm a progress indicator shows during upload (test with a reasonably large file, a few hundred MB, to actually see progress rather than an instant completion).
3. Confirm that once the upload finishes, JARVIS automatically proceeds to generate subtitles for the uploaded file without any further typing — a `.srt` appears next to the uploaded copy in `backend/data/uploads/`, and the subtitle preview card appears in chat.
4. Confirm typing a local file path directly (the 6a flow) still works unaffected — both input modes coexist.
5. Try uploading an unsupported/non-media file. Confirm a clear error surfaces (either at the ffmpeg-extraction stage, consistent with 6a's existing error handling, or earlier if feasible) rather than a silent hang.
6. Quickly re-verify voice input (a different upload-adjacent feature, `/api/transcribe`) still works unaffected.

## Explicitly deferred to future increments

- Automatic cleanup of `backend/data/uploads/`.
- In-browser audio pre-extraction before upload.
- Wiring `request_file_upload` into other video-editing tools (as those get built).
- Always-visible attach button.

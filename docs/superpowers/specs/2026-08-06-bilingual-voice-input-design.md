# Core AI Assistant Foundation — Increment 1b: Bilingual Voice Input

## Context

Increment 1a (persistent memory, bilingual EN/ES text replies, bilingual-aware TTS voice selection) is built, tested, and working — see `docs/superpowers/specs/2026-08-04-core-memory-bilingual-design.md`. During that testing round, real bugs were also found and fixed post-hoc: the Groq model was swapped from a deprecated `llama-3.1-8b-instant` to `openai/gpt-oss-120b`, tool schemas were loosened to accept `null` for optional parameters, a server-side safety net strips any leaked tool-call syntax from replies, and the system prompt now forbids fabricating false claims about conversation history. All of that is live in `backend/app/ai/provider.py` and `backend/app/ai/tools.py`.

This increment is the piece explicitly deferred from 1a: the microphone still uses the browser's `SpeechRecognition` API hardcoded to `en-US`, so speaking Spanish to JARVIS does not transcribe correctly — only typed Spanish works today. This increment fixes that by routing spoken audio through Groq's Whisper transcription endpoint, which auto-detects language per request.

## Scope

**In scope:**
1. A new backend endpoint that accepts a recorded audio file and forwards it to Groq's Whisper transcription endpoint, keeping the Groq API key server-side.
2. Replacing the frontend's primary voice-input mechanism (mic button, `Ctrl+J`/`Alt+J` shortcuts) from browser `SpeechRecognition` to `MediaRecorder`-based recording + upload.
3. Toggle-based recording UX: press to start, press again to stop and send (not push-to-talk, not auto-stop-on-silence).
4. Clear, inline error handling when transcription fails (network error, API error, unintelligible audio) — no silent failure, no dual-fallback voice system.

**Out of scope:**
- The wake-word listener ("say Jarvis to activate") stays on the browser's `SpeechRecognition` — it only needs to catch one English trigger word continuously in the background, which is cheap and already works; moving it to Whisper would mean constantly uploading background audio for no accuracy benefit on a single word.
- Whisper's own language-tag output is not used — the transcribed text flows into the existing `/api/chat`, whose system prompt (from 1a) already detects language from text and replies accordingly. No duplicated language-detection logic.
- No new frontend testing framework — this project has no existing frontend test infrastructure, and browser microphone/audio APIs need a real browser to exercise meaningfully. Verified manually, consistent with 1a's testing approach.

## Design

### Backend: `POST /api/transcribe`

New file `backend/app/routers/transcribe.py` (a new, focused router file, following the existing one-router-per-concern pattern rather than growing `chat.py`). Registered in `backend/app/main.py` alongside the existing chat router.

- Accepts a multipart file upload (FastAPI `UploadFile`) containing the recorded audio.
- Forwards it to `https://api.groq.com/openai/v1/audio/transcriptions` using `settings.groq_api_key` and a new `settings.groq_whisper_model` (env var `GROQ_WHISPER_MODEL`, default `whisper-large-v3-turbo` — fast and inexpensive, chosen during 1a's research).
- The multipart request to Groq is built with stdlib `urllib` (no `requests`/`httpx`), matching the rest of the backend's zero-extra-HTTP-library convention (`post_json` in `provider.py` already does raw `urllib` requests the same way).
- Returns `{"text": "<transcribed text>"}`.
- On a Groq error or network failure, returns an HTTP error response with a clear `detail` message the frontend can surface directly.

### Frontend: `lib/use-speech.ts`

The hook's public interface (`startListening`, `stopListening`, `listening`) stays unchanged so `components/jarvis-interface.tsx`'s three call sites (mic button `toggleMic`, the `Ctrl+J`/`Alt+J` keydown handler, and the wake-word trigger callback) don't need structural changes — only the internals of `startListening`/`stopListening` swap from browser `SpeechRecognition` to `MediaRecorder`.

- `startListening(onResult)`: requests microphone access via `navigator.mediaDevices.getUserMedia({ audio: true })`, creates a `MediaRecorder` (preferring `audio/webm` when supported, falling back to the browser default), and collects chunks via `ondataavailable`.
- `stopListening()`: stops the recorder, which triggers assembly of the recorded `Blob`, uploads it to `/api/transcribe` as `multipart/form-data`, and on success calls the same `onResult(text)` callback the old implementation used — so call sites in `jarvis-interface.tsx` don't need to change how they consume the result.
- On transcription failure (permission denied, network error, backend error response), the hook calls an `onError(message)` callback instead. `jarvis-interface.tsx` wires this to push a normal assistant-role message into the existing comms log (e.g. "Couldn't transcribe that — try again or type your message"), reusing the existing message-rendering UI rather than adding a new error component.
- The wake-word listener (`startWakeWordDetection`/`stopWakeWordDetection`) is untouched — still browser `SpeechRecognition`, English-only, Chromium-only, listening only for the word "Jarvis," then handing off to the (now Whisper-based) `startListening`.
- The `supported` flag's meaning shifts slightly: voice *input* (mic button) now depends on `MediaRecorder`/`getUserMedia` support, which is broadly available across modern browsers (Chrome, Firefox, Safari) — unlike the old Chromium-only `SpeechRecognition`. The wake-word button's availability still depends specifically on `SpeechRecognition` support. The hook will expose these as two distinct capability signals so the UI can enable the mic button more broadly while still gating the "Wake" button on Chromium-only support.
- No new visual/orb state is added — the brief network round-trip between "finished recording" and "got transcribed text back" reuses the existing `"thinking"` orb state, keeping the HUD's visual design untouched.

### Error handling

- Microphone permission denied or no microphone available: `getUserMedia` rejects; the hook surfaces this through the same `onError` path as a transcription failure, with a message distinguishing "no microphone access" from "couldn't transcribe."
- Empty or silent recordings: Groq's Whisper endpoint will return an empty or near-empty transcript rather than erroring; if the returned text is empty/whitespace-only after trimming, treat it as a failure and surface the same "couldn't transcribe" message rather than silently sending an empty message to `/api/chat`.
- Backend/network failure calling Groq: the `/api/transcribe` endpoint returns a non-2xx response with a `detail` message; the frontend's upload call checks `response.ok` and passes `detail` (or a generic fallback) to `onError`.

### Testing plan (manual, human-in-the-loop per the project's established workflow)

1. Click the mic button, speak a command in English, click again to stop → correct transcription appears and is sent, JARVIS responds normally.
2. Same flow speaking in Spanish → correctly transcribed in Spanish (this is the core fix — the old recognizer could not do this).
3. Enable "Wake," say "Jarvis," then speak a command in either language → wake-word detection still triggers, followed by correct Whisper-based transcription.
4. Deny microphone permission when prompted → a clear inline error appears, not a silent failure; typing still works.
5. Try the mic button in a non-Chromium browser (e.g. Firefox) if available → voice input should now work there too (the "Wake" button is expected to be unavailable/disabled, since it still depends on Chromium's `SpeechRecognition`).

## Explicitly deferred to future increments

- Everything else in `AGENT.md` beyond Section 1 (studio automation, 3D printing, content creation, video editing, research assistant, multi-model routing, computer vision, holographic avatar, mobile companion, remote control, business intelligence, security, scalability) — each scoped as its own increment after this one is tested and approved, per the project's established one-increment-at-a-time workflow.

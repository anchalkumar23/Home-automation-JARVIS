# Core AI Assistant Foundation — Increment 1a: Persistent Memory & Bilingual Text

## Context

This is the first real increment of the "Ultimate JARVIS" build described in `AGENT.md`. That spec covers 20 sections spanning years of work (studio automation, 3D printing, holographic avatars, computer vision, mobile apps, etc.). Per the client's explicit instruction, JARVIS is being built one small, human-testable increment at a time rather than all at once.

A working local demo already exists at `C:\Anchal\Fiverr\JARVIS Demo` (FastAPI backend + Next.js/React frontend) covering a slice of Section 1 (Core AI Assistant): chat with tool calling (time, memory, tasks, URL opening, web search, image generation, news, music, email drafting), browser-based voice (Web Speech API STT/TTS), and SQLite-backed memory. Groq is already configured and working as the primary provider (`.env` has a live key, `JARVIS_PROVIDER=groq`).

This increment hardens the foundation everything else depends on: making memory actually persistent/proactive (not just recall-on-request) and adding English/Spanish bilingual replies. A second increment (1b) will follow separately to replace the browser's single-language speech recognition with Groq's Whisper transcription for true bilingual voice input — deferred because it's a separate, larger frontend audio-pipeline change and this project builds one testable piece at a time.

## Prior art considered

Researched mem0, Letta/MemGPT, Zep, and memobase for long-term memory patterns. All either require a vector database or are designed for multi-tenant scale — overkill for a single-user personal assistant, and in conflict with this project's house rules (`CLAUDE.md`: "never overengineer," "minimize dependencies," "reuse existing code before creating new files"). The adopted pattern borrows two ideas without the infrastructure:
- **Letta's "core memory"**: keep a small set of facts always in the system prompt, not retrieved on demand.
- **memobase's structured profile**: a simple key/value fact store rather than embeddings/chunks.

The existing `memories` SQLite table and `save_memory`/`get_memory` tools already implement exactly this shape — the gap is only that the model currently has to *choose* to call `get_memory`, so it doesn't reliably greet the user by name or recall facts unless asked. No new table or dependency is needed.

For bilingual voice (relevant to 1b, noted here for continuity): browser `SpeechRecognition` only supports one language at a time with no auto-detect. Groq's Whisper transcription endpoint (`/openai/v1/audio/transcriptions`) auto-detects language per request and is already accessible via the existing Groq key — the planned approach for 1b.

## Scope of this increment (1a)

**In scope:**
1. Proactive memory recall — known facts about the user are injected into every chat request's system prompt, not just fetched when the model calls `get_memory`.
2. Proactive memory saving — the model is instructed to call `save_memory` whenever the user reveals a new stable fact, without needing to be explicitly told "remember that...".
3. Bilingual text — the model detects the language (English/Spanish) of each incoming message and replies in kind, switching per message as needed.
4. Bilingual-aware text-to-speech voice selection — the backend tags each reply with a detected `language` field; the frontend prefers an installed Spanish voice when speaking a Spanish reply.

**Out of scope (deferred to increment 1b or later):**
- Replacing browser speech recognition with Groq Whisper (true bilingual voice *input*).
- Multi-user identification (this JARVIS instance serves a single user; `user_id` stays hardcoded as `"default"`).
- Any new database table, vector store, or embedding-based memory search.
- Authentication/security (Section 18) — not needed yet for a single local user.

## Design

### Project migration (precondition, no feature logic)

Before feature work: copy `JARVIS Demo/frontend` and `JARVIS Demo/backend` into `Ultimate JARVIS/`, `git init` the `Ultimate JARVIS` folder, and add a `.gitignore` covering `node_modules`, `.venv`, `__pycache__`, `.next`, `*.db`, and `.env`. Only `.env.example` (blank placeholders) is committed — `backend/.env` currently holds live OpenAI and Groq API keys and must never enter git history. `JARVIS Demo` is left untouched as a backup. `AGENT.md`, `CLAUDE.md`, `.agents/`, and `skills-lock.json` already live at the `Ultimate JARVIS` root and carry over as-is.

### Memory: proactive injection

`build_messages()` in `backend/app/ai/provider.py` currently takes `(history, message)` and returns the message list with a static system prompt. It will be extended to also take the `MemoryStore` and `user_id`, fetch `store.list_memories(user_id)`, and — if any exist — append a compact block to the system prompt, e.g.:

```
What you already know about this user (use naturally; don't just recite this list):
- name: Anchal
- favorite_color: red
```

`run_remote_agent` already has both `runner.memory_store` and `request.user_id` available, so this is a threading change, not new plumbing.

The system prompt's behavior rules gain two additions:
1. Use known facts naturally (e.g., greet by name if known) rather than listing them back.
2. Proactively call `save_memory` when the user reveals a new stable fact or preference, even if not explicitly asked to remember it.

No schema change — the existing `memories` table (`user_id`, `key`, `value`) already fits.

### Bilingual text

The system prompt gains an instruction: detect whether each incoming message is English or Spanish, and reply in that language; if the user switches languages mid-conversation, follow them; default to English if ambiguous.

To keep spoken output consistent with a Spanish reply, `provider.py` adds a small heuristic `detect_language(text) -> "en" | "es"` (checks for Spanish-specific characters like `ñ`, `¿`, `¡` and common Spanish stopwords) run on the final answer text. `ChatResponse` (in `schemas.py`) gains a `language: str` field populated with the result.

On the frontend, `useSpeech`'s `speak()` gains an optional language parameter. When `"es"`, voice selection prefers a voice whose `lang` starts with `es`; otherwise it keeps the current English-preferring `scoreVoice` logic. If no Spanish voice is installed in the browser, it silently falls back to the default voice — no error state, since `speak()` already has this no-match fallback pattern today.

### Error handling

- If `list_memories` returns nothing (new install, no facts yet), the system prompt simply omits the "known facts" block — no special-casing needed.
- `detect_language` is a best-effort heuristic, not a hard dependency; if it misclassifies, the only effect is the wrong TTS voice being picked for a single reply — not a functional failure. No retry logic needed.
- Existing error handling (provider failure → local fallback) is untouched by this increment.

### Testing plan (manual, human-in-the-loop per project instruction)

1. Tell JARVIS your name in one session (e.g. "Remember that my name is Anchal"). Reload the page (new session) and say hello — confirm it greets you by name without being asked.
2. Mention a preference without saying "remember" (e.g. "I really love hiking on weekends"). Later ask "what do you know about me?" — confirm the preference was saved proactively.
3. Type a full message in Spanish — confirm the reply text is in Spanish and, if a Spanish browser voice is installed, that it's spoken in that voice.
4. Send an English message immediately after — confirm the reply switches back to English.

## Explicitly deferred to future increments

- **1b**: Groq Whisper-based speech-to-text to replace browser `SpeechRecognition`, enabling accurate spoken Spanish input.
- Everything else in `AGENT.md` (Sections 2–20) — studio automation, 3D printing, content creation, video editing, research assistant, multi-model routing, computer vision, holographic avatar, mobile companion, remote control, business intelligence, security, scalability — each to be scoped as its own increment after this one is tested and approved.

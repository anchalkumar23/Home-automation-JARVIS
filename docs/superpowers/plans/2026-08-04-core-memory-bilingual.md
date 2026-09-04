# Core AI Assistant Foundation — Increment 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the working JARVIS demo into `Ultimate JARVIS`, then make memory proactive (JARVIS recalls facts and greets the user by name without being asked) and add English/Spanish bilingual text replies with matching TTS voice selection.

**Architecture:** The backend (`FastAPI`) already stores facts in a SQLite `memories` table and has a `save_memory`/`get_memory` tool pair. This plan changes *when* memory is used — injecting known facts into the system prompt on every request instead of only when the model calls `get_memory` — and adds a small language-detection heuristic so replies and the frontend's `speechSynthesis` voice choice both follow whichever language (English/Spanish) the user is using. No new database tables, no new external dependencies beyond `pytest` for backend unit tests.

**Tech Stack:** FastAPI, Python stdlib + `pytest`, Next.js/React, browser `SpeechSynthesis`.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a verification step (test run or manual check) instead of a commit step.

---

### Task 1: Migrate demo code into Ultimate JARVIS

**Files:**
- Create: `C:\Anchal\Fiverr\Ultimate JARVIS\.gitignore`
- Create: `C:\Anchal\Fiverr\Ultimate JARVIS\frontend\` (copied from `JARVIS Demo`)
- Create: `C:\Anchal\Fiverr\Ultimate JARVIS\backend\` (copied from `JARVIS Demo`)

- [ ] **Step 1: Copy the frontend, excluding build artifacts**

Run (PowerShell):
```powershell
robocopy "C:\Anchal\Fiverr\JARVIS Demo\frontend" "C:\Anchal\Fiverr\Ultimate JARVIS\frontend" /E /XD node_modules .next
```
Expected: exit code 1 (robocopy uses 0–7 for success; 1 means "files copied", not an error). A long file list is printed.

- [ ] **Step 2: Copy the backend, excluding venv/cache/data**

Run (PowerShell):
```powershell
robocopy "C:\Anchal\Fiverr\JARVIS Demo\backend" "C:\Anchal\Fiverr\Ultimate JARVIS\backend" /E /XD .venv __pycache__ data
```
Expected: exit code 0 or 1, same reasoning as above.

- [ ] **Step 3: Verify the copy**

Run (PowerShell):
```powershell
Test-Path "C:\Anchal\Fiverr\Ultimate JARVIS\backend\app\main.py"
Test-Path "C:\Anchal\Fiverr\Ultimate JARVIS\frontend\components\jarvis-interface.tsx"
```
Expected: both print `True`.

- [ ] **Step 4: Create the root `.gitignore`**

Write `C:\Anchal\Fiverr\Ultimate JARVIS\.gitignore`:
```
node_modules/
.venv/
__pycache__/
*.pyc
.next/
*.db
.env
```

- [ ] **Step 5: Set up the backend virtual environment in the new location**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Expected: packages install without errors (`fastapi`, `uvicorn`, `pydantic`, `tzdata`).

- [ ] **Step 6: Install frontend dependencies in the new location**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npm install
```
Expected: completes without errors, creates `node_modules`.

- [ ] **Step 7: Verify the migrated app boots**

Run (PowerShell), in two separate terminals:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Expected: backend logs `Uvicorn running on http://127.0.0.1:8000`; `http://127.0.0.1:8000/health` returns `{"status":"online","service":"jarvis-backend"}`; `http://localhost:3000` loads the JARVIS HUD interface. Stop both servers (Ctrl+C) before continuing to Task 2.

---

### Task 2: Add a language-detection heuristic (TDD)

**Files:**
- Modify: `backend/app/ai/provider.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_provider.py`

- [ ] **Step 1: Add `pytest` to requirements and install it**

Modify `backend/requirements.txt` to add one line:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
tzdata>=2024.1
pytest==8.3.4
```

Run (PowerShell, with the venv from Task 1 still active):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
pip install -r requirements.txt
```
Expected: `pytest` installs successfully.

- [ ] **Step 2: Create the tests package**

Create `backend/tests/__init__.py` (empty file).

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_provider.py`:
```python
from app.ai.provider import detect_language


def test_detect_language_spanish_via_accents_and_punctuation():
    assert detect_language("Hola, ¿cómo estás hoy?") == "es"


def test_detect_language_spanish_via_stopwords():
    assert detect_language("Muchas gracias por tu ayuda con esto") == "es"


def test_detect_language_english_default():
    assert detect_language("Remember that my favorite color is red") == "en"
```

- [ ] **Step 4: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: `ImportError: cannot import name 'detect_language'` (function doesn't exist yet).

- [ ] **Step 5: Implement `detect_language`**

Modify `backend/app/ai/provider.py`. Add near the top of the file, after the existing module-level imports (after line 12, before `SYSTEM_PROMPT`):
```python
_SPANISH_CHARS = set("ñáéíóúü¿¡")
_SPANISH_WORDS = {
    "el", "la", "los", "las", "de", "que", "es", "en", "un", "una",
    "por", "para", "con", "como", "pero", "más", "muy", "está", "hola",
    "gracias", "buenos", "usted", "tú", "yo", "qué", "cómo",
}


def detect_language(text: str) -> str:
    """Best-effort English/Spanish detection for reply language and TTS voice selection."""
    lowered = text.lower()
    if any(char in _SPANISH_CHARS for char in lowered):
        return "es"
    words = re.findall(r"[a-záéíóúñü]+", lowered)
    spanish_hits = sum(1 for word in words if word in _SPANISH_WORDS)
    if spanish_hits >= 2:
        return "es"
    return "en"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: 3 passed.

---

### Task 3: Add a known-facts formatting helper (TDD)

**Files:**
- Modify: `backend/app/ai/provider.py`
- Modify: `backend/tests/test_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_provider.py`:
```python
from app.ai.provider import build_known_facts_block


def test_build_known_facts_block_empty():
    assert build_known_facts_block([]) == ""


def test_build_known_facts_block_lists_facts():
    memories = [
        {"key": "name", "value": "Anchal"},
        {"key": "favorite_color", "value": "red"},
    ]
    block = build_known_facts_block(memories)
    assert "- name: Anchal" in block
    assert "- favorite_color: red" in block
    assert "use naturally" in block
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: `ImportError: cannot import name 'build_known_facts_block'`.

- [ ] **Step 3: Implement `build_known_facts_block`**

Modify `backend/app/ai/provider.py`. Add directly below the `detect_language` function added in Task 2:
```python
def build_known_facts_block(memories: list[dict[str, Any]]) -> str:
    """Format saved user memories as a system-prompt addendum for proactive recall."""
    if not memories:
        return ""
    facts = "\n".join(f"- {item['key']}: {item['value']}" for item in memories)
    return (
        "\n\nWhat you already know about this user "
        "(use naturally; don't just recite this list):\n" + facts
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: 5 passed.

---

### Task 4: Thread memory into `build_messages` for proactive recall (TDD)

**Files:**
- Modify: `backend/app/ai/provider.py:1-13` (imports), `:60-67` (`build_messages`), `:138` (call site in `run_remote_agent`)
- Modify: `backend/tests/test_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_provider.py`:
```python
from app.ai.provider import build_messages, SYSTEM_PROMPT
from app.services.memory import MemoryStore


def test_build_messages_includes_known_facts(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_memory("default", "name", "Anchal")

    messages = build_messages([], "hello", store, "default")

    assert "name: Anchal" in messages[0]["content"]


def test_build_messages_without_memories_omits_block(tmp_path):
    store = MemoryStore(tmp_path / "test.db")

    messages = build_messages([], "hello", store, "default")

    assert messages[0]["content"] == SYSTEM_PROMPT
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: `TypeError: build_messages() takes 2 positional arguments but 4 were given`.

- [ ] **Step 3: Add the `MemoryStore` import**

Modify `backend/app/ai/provider.py`. Change the import block at the top of the file (lines 10-13):
```python
from app.ai.tools import TOOL_DEFINITIONS
from app.config import Settings
from app.schemas import ChatMessage, ChatRequest, ChatResponse, ToolResult
from app.services.memory import MemoryStore
from app.services.tool_runner import ToolRunner
```

- [ ] **Step 4: Update `build_messages` to accept and use memory**

Modify `backend/app/ai/provider.py`, replacing the existing `build_messages` function (current lines 60-67):
```python
def build_messages(
    history: list[ChatMessage],
    message: str,
    memory_store: MemoryStore,
    user_id: str,
) -> list[dict[str, Any]]:
    known_facts = build_known_facts_block(memory_store.list_memories(user_id))
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT + known_facts}]
    for item in history[-12:]:
        if item.role == "system":
            continue
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": message})
    return messages
```

- [ ] **Step 5: Update the call site in `run_remote_agent`**

Modify `backend/app/ai/provider.py`. In `run_remote_agent`, change:
```python
    messages = build_messages(request.history, request.message)
```
to:
```python
    messages = build_messages(request.history, request.message, runner.memory_store, request.user_id)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_provider.py -v
```
Expected: 7 passed.

---

### Task 5: Strengthen the system prompt for proactive memory and bilingual replies

**Files:**
- Modify: `backend/app/ai/provider.py:15-38` (`SYSTEM_PROMPT`)

This task edits a prompt string, not testable logic — no automated test applies. Verification happens in Task 9's manual checklist.

- [ ] **Step 1: Update `SYSTEM_PROMPT`**

Modify `backend/app/ai/provider.py`, replacing the existing `SYSTEM_PROMPT` constant (current lines 15-38) with:
```python
SYSTEM_PROMPT = """You are JARVIS, a precise, witty, and capable personal AI assistant inside a futuristic HUD interface.
You have access to the following tools — use them proactively whenever appropriate:

• get_time — Get current time/date for any timezone.
• get_system_status — Return system health and capabilities.
• save_memory / get_memory — Remember and recall user facts and preferences.
• add_task / list_tasks — Manage the user's task list.
• open_url — Open any website (Instagram, Twitter, GitHub, etc.) in the user's browser.
• web_search — Search the web for factual answers.
• generate_image — Create an AI-generated image from a text description.
• get_news — Fetch the latest news headlines.
• play_music — Play a song or music on YouTube.
• compose_email — Draft an email for the user to review and send.

Long-term memory:
1. If the system prompt includes a "What you already know about this user" section, use those facts naturally in conversation (e.g. greet the user by name if known, tailor answers to known preferences) — do not just recite the list back to them.
2. Whenever the user reveals a new stable fact or preference about themselves (name, preferences, work, family, recurring context), proactively call save_memory to store it — do not wait to be explicitly asked to remember it.

Language:
3. Detect whether each message from the user is written in English or Spanish, and reply in that same language. If the user switches languages mid-conversation, switch with them. Default to English if the language is ambiguous.

Behavior rules:
4. Use tools whenever the user's request matches a tool's purpose. Do NOT claim a tool action happened unless the tool result confirms it.
5. You can call MULTIPLE tools in a single response when the user makes compound requests (e.g. "open Instagram and play some music").
6. Keep answers concise, useful, and natural — as if speaking aloud.
7. If a tool returns an action (like open_url), briefly confirm it.
8. For image generation, describe what you're creating before calling the tool.
9. For email composition, ask for clarification on missing details (recipient, subject) before calling compose_email.
10. When the user says "play [song/artist]", always use the play_music tool.
11. Be warm and professional like the JARVIS from Iron Man. Use occasional wit but stay helpful.
"""
```

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: all 7 tests still pass (the tests reference `SYSTEM_PROMPT` by identity, not content, so this edit doesn't break them).

---

### Task 6: Add a `language` field to `ChatResponse` and populate it

**Files:**
- Modify: `backend/app/schemas.py:37-45` (`ChatResponse`)
- Modify: `backend/app/ai/provider.py` (`run_remote_agent`)

- [ ] **Step 1: Add the field to the schema**

Modify `backend/app/schemas.py`, replacing the `ChatResponse` class (current lines 37-45):
```python
class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str | None = None
    tools_used: list[ToolResult] = Field(default_factory=list)
    action: ClientAction | None = None
    error: str | None = None
    image_url: str | None = None
    language: str = "en"
```

- [ ] **Step 2: Populate it on the successful-answer return path**

Modify `backend/app/ai/provider.py`. In `run_remote_agent`, find the block that returns the final answer when there are no more tool calls:
```python
        if not tool_calls:
            answer = assistant_message.get("content") or "I completed the request."
            return ChatResponse(
                answer=answer,
                provider=provider,
                model=model,
                tools_used=tool_results,
                action=runner.extract_action(tool_results),
                image_url=runner.extract_image_url(tool_results),
            )
```
Replace it with:
```python
        if not tool_calls:
            answer = assistant_message.get("content") or "I completed the request."
            return ChatResponse(
                answer=answer,
                provider=provider,
                model=model,
                tools_used=tool_results,
                action=runner.extract_action(tool_results),
                image_url=runner.extract_image_url(tool_results),
                language=detect_language(answer),
            )
```

The `tool_loop_limit_reached` fallback and the local-mode paths keep the schema default (`"en"`) — both return fixed English messages today, so no change needed there.

- [ ] **Step 3: Verify the backend still starts and the schema is valid**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
python -c "from app.schemas import ChatResponse; print(ChatResponse(answer='hi', provider='groq').language)"
```
Expected: all 7 tests pass; the script prints `en`.

---

### Task 7: Frontend — teach `speak()` to prefer a Spanish voice

**Files:**
- Modify: `frontend/lib/use-speech.ts:120-140` (`speak`)

No automated frontend test is added here — this project has no existing frontend test framework (no Jest/Vitest, no test files under `frontend/`), and `speak()` is a thin wrapper around the browser's `SpeechSynthesis` API, which requires a real browser to exercise meaningfully. Verification is manual, via Task 9's checklist, consistent with the design doc's testing plan.

- [ ] **Step 1: Update `speak()` to accept an optional language hint**

Modify `frontend/lib/use-speech.ts`, replacing the existing `speak` callback (current lines 121-140):
```typescript
  const speak = useCallback(
    (text: string, onEnd?: () => void, language?: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window) || muted) {
        onEnd?.()
        return
      }
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.02
      utterance.pitch = 0.85

      let selected = rawVoicesRef.current.find((v) => v.voiceURI === selectedVoiceURI)
      if (language === "es") {
        const spanishVoice = rawVoicesRef.current.find((v) => v.lang.toLowerCase().startsWith("es"))
        if (spanishVoice) selected = spanishVoice
      }
      if (selected) {
        utterance.voice = selected
      }
      utterance.onend = () => onEnd?.()
      window.speechSynthesis.speak(utterance)
    },
    [selectedVoiceURI, muted],
  )
```

- [ ] **Step 2: Verify the frontend still type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no type errors (the new `language` parameter is optional, so existing call sites without a third argument remain valid).

---

### Task 8: Frontend — pass the detected language through to `speak()`

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:47-55` (`BackendResponse` interface), `:488-493` (`handleSend`'s speak call)

- [ ] **Step 1: Add `language` to the `BackendResponse` interface**

Modify `frontend/components/jarvis-interface.tsx`, replacing the existing interface (current lines 47-55):
```typescript
interface BackendResponse {
  answer: string
  provider: string
  model?: string | null
  tools_used?: ToolUsed[]
  action?: ClientAction | null
  error?: string | null
  image_url?: string | null
  language?: string
}
```

- [ ] **Step 2: Pass the language through when speaking the response**

Modify `frontend/components/jarvis-interface.tsx`. In `handleSend`, find:
```typescript
      if (!muted && supported) {
        setOrbState("speaking")
        speak(response.answer, () => setOrbState("idle"))
      } else {
        setOrbState("idle")
      }
```
Replace it with:
```typescript
      if (!muted && supported) {
        setOrbState("speaking")
        speak(response.answer, () => setOrbState("idle"), response.language)
      } else {
        setOrbState("idle")
      }
```

- [ ] **Step 3: Verify the frontend still type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 9: End-to-end manual verification

**Files:**
- None (verification only).

- [ ] **Step 1: Start both servers**

Run (PowerShell), in two separate terminals:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Open `http://localhost:3000` in a Chromium-based browser.

- [ ] **Step 2: Verify proactive name recall across sessions**

Type: `Remember that my name is <your name>`. Reload the page (new session, history cleared client-side). Type: `Hello`. Expected: JARVIS greets you by name without being asked to recall it.

- [ ] **Step 3: Verify proactive fact-saving without an explicit "remember" instruction**

Type a preference without the word "remember", e.g. `I really love hiking on weekends`. Then type: `What do you know about me?`. Expected: the hiking preference is included in the answer, and `tools_used` metadata under the reply shows a `✓ save_memory` call happened on the first message.

- [ ] **Step 4: Verify bilingual text and voice**

Type a full message in Spanish, e.g. `Hola, ¿qué hora es en Madrid?`. Expected: the reply text is in Spanish, and if the browser has a Spanish voice installed (check the voice dropdown in the header for any `es-*` entries), it's spoken in that voice.

- [ ] **Step 5: Verify language switches back**

Immediately send an English message, e.g. `Thanks, what about in New York?`. Expected: the reply switches back to English text and (if applicable) the English voice.

- [ ] **Step 6: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- Groq Whisper-based speech-to-text (accurate spoken Spanish input) — planned as increment 1b, a separate plan.
- Everything else in `AGENT.md` beyond Section 1 — each future section gets its own brainstorming → spec → plan cycle, one increment at a time, per the project's existing instruction.

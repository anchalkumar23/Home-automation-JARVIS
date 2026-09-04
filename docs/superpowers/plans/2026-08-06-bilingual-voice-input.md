# Core AI Assistant Foundation — Increment 1b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frontend's browser-only, English-only microphone (`SpeechRecognition`) with `MediaRecorder`-based audio capture uploaded to a new backend endpoint that proxies to Groq's Whisper transcription API, so spoken Spanish (and English) both transcribe correctly.

**Architecture:** The frontend records audio with `MediaRecorder`, uploads the blob as `multipart/form-data` to a new `POST /api/transcribe` backend endpoint, which forwards it to Groq's Whisper endpoint (keeping the API key server-side, mirroring the existing `/api/chat` proxy pattern) and returns plain transcribed text. The wake-word listener keeps using the browser's `SpeechRecognition` unchanged — it only needs to catch one English word ("Jarvis") in the background.

**Tech Stack:** FastAPI, Python stdlib `urllib` (no new HTTP library), pytest, Next.js/React, browser `MediaRecorder` + `getUserMedia`.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test run or manual verification step instead of a commit step.

---

### Task 1: Backend config and schema additions

**Files:**
- Modify: `backend/app/config.py:28-57` (`Settings` dataclass and `get_settings`)
- Modify: `backend/app/schemas.py` (append `TranscribeResponse`)
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add `groq_whisper_model` to the `Settings` dataclass**

Modify `backend/app/config.py`, replacing the `Settings` dataclass (current lines 28-38):
```python
@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    provider: str
    openai_api_key: str
    openai_model: str
    groq_api_key: str
    groq_model: str
    groq_whisper_model: str
    database_path: Path
```

- [ ] **Step 2: Populate it in `get_settings`**

Modify `backend/app/config.py`, replacing the `get_settings` function (current lines 41-57):
```python
def get_settings() -> Settings:
    load_dotenv()
    origins = os.getenv(
        "JARVIS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
    )
    return Settings(
        host=os.getenv("JARVIS_HOST", "127.0.0.1"),
        port=int(os.getenv("JARVIS_PORT", "8000")),
        allowed_origins=parse_csv(origins),
        provider=os.getenv("JARVIS_PROVIDER", "auto").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_whisper_model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        database_path=DATA_DIR / "jarvis.db",
    )
```

- [ ] **Step 3: Add `GROQ_WHISPER_MODEL` to both env files**

Modify `backend/.env`, adding this line directly after the existing `GROQ_MODEL=openai/gpt-oss-120b` line:
```
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
```

Modify `backend/.env.example`, adding this line directly after the existing `GROQ_MODEL=openai/gpt-oss-120b` line:
```
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
```

- [ ] **Step 4: Add the `TranscribeResponse` schema**

Modify `backend/app/schemas.py`, appending this class at the end of the file (after the existing `ChatResponse` class):
```python


class TranscribeResponse(BaseModel):
    text: str
```

- [ ] **Step 5: Verify the app still imports cleanly**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -c "from app.config import get_settings; from app.schemas import TranscribeResponse; s = get_settings(); print(s.groq_whisper_model); print(TranscribeResponse(text='hello').text)"
```
Expected: prints `whisper-large-v3-turbo` then `hello`.

---

### Task 2: Multipart body builder (TDD)

**Files:**
- Create: `backend/app/routers/transcribe.py` (helper function only in this task; the endpoint itself is Task 3)
- Create: `backend/tests/test_transcribe.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_transcribe.py`:
```python
from app.routers.transcribe import build_multipart_body


def test_build_multipart_body_includes_model_field():
    body, content_type = build_multipart_body(
        "recording.webm", b"fake-audio-bytes", "audio/webm", "whisper-large-v3-turbo"
    )
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="model"' in body
    assert b"whisper-large-v3-turbo" in body


def test_build_multipart_body_includes_file_field_and_bytes():
    body, _ = build_multipart_body(
        "recording.webm", b"fake-audio-bytes", "audio/webm", "whisper-large-v3-turbo"
    )
    assert b'name="file"; filename="recording.webm"' in body
    assert b"Content-Type: audio/webm" in body
    assert b"fake-audio-bytes" in body


def test_build_multipart_body_ends_with_closing_boundary():
    body, content_type = build_multipart_body("recording.webm", b"x", "audio/webm", "whisper-large-v3-turbo")
    boundary = content_type.split("boundary=")[1]
    assert body.rstrip(b"\r\n").endswith(f"--{boundary}--".encode("utf-8"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_transcribe.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `app/routers/transcribe.py` doesn't exist yet.

- [ ] **Step 3: Create `transcribe.py` with the multipart builder**

Create `backend/app/routers/transcribe.py`:
```python
from __future__ import annotations

import uuid


def build_multipart_body(
    filename: str, file_bytes: bytes, content_type: str, model: str
) -> tuple[bytes, str]:
    """Build a multipart/form-data body for Groq's audio transcription endpoint."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_transcribe.py -v
```
Expected: 3 passed.

---

### Task 3: `/api/transcribe` endpoint

**Files:**
- Modify: `backend/app/routers/transcribe.py` (add the Groq-calling function and the FastAPI route)
- Modify: `backend/app/main.py:1-44` (register the new router)

- [ ] **Step 1: Add the Groq-calling function and the route**

Modify `backend/app/routers/transcribe.py`, replacing its full contents with:
```python
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.schemas import TranscribeResponse

router = APIRouter(prefix="/api", tags=["transcribe"])


def build_multipart_body(
    filename: str, file_bytes: bytes, content_type: str, model: str
) -> tuple[bytes, str]:
    """Build a multipart/form-data body for Groq's audio transcription endpoint."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe_with_groq(
    api_key: str, model: str, filename: str, file_bytes: bytes, content_type: str
) -> str:
    body, content_type_header = build_multipart_body(filename, file_bytes, content_type, model)
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type_header,
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq transcription HTTP {exc.code}: {body_text}") from exc
    except Exception as exc:
        raise RuntimeError(f"Groq transcription request failed: {exc}") from exc

    return str(payload.get("text", ""))


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: Request, audio: UploadFile = File(...)) -> TranscribeResponse:
    settings = request.app.state.settings
    if not settings.groq_api_key:
        raise HTTPException(status_code=400, detail="Voice transcription requires a Groq API key.")

    file_bytes = await audio.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="No audio data received.")

    try:
        text = transcribe_with_groq(
            settings.groq_api_key,
            settings.groq_whisper_model,
            audio.filename or "recording.webm",
            file_bytes,
            audio.content_type or "audio/webm",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TranscribeResponse(text=text.strip())
```

- [ ] **Step 2: Run the existing tests to verify the module still works**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_transcribe.py -v
```
Expected: 3 passed (the tests import the same `build_multipart_body` function, now alongside the new route code in the same file).

- [ ] **Step 3: Register the router in `main.py`**

Modify `backend/app/main.py`, replacing its full contents with:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.chat import router as chat_router
from app.routers.transcribe import router as transcribe_router
from app.services.memory import MemoryStore
from app.services.tool_runner import ToolRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    memory_store = MemoryStore(settings.database_path)
    app.state.settings = settings
    app.state.memory_store = memory_store
    app.state.tool_runner = ToolRunner(memory_store)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JARVIS Backend", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(transcribe_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "jarvis-backend"}

    return app


app = create_app()
```

- [ ] **Step 4: Restart the backend**

The model/router registration requires a real process restart (not just `--reload`, to be safe). Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`.

- [ ] **Step 5: Sanity-check the endpoint end-to-end with a synthetic audio file**

This verifies the whole proxy pipeline (multipart encoding, Groq auth, response parsing) works before relying on a real microphone recording. Generate a tiny silent WAV and POST it:

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -c "
import wave
with wave.open('test_silence.wav', 'wb') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(16000)
    f.writeframes(b'\x00\x00' * 16000)
"
$form = @{ audio = Get-Item "test_silence.wav" }
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/transcribe" -Method Post -Form $form
$response | ConvertTo-Json
Remove-Item "test_silence.wav"
```
Expected: HTTP 200 with a JSON body containing a `text` field (likely empty or near-empty, since the audio is silence — that's fine, this step is testing the plumbing works without error, not transcription accuracy). If this errors, check the backend terminal window for the actual Groq error message before proceeding to Task 4.

---

### Task 4: Frontend — MediaRecorder-based recording in `use-speech.ts`

**Files:**
- Modify: `frontend/lib/use-speech.ts` (full-file restructure of the state/refs block, the init effect, and `startListening`/`stopListening`; `speak`, `cancelSpeech`, and the wake-word functions are untouched)

- [ ] **Step 1: Add the `transcribeAudio` helper and a backend URL constant**

Modify `frontend/lib/use-speech.ts`, adding this near the top of the file, directly after the `scoreVoice` function (current lines 17-25) and before `export function useSpeech()`:
```typescript
const TRANSCRIBE_URL = `${process.env.NEXT_PUBLIC_JARVIS_BACKEND ?? "http://127.0.0.1:8000"}/api/transcribe`

async function transcribeAudio(blob: Blob, mimeType: string): Promise<string> {
  const extension = mimeType.includes("ogg") ? "ogg" : mimeType.includes("mp4") ? "mp4" : "webm"
  const formData = new FormData()
  formData.append("audio", blob, `recording.${extension}`)

  const response = await fetch(TRANSCRIBE_URL, { method: "POST", body: formData })

  if (!response.ok) {
    let detail = "Transcription failed."
    try {
      const data = await response.json()
      if (typeof data.detail === "string") detail = data.detail
    } catch {
      // ignore parse failure, use default message
    }
    throw new Error(detail)
  }

  const data = await response.json()
  return typeof data.text === "string" ? data.text : ""
}
```

- [ ] **Step 2: Replace the state/refs block**

Modify `frontend/lib/use-speech.ts`, replacing the current state/refs declarations (current lines 27-41, from `export function useSpeech() {` through the `wakeActiveRef` line):
```typescript
export function useSpeech() {
  const [supported, setSupported] = useState(false)
  const [wakeWordSupported, setWakeWordSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const [voices, setVoices] = useState<VoiceOption[]>([])
  const [selectedVoiceURI, setSelectedVoiceURI] = useState<string>("")
  const [muted, setMuted] = useState(false)
  const [wakeWordActive, setWakeWordActive] = useState(false)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const micStreamRef = useRef<MediaStream | null>(null)
  const wakeRecognitionRef = useRef<any>(null)
  const onResultRef = useRef<(text: string) => void>(() => {})
  const onErrorRef = useRef<(message: string) => void>(() => {})
  const onWakeRef = useRef<() => void>(() => {})
  const rawVoicesRef = useRef<SpeechSynthesisVoice[]>([])
  // Use a ref to track wake-word-active so the onend closure always sees current value
  const wakeActiveRef = useRef(false)
```

- [ ] **Step 3: Replace the capability-detection effect**

Modify `frontend/lib/use-speech.ts`, replacing the init `useEffect` (current lines 67-100, from `// --- Initialise recognition + voice loading ---` through its closing `}, [loadVoices])`):
```typescript
  // --- Initialise capability detection + voice loading ---
  useEffect(() => {
    if (typeof window === "undefined") return

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    const hasSynth = "speechSynthesis" in window
    const hasRecorder =
      typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia)

    setSupported(hasRecorder && hasSynth)
    setWakeWordSupported(Boolean(SpeechRecognition))

    if (hasSynth) {
      loadVoices()
      window.speechSynthesis.addEventListener("voiceschanged", loadVoices)
      return () => {
        window.speechSynthesis.removeEventListener("voiceschanged", loadVoices)
      }
    }
  }, [loadVoices])
```

- [ ] **Step 4: Replace `startListening`/`stopListening` with the MediaRecorder implementation**

Modify `frontend/lib/use-speech.ts`, replacing the current `startListening`/`stopListening` block (current lines 102-118, from `// --- Primary microphone listening ---` through the closing `}, [])` of `stopListening`):
```typescript
  // --- Primary microphone recording + Whisper transcription ---
  const startListening = useCallback(
    (onResult: (text: string) => void, onError?: (message: string) => void) => {
      onResultRef.current = onResult
      onErrorRef.current = onError ?? (() => {})

      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then((stream) => {
          micStreamRef.current = stream
          const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : ""
          const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
          audioChunksRef.current = []

          recorder.ondataavailable = (event: BlobEvent) => {
            if (event.data.size > 0) audioChunksRef.current.push(event.data)
          }

          recorder.onstop = async () => {
            micStreamRef.current?.getTracks().forEach((track) => track.stop())
            micStreamRef.current = null
            setListening(false)

            const recordedType = recorder.mimeType || "audio/webm"
            const blob = new Blob(audioChunksRef.current, { type: recordedType })
            audioChunksRef.current = []

            if (blob.size === 0) {
              onErrorRef.current("No audio was recorded. Please try again.")
              return
            }

            try {
              const text = await transcribeAudio(blob, recordedType)
              if (!text.trim()) {
                onErrorRef.current("Couldn't make out what you said. Please try again or type your message.")
                return
              }
              onResultRef.current(text)
            } catch (err) {
              onErrorRef.current(
                err instanceof Error
                  ? err.message
                  : "Couldn't transcribe that. Please try again or type your message.",
              )
            }
          }

          mediaRecorderRef.current = recorder
          recorder.start()
          setListening(true)
        })
        .catch(() => {
          onErrorRef.current(
            "Microphone access was denied or unavailable. Please allow microphone access, or type your message instead.",
          )
        })
    },
    [],
  )

  const stopListening = useCallback(() => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
  }, [])
```

- [ ] **Step 5: Add `wakeWordSupported` to the returned object**

Modify `frontend/lib/use-speech.ts`, replacing the final `return` statement (current lines 224-240):
```typescript
  return {
    supported,
    wakeWordSupported,
    listening,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
    voices,
    selectedVoiceURI,
    setSelectedVoiceURI,
    muted,
    setMuted,
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
  }
}
```

- [ ] **Step 6: Verify the frontend type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no type errors.

---

### Task 5: Frontend — wire error handling and capability gating in `jarvis-interface.tsx`

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:374-389` (destructure `wakeWordSupported`)
- Modify: `frontend/components/jarvis-interface.tsx` (add `handleVoiceError`, wire it into 3 call sites)
- Modify: `frontend/components/jarvis-interface.tsx:684-700` (Wake button gating)
- Modify: `frontend/components/jarvis-interface.tsx:927-930` (outdated browser-support message)

- [ ] **Step 1: Destructure `wakeWordSupported` from the hook**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `useSpeech()` destructure (current lines 374-389):
```typescript
  const {
    supported,
    wakeWordSupported,
    listening,
    startListening,
    stopListening,
    speak,
    cancelSpeech,
    voices,
    selectedVoiceURI,
    setSelectedVoiceURI,
    muted,
    setMuted,
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
  } = useSpeech()
```

- [ ] **Step 2: Add a `handleVoiceError` callback**

Modify `frontend/components/jarvis-interface.tsx`, adding this new callback directly after the closing of `handleSend` (current line 497, right after `[speak, supported, muted, cancelSpeech],\n  )`) and before the `// ── Mic toggle ─────` comment:
```typescript

  // ── Voice input error handler ────────────────────────────────────────
  const handleVoiceError = useCallback((message: string) => {
    setOrbState("idle")
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "assistant" as const, content: message },
    ])
  }, [])
```

- [ ] **Step 3: Pass `handleVoiceError` into the `toggleMic` call site**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `toggleMic` callback (current lines 500-513):
```typescript
  // ── Mic toggle ─────────────────────────────────────────────────────
  const toggleMic = useCallback(() => {
    if (!supported) return
    if (listening) {
      stopListening()
      setOrbState("idle")
      return
    }
    cancelSpeech()
    setOrbState("listening")
    startListening((text) => {
      setOrbState("thinking")
      handleSend(text)
    }, handleVoiceError)
  }, [supported, listening, stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])
```

- [ ] **Step 4: Pass `handleVoiceError` into the `Ctrl+J`/`Alt+J` call site**

Modify `frontend/components/jarvis-interface.tsx`, replacing the keyboard-shortcut effect (current lines 521-544):
```typescript
  // ── Keyboard shortcuts: Ctrl+J / Alt+J ──────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.altKey) && e.key.toLowerCase() === "j") {
        e.preventDefault()
        if (stateRef.current === "speaking") {
          cancelSpeech()
          setOrbState("idle")
        }
        if (stateRef.current === "listening") {
          stopListening()
          setOrbState("idle")
        } else if (stateRef.current === "idle") {
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [stopListening, cancelSpeech, startListening, handleSend, handleVoiceError])
```

- [ ] **Step 5: Pass `handleVoiceError` into the wake-word trigger call site**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `toggleWakeWord` callback (current lines 547-570):
```typescript
  // ── Wake word ────────────────────────────────────────────────────────
  const toggleWakeWord = useCallback(() => {
    if (wakeWordActive) {
      stopWakeWordDetection()
    } else {
      startWakeWordDetection(() => {
        if (stateRef.current === "idle") {
          stopWakeWordDetection()
          cancelSpeech()
          setOrbState("listening")
          startListening((text) => {
            setOrbState("thinking")
            handleSend(text)
          }, handleVoiceError)
        }
      })
    }
  }, [
    wakeWordActive,
    startWakeWordDetection,
    stopWakeWordDetection,
    cancelSpeech,
    startListening,
    handleSend,
    handleVoiceError,
  ])
```

- [ ] **Step 6: Gate the Wake button on `wakeWordSupported` instead of `supported`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the conditional wrapping the Wake button (current line 684, `{supported && (`):
```typescript
            {wakeWordSupported && (
```
(The rest of that block — the `<button id="wake-word-toggle">` through its closing `)}` — is unchanged; only the guarding condition changes.)

- [ ] **Step 7: Fix the outdated browser-support message**

Modify `frontend/components/jarvis-interface.tsx`, replacing the current message (current lines 927-930):
```typescript
        {!supported && (
          <p className="pb-2 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Voice input requires microphone access and browser audio support. Text input is
            always available.
          </p>
        )}
```

- [ ] **Step 8: Verify the frontend type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 6: End-to-end manual verification

**Files:**
- None (verification only).

- [ ] **Step 1: Restart both servers**

Run (PowerShell), in two separate terminals (skip if already running from Task 3):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Open `http://localhost:3000` in a Chromium-based browser.

- [ ] **Step 2: Verify English voice input**

Click the mic button, allow microphone access when prompted, speak a short command in English (e.g. "What time is it?"), click the mic button again to stop. Expected: the recorded speech is correctly transcribed and sent; JARVIS responds normally.

- [ ] **Step 3: Verify Spanish voice input (the core fix)**

Click the mic button, speak a command in Spanish (e.g. "¿Qué hora es?"), click again to stop. Expected: correctly transcribed in Spanish — this is the capability the old browser recognizer could not provide.

- [ ] **Step 4: Verify wake word still works and hands off correctly**

Click "Wake" in the header, say "Jarvis" out loud, then speak a command in either language once it starts listening. Expected: wake-word detection still triggers (unchanged), followed by correct Whisper-based transcription of the command.

- [ ] **Step 5: Verify microphone permission denial is handled gracefully**

In the browser's site settings, block microphone access for `localhost:3000`, reload, then click the mic button. Expected: a clear inline message appears in the comms log (not a silent failure or console-only error); typing still works normally.

- [ ] **Step 6: Verify the Ctrl+J / Alt+J shortcuts still work**

Press `Ctrl+J`, speak a short command, press `Ctrl+J` again to stop. Expected: same recording/transcription flow as the mic button.

- [ ] **Step 7 (optional): Verify broader browser support**

If a non-Chromium browser (e.g. Firefox) is available, open the app there. Expected: the mic button is enabled and voice input works; the "Wake" button should not appear (or should be disabled), since wake-word detection still depends on Chromium's `SpeechRecognition`.

- [ ] **Step 8: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- Everything else in `AGENT.md` beyond Section 1 — each future section gets its own brainstorming → spec → plan cycle, one increment at a time, per the project's established workflow.

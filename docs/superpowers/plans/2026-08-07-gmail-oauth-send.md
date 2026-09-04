# Productivity Foundation — Increment 2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let JARVIS actually send email through the user's own Gmail account, via a one-time in-app OAuth connection, with sending always triggered by a user-clicked button rather than the AI model.

**Architecture:** `google-auth` + `google-auth-oauthlib` handle the OAuth consent flow and token refresh (avoiding hand-rolled refresh bugs); the actual Gmail API call is a plain `urllib` POST matching this backend's existing HTTP style. Tokens live in a new single-row table in the existing SQLite `MemoryStore`. The frontend gets a "Connect Gmail" header button and a "Send via Gmail" button on the existing email-draft card — both call the backend directly, never through the LLM tool-calling loop.

**Tech Stack:** FastAPI, `google-auth`, `google-auth-oauthlib`, stdlib `urllib`/`email`/`base64`, pytest, Next.js/React.

**Note on git:** the user is handling all git init/commit/push themselves. No task in this plan runs a git command — each task ends with a test/build/manual-verification step instead.

---

### Task 1: Google Cloud Console setup (manual, done by the user)

**Files:** None — this is manual setup performed in a browser.

- [ ] **Step 1: Create a new Google Cloud project**

Go to `https://console.cloud.google.com/projectcreate`, name it something like "JARVIS Assistant," and create it.

- [ ] **Step 2: Enable the Gmail API**

In the new project, go to `https://console.cloud.google.com/apis/library/gmail.googleapis.com` and click Enable.

- [ ] **Step 3: Configure the OAuth consent screen**

Go to `https://console.cloud.google.com/apis/credentials/consent`. Choose **External** user type. Fill in the required app name/support email fields. Under Scopes, add `https://www.googleapis.com/auth/gmail.send` — no other scopes. Under Test users, add your own Google account email (required while the app is in testing mode — without this, consent will be blocked).

- [ ] **Step 4: Create OAuth Client ID credentials**

Go to `https://console.cloud.google.com/apis/credentials`, click "Create Credentials" → "OAuth client ID," choose type **Web application**. Under "Authorized redirect URIs," add exactly:
```
http://127.0.0.1:8000/api/gmail/callback
```
Create it, then copy the generated **Client ID** and **Client Secret**.

- [ ] **Step 5: Add the credentials to `backend/.env`**

Open `backend/.env` and set (this is done as part of Task 2 below, once the file has the new variable names — note them here for now):
```
GOOGLE_CLIENT_ID=<paste your Client ID>
GOOGLE_CLIENT_SECRET=<paste your Client Secret>
```

---

### Task 2: Backend config, dependencies, and env variables

**Files:**
- Modify: `backend/app/config.py:28-59` (`Settings` dataclass and `get_settings`)
- Modify: `backend/requirements.txt`
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add Google OAuth fields to `Settings`**

Modify `backend/app/config.py`, replacing the `Settings` dataclass (current lines 28-39):
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
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    database_path: Path
```

- [ ] **Step 2: Populate them in `get_settings`**

Modify `backend/app/config.py`, replacing the `get_settings` function (current lines 42-59):
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
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback"),
        database_path=DATA_DIR / "jarvis.db",
    )
```

- [ ] **Step 3: Add the new dependencies**

Modify `backend/requirements.txt`, appending:
```
google-auth>=2.35.0
google-auth-oauthlib>=1.2.1
```

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Expected: `google-auth`, `google-auth-oauthlib`, and their dependencies (including `requests`) install successfully.

- [ ] **Step 4: Add the env variables**

Modify `backend/.env`, appending after the existing `GROQ_WHISPER_MODEL=whisper-large-v3-turbo` line:
```

# Google OAuth (Gmail send) — see Task 1 for setup steps
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/gmail/callback
```
Fill in `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` with the values from Task 1, Step 4.

Modify `backend/.env.example`, appending the same block but with blank `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (already blank by default, matching the pattern of the other secrets in this file).

- [ ] **Step 5: Verify settings load correctly**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -c "from app.config import get_settings; s = get_settings(); print(bool(s.google_client_id)); print(s.google_redirect_uri)"
```
Expected: prints `True` (assuming Step 4's values were filled in) then `http://127.0.0.1:8000/api/gmail/callback`.

---

### Task 3: `oauth_tokens` storage in `MemoryStore` (TDD)

**Files:**
- Modify: `backend/app/services/memory.py:19-44` (`_init_db`), append new methods after `list_tasks`
- Create: `backend/tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_memory.py`:
```python
from app.services.memory import MemoryStore


def test_get_google_tokens_returns_none_when_not_connected(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.get_google_tokens() is None


def test_save_and_get_google_tokens_roundtrip(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_google_tokens(
        access_token="access123",
        refresh_token="refresh456",
        expiry="2026-01-01T00:00:00+00:00",
        scopes="https://www.googleapis.com/auth/gmail.send",
        email="user@example.com",
    )

    result = store.get_google_tokens()

    assert result["access_token"] == "access123"
    assert result["refresh_token"] == "refresh456"
    assert result["email"] == "user@example.com"


def test_save_google_tokens_upserts_single_row(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_google_tokens(
        access_token="first", refresh_token="r1", expiry="", scopes="", email=None,
    )
    store.save_google_tokens(
        access_token="second", refresh_token="r2", expiry="", scopes="", email="a@b.com",
    )

    result = store.get_google_tokens()

    assert result["access_token"] == "second"
    assert result["email"] == "a@b.com"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_memory.py -v
```
Expected: `AttributeError: 'MemoryStore' object has no attribute 'get_google_tokens'`.

- [ ] **Step 3: Add the `oauth_tokens` table**

Modify `backend/app/services/memory.py`, inside `_init_db` (current lines 19-44), adding a new `connection.execute(...)` call for the new table right after the existing `tasks` table creation and before `connection.commit()`:
```python
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expiry TEXT,
                    scopes TEXT,
                    email TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
```
(This goes directly before the existing `connection.commit()` line that currently ends `_init_db`.)

- [ ] **Step 4: Add `save_google_tokens` and `get_google_tokens`**

Modify `backend/app/services/memory.py`, appending these two methods after the existing `list_tasks` method (at the end of the class):
```python

    def save_google_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expiry: str,
        scopes: str,
        email: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO oauth_tokens (id, access_token, refresh_token, expiry, scopes, email, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expiry = excluded.expiry,
                    scopes = excluded.scopes,
                    email = excluded.email,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (access_token, refresh_token, expiry, scopes, email),
            )
            connection.commit()

    def get_google_tokens(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT access_token, refresh_token, expiry, scopes, email FROM oauth_tokens WHERE id = 1"
            ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_memory.py -v
```
Expected: 3 passed.

---

### Task 4: `backend/app/services/google_auth.py` (new file, TDD where feasible)

**Files:**
- Create: `backend/app/services/google_auth.py`
- Create: `backend/tests/test_google_auth.py`

- [ ] **Step 1: Write the failing test for `build_auth_url`**

Create `backend/tests/test_google_auth.py`:
```python
from pathlib import Path

from app.config import Settings


def _fake_settings() -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=[],
        provider="auto",
        openai_api_key="",
        openai_model="",
        groq_api_key="",
        groq_model="",
        groq_whisper_model="",
        google_client_id="test-client-id",
        google_client_secret="test-secret",
        google_redirect_uri="http://127.0.0.1:8000/api/gmail/callback",
        database_path=Path("unused.db"),
    )


def test_build_auth_url_includes_client_id_and_scope():
    from app.services.google_auth import build_auth_url

    url = build_auth_url(_fake_settings())

    assert "accounts.google.com" in url
    assert "client_id=test-client-id" in url
    assert "gmail.send" in url
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_google_auth.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.google_auth'`.

- [ ] **Step 3: Create `google_auth.py`**

Create `backend/app/services/google_auth.py`:
```python
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import Settings
from app.services.memory import MemoryStore

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _client_config(settings: Settings) -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def _make_flow(settings: Settings) -> Flow:
    return Flow.from_client_config(
        _client_config(settings),
        scopes=[GMAIL_SEND_SCOPE],
        redirect_uri=settings.google_redirect_uri,
    )


def build_auth_url(settings: Settings) -> str:
    flow = _make_flow(settings)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url


def _fetch_email_address(access_token: str) -> str | None:
    request = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("email")
    except Exception:
        return None


def exchange_code(settings: Settings, store: MemoryStore, code: str) -> str | None:
    flow = _make_flow(settings)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    email = _fetch_email_address(credentials.token)

    store.save_google_tokens(
        access_token=credentials.token,
        refresh_token=credentials.refresh_token or "",
        expiry=credentials.expiry.isoformat() if credentials.expiry else "",
        scopes=" ".join(credentials.scopes or [GMAIL_SEND_SCOPE]),
        email=email,
    )
    return email


def get_valid_access_token(settings: Settings, store: MemoryStore) -> str:
    stored = store.get_google_tokens()
    if not stored or not stored.get("refresh_token"):
        raise RuntimeError("Gmail is not connected. Please connect Gmail first.")

    stored_expiry = None
    if stored.get("expiry"):
        try:
            stored_expiry = datetime.fromisoformat(stored["expiry"])
        except ValueError:
            stored_expiry = None

    credentials = Credentials(
        token=stored["access_token"],
        refresh_token=stored["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=stored["scopes"].split() if stored.get("scopes") else [GMAIL_SEND_SCOPE],
        expiry=stored_expiry,
    )

    if not credentials.valid:
        try:
            credentials.refresh(GoogleAuthRequest())
        except Exception as exc:
            raise RuntimeError("Gmail connection expired. Please reconnect.") from exc
        store.save_google_tokens(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or stored["refresh_token"],
            expiry=credentials.expiry.isoformat() if credentials.expiry else "",
            scopes=" ".join(credentials.scopes or [GMAIL_SEND_SCOPE]),
            email=stored.get("email"),
        )

    return credentials.token
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_google_auth.py tests/test_memory.py tests/test_provider.py tests/test_transcribe.py -v
```
Expected: all tests pass (1 new + the 3 from Task 3 + the previously-existing 12 from earlier increments = 16 total). `exchange_code` and `get_valid_access_token` are not unit-tested here since they require a real Google OAuth exchange/refresh over the network — they're covered by Task 8's manual verification instead, consistent with how this project has always left network-dependent provider calls to manual testing.

---

### Task 5: `/api/gmail/*` endpoints

**Files:**
- Modify: `backend/app/schemas.py` (append 4 new models)
- Create: `backend/app/routers/gmail.py`
- Modify: `backend/app/main.py:1-46` (register the router)

- [ ] **Step 1: Add the Gmail schemas**

Modify `backend/app/schemas.py`, appending after the existing `TranscribeResponse` class (current lines 48-49):
```python


class GmailAuthUrlResponse(BaseModel):
    url: str


class GmailStatusResponse(BaseModel):
    connected: bool
    email: str | None = None


class SendEmailRequest(BaseModel):
    to: str = Field(min_length=1, max_length=320)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="")


class SendEmailResponse(BaseModel):
    ok: bool
    message_id: str | None = None
```

- [ ] **Step 2: Create the router**

Create `backend/app/routers/gmail.py`:
```python
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.schemas import (
    GmailAuthUrlResponse,
    GmailStatusResponse,
    SendEmailRequest,
    SendEmailResponse,
)
from app.services import google_auth

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/auth-url", response_model=GmailAuthUrlResponse)
async def auth_url(request: Request) -> GmailAuthUrlResponse:
    settings = request.app.state.settings
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured on the backend.")
    return GmailAuthUrlResponse(url=google_auth.build_auth_url(settings))


@router.get("/callback", response_class=HTMLResponse)
async def callback(request: Request, code: str | None = None, error: str | None = None) -> HTMLResponse:
    if error:
        return HTMLResponse(f"<h1>Gmail connection cancelled</h1><p>{error}</p>", status_code=400)
    if not code:
        return HTMLResponse(
            "<h1>Gmail connection failed</h1><p>No authorization code received.</p>", status_code=400
        )

    settings = request.app.state.settings
    store = request.app.state.memory_store
    try:
        email = google_auth.exchange_code(settings, store, code)
    except Exception as exc:
        return HTMLResponse(f"<h1>Gmail connection failed</h1><p>{exc}</p>", status_code=400)

    label = f" as {email}" if email else ""
    return HTMLResponse(f"<h1>Gmail connected{label}</h1><p>You can close this tab and return to JARVIS.</p>")


@router.get("/status", response_model=GmailStatusResponse)
async def status(request: Request) -> GmailStatusResponse:
    store = request.app.state.memory_store
    stored = store.get_google_tokens()
    if not stored:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(connected=True, email=stored.get("email"))


@router.post("/send", response_model=SendEmailResponse)
async def send(payload: SendEmailRequest, request: Request) -> SendEmailResponse:
    to = payload.to.strip()
    if not to:
        raise HTTPException(status_code=400, detail="Recipient email address is required.")

    settings = request.app.state.settings
    store = request.app.state.memory_store

    try:
        access_token = google_auth.get_valid_access_token(settings, store)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = payload.subject
    message.set_content(payload.body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    api_request = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(api_request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Gmail send failed: {body_text}") from exc

    return SendEmailResponse(ok=True, message_id=data.get("id"))
```

- [ ] **Step 3: Register the router**

Modify `backend/app/main.py`, replacing its full contents with:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.chat import router as chat_router
from app.routers.gmail import router as gmail_router
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
    app.include_router(gmail_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "jarvis-backend"}

    return app


app = create_app()
```

- [ ] **Step 4: Restart the backend and verify it boots**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:8000/api/gmail/status -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: health check returns `{"status":"online","service":"jarvis-backend"}`; the status check returns `{"connected":false,"email":null}` (nothing connected yet).

- [ ] **Step 5: Run the full backend test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: all 16 tests pass.

---

### Task 6: Frontend — shared message helper + Gmail connect button

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:365-373` (new state)
- Modify: `frontend/components/jarvis-interface.tsx:405-420` (add Gmail status check effect)
- Modify: `frontend/components/jarvis-interface.tsx:501-508` (extract `pushSystemMessage`, reuse in `handleVoiceError`)
- Modify: `frontend/components/jarvis-interface.tsx:696-712` (add Gmail header button next to the Wake button)

- [ ] **Step 1: Add new state for Gmail connection status**

Modify `frontend/components/jarvis-interface.tsx`, in the state declarations at the top of `JarvisInterface` (current lines 366-373), adding two new lines after `const [fullscreenImage, setFullscreenImage] = useState<string | null>(null)`:
```typescript
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null)
  const [gmailEmail, setGmailEmail] = useState<string | null>(null)
  const [sendingEmail, setSendingEmail] = useState(false)
```

- [ ] **Step 2: Add a Gmail status check on mount**

Modify `frontend/components/jarvis-interface.tsx`, adding this new effect directly after the existing "Check backend health on mount" effect (current lines 405-420, ending in `}, [])`):
```typescript

  // Check Gmail connection status on mount
  useEffect(() => {
    let cancelled = false
    async function checkGmail() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/status`)
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) {
          setGmailConnected(Boolean(data.connected))
          setGmailEmail(data.email ?? null)
        }
      } catch {
        if (!cancelled) setGmailConnected(false)
      }
    }
    checkGmail()
    return () => {
      cancelled = true
    }
  }, [])
```

- [ ] **Step 3: Extract `pushSystemMessage` and reuse it in `handleVoiceError`**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `handleVoiceError` callback (current lines 501-508):
```typescript
  // ── Shared comms-log system message helper ─────────────────────────
  const pushSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant" as const, content }])
  }, [])

  // ── Voice input error handler ────────────────────────────────────────
  const handleVoiceError = useCallback(
    (message: string) => {
      setOrbState("idle")
      pushSystemMessage(message)
    },
    [pushSystemMessage],
  )

  // ── Gmail connect + send handlers ───────────────────────────────────
  const handleConnectGmail = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/gmail/auth-url`)
      if (!res.ok) throw new Error()
      const data = await res.json()
      if (data.url) window.open(data.url, "_blank", "noopener,noreferrer")
    } catch {
      pushSystemMessage(
        "Couldn't start the Gmail connection — check that the backend is configured with Google OAuth credentials.",
      )
    }
  }, [pushSystemMessage])

  const handleSendViaGmail = useCallback(
    async (to: string, subject: string, body: string) => {
      if (!to.trim()) {
        pushSystemMessage("Please enter a recipient email address before sending.")
        return
      }
      setSendingEmail(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/gmail/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to, subject, body }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || "Gmail send failed.")
        }
        pushSystemMessage(`Email sent to ${to} via Gmail.`)
      } catch (err) {
        pushSystemMessage(err instanceof Error ? err.message : "Couldn't send the email via Gmail.")
      } finally {
        setSendingEmail(false)
      }
    },
    [pushSystemMessage],
  )
```

- [ ] **Step 4: Add the Gmail header button**

Modify `frontend/components/jarvis-interface.tsx`, adding this new button directly after the closing `)}` of the existing Wake button block (current lines 696-712, i.e. right after `{wakeWordSupported && ( ... )}` and before the closing `</div>` of the header's right-hand button group):
```typescript

            <button
              id="gmail-toggle"
              onClick={gmailConnected ? undefined : handleConnectGmail}
              disabled={gmailConnected === null}
              className={cn(
                "flex h-9 items-center gap-2 rounded-md border px-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors",
                gmailConnected
                  ? "cursor-default border-primary/35 bg-primary/10 text-primary"
                  : "border-border bg-card/35 text-muted-foreground hover:text-foreground",
              )}
              title={gmailConnected ? `Connected as ${gmailEmail ?? "unknown"}` : "Connect Gmail to send email"}
            >
              <Mail className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">{gmailConnected ? "Gmail" : "Connect Gmail"}</span>
            </button>
```

- [ ] **Step 5: Verify the frontend type-checks**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: type errors referencing `EmailDraftCard`/`handleSendViaGmail` usage will NOT yet appear since Task 7 hasn't wired the send button into the draft card. No errors should appear from this task's own changes.

---

### Task 7: Frontend — editable recipient field + real "Send via Gmail" button

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx` (add a new `EmailDraftCard` component near the other small components)
- Modify: `frontend/components/jarvis-interface.tsx:824-861` (use `EmailDraftCard` instead of the inline block)

The current email-draft UI only shows read-only Subject/Body text and a `mailto:` link with no recipient input — the `mailto:` flow relies on the user's own mail client to ask for the recipient. A real "Send via Gmail" button needs an actual recipient value to send, so this task adds an editable "To" field, which requires its own local state — making this a small dedicated component rather than inline JSX, following the same pattern already used for `CopyButton`/`InlineImage`/`ImageModal` in this file.

- [ ] **Step 1: Add the `EmailDraftCard` component**

Modify `frontend/components/jarvis-interface.tsx`, adding this new component directly after the existing `CopyButton` function (which currently ends at line 259 with its closing `}`) and before the `InlineImage` function:
```typescript

/* ── Email Draft Card with editable recipient ───────────────────────────── */

function EmailDraftCard({
  action,
  onSend,
  sending,
}: {
  action: ClientAction
  onSend: (to: string, subject: string, body: string) => void
  sending: boolean
}) {
  const [to, setTo] = useState(action.email_to || "")

  return (
    <div className="mt-3 space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-accent">
        <Mail className="h-3 w-3" />
        Email Draft
      </div>
      <input
        value={to}
        onChange={(e) => setTo(e.target.value)}
        placeholder="Recipient email address"
        className="w-full rounded-md border border-accent/25 bg-card/50 px-2 py-1.5 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
        aria-label="Recipient email address"
      />
      {action.email_subject && (
        <p className="text-[11px] text-foreground">
          <strong>Subject:</strong> {action.email_subject}
        </p>
      )}
      {action.email_body && (
        <p className="max-h-[120px] overflow-y-auto text-[11px] leading-relaxed text-muted-foreground">
          {action.email_body}
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={sending}
          onClick={() => onSend(to, action.email_subject || "", action.email_body || "")}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <Mail className="h-3 w-3" /> {sending ? "Sending…" : "Send via Gmail"}
        </button>
        {action.mailto_link && (
          <a
            href={action.mailto_link}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] text-accent-foreground transition-opacity hover:opacity-90"
          >
            <Mail className="h-3 w-3" /> Open in Mail App
          </a>
        )}
        {action.mailto_link && <CopyButton text={action.mailto_link} label="Copy link" />}
        {action.email_body && (
          <CopyButton
            text={`Subject: ${action.email_subject || ""}\n\n${action.email_body}`}
            label="Copy email"
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Use `EmailDraftCard` in place of the inline block**

Modify `frontend/components/jarvis-interface.tsx`, replacing the existing inline email-draft block (current lines 823-860, from the `{/* Email draft: clickable mailto link + copy buttons */}` comment through its closing `)}`):
```typescript
                  {/* Email draft: recipient input + real send + mailto fallback + copy buttons */}
                  {message.action?.type === "compose_email" && (
                    <EmailDraftCard
                      action={message.action}
                      onSend={handleSendViaGmail}
                      sending={sendingEmail}
                    />
                  )}
```

- [ ] **Step 3: Verify the frontend type-checks and builds**

Run (PowerShell):
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
npm run build
```
Expected: no type errors; production build completes successfully.

---

### Task 8: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart both servers**

Run (PowerShell), in separate terminals as needed:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"; npm run dev
```
Open `http://localhost:3000`.

- [ ] **Step 2: Connect Gmail**

Click the "Connect Gmail" button in the header. Expected: a new tab opens Google's real consent screen; after approving, it redirects to the callback page showing "Gmail connected as <your email>." Return to the JARVIS tab and reload — the header button should now show "Gmail" (connected state) instead of "Connect Gmail."

- [ ] **Step 3: Draft and send a real email**

Type something like "Write an email to yourself about testing JARVIS." Expected: the draft card appears with an empty recipient field, editable Subject/Body. Type your own email address into the recipient field, click "Send via Gmail." Expected: a "Sending…" state briefly, then a comms-log message confirming it sent — and the email actually arrives in the recipient's inbox shortly after.

- [ ] **Step 4: Verify the "Open in Mail App" fallback still works**

On a new email draft, click "Open in Mail App" instead. Expected: still opens your default mail client with the draft prefilled, unaffected by this increment's changes.

- [ ] **Step 5: Verify graceful failure on a bad send**

Try sending with an obviously invalid recipient (e.g. `not-an-email`). Expected: a clear error message in the comms log, not a silent failure or a raw stack trace.

- [ ] **Step 6: Stop both servers**

Ctrl+C in both terminals.

---

## Post-plan: what's explicitly not in this increment

- 2b: Calendar read.
- 2c: Calendar write.
- 2d: Task/reminder redesign (due dates/times).
- Reading or searching the inbox (only `gmail.send` scope requested).
- Any path where the AI model can send email on its own — sending stays a user-clicked action.

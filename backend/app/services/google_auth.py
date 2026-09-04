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
# calendar.events covers both reading and writing (insert/patch/delete) individual
# events, which increment 2c needs — calendar.readonly (used until 2c) can only
# read and is rejected with 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT on any write call.
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
REQUIRED_SCOPES = [GMAIL_SEND_SCOPE, CALENDAR_EVENTS_SCOPE]


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
        scopes=REQUIRED_SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


# Google's OAuth flow uses PKCE: the code_verifier generated when building the
# consent URL must be reused when exchanging the resulting code for a token.
# Those two steps happen in separate HTTP requests (the browser visits Google,
# then Google redirects back to our callback), so the verifier has to be kept
# somewhere in between. A module-level variable is enough for a single local
# user completing one connection flow at a time — no need for a session store.
_pending_code_verifier: str | None = None


def build_auth_url(settings: Settings) -> str:
    global _pending_code_verifier
    flow = _make_flow(settings)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    _pending_code_verifier = flow.code_verifier
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
    global _pending_code_verifier
    flow = _make_flow(settings)
    flow.code_verifier = _pending_code_verifier
    flow.fetch_token(code=code)
    _pending_code_verifier = None
    credentials = flow.credentials

    email = _fetch_email_address(credentials.token)

    store.save_google_tokens(
        access_token=credentials.token,
        refresh_token=credentials.refresh_token or "",
        expiry=credentials.expiry.isoformat() if credentials.expiry else "",
        scopes=" ".join(credentials.scopes or REQUIRED_SCOPES),
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
        scopes=stored["scopes"].split() if stored.get("scopes") else REQUIRED_SCOPES,
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
            scopes=" ".join(credentials.scopes or REQUIRED_SCOPES),
            email=stored.get("email"),
        )

    return credentials.token

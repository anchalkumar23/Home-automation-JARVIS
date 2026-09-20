from __future__ import annotations

import base64
import html
import json
import urllib.error
import urllib.request
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.schemas import (
    GmailAuthUrlResponse,
    GmailStatusResponse,
    SendEmailRequest,
    SendEmailResponse,
)
from app.security import require_session
from app.services import google_auth

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/auth-url", response_model=GmailAuthUrlResponse, dependencies=[Depends(require_session)])
async def auth_url(request: Request) -> GmailAuthUrlResponse:
    settings = request.app.state.settings
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured on the backend.")
    return GmailAuthUrlResponse(url=google_auth.build_auth_url(settings))


@router.get("/callback", response_class=HTMLResponse, dependencies=[Depends(require_session)])
async def callback(request: Request, code: str | None = None, error: str | None = None) -> HTMLResponse:
    # error/code are query params reflected into HTML below — escape them, since
    # this endpoint is a browser-navigable URL an attacker can craft and send.
    if error:
        return HTMLResponse(f"<h1>Gmail connection cancelled</h1><p>{html.escape(error)}</p>", status_code=400)
    if not code:
        return HTMLResponse(
            "<h1>Gmail connection failed</h1><p>No authorization code received.</p>", status_code=400
        )

    settings = request.app.state.settings
    store = request.app.state.memory_store
    try:
        email = google_auth.exchange_code(settings, store, code)
    except Exception as exc:
        return HTMLResponse(f"<h1>Gmail connection failed</h1><p>{html.escape(str(exc))}</p>", status_code=400)

    label = f" as {html.escape(email)}" if email else ""
    return HTMLResponse(f"<h1>Gmail connected{label}</h1><p>You can close this tab and return to JARVIS.</p>")


@router.get("/status", response_model=GmailStatusResponse, dependencies=[Depends(require_session)])
async def status(request: Request) -> GmailStatusResponse:
    store = request.app.state.memory_store
    stored = store.get_google_tokens()
    if not stored:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(connected=True, email=stored.get("email"))


@router.post("/send", response_model=SendEmailResponse, dependencies=[Depends(require_session)])
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

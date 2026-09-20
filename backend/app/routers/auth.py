from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security import SESSION_COOKIE
from app.services.auth import verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_RATE_LIMIT_ATTEMPTS = 5
_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < _RATE_LIMIT_WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    return len(attempts) >= _RATE_LIMIT_ATTEMPTS


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class StatusResponse(BaseModel):
    authenticated: bool


@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    token = request.cookies.get(SESSION_COOKIE)
    store = request.app.state.memory_store
    return StatusResponse(authenticated=bool(token and store.session_valid(token)))


@router.post("/login", response_model=StatusResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> StatusResponse:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    settings = request.app.state.settings
    if not settings.password_hash or not verify_password(payload.password, settings.password_hash):
        _login_attempts[ip].append(time.time())
        raise HTTPException(status_code=401, detail="Incorrect password")

    store = request.app.state.memory_store
    token = store.create_session()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )
    return StatusResponse(authenticated=True)


@router.post("/logout", response_model=StatusResponse)
async def logout(request: Request, response: Response) -> StatusResponse:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        request.app.state.memory_store.delete_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return StatusResponse(authenticated=False)

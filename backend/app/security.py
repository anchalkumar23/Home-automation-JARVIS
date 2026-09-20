from __future__ import annotations

from fastapi import HTTPException, Request

SESSION_COOKIE = "jarvis_session"


async def require_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    store = request.app.state.memory_store
    if not token or not store.session_valid(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

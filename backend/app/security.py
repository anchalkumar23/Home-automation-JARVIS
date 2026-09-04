from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings


async def require_api_key(x_jarvis_key: str = Header(default="")) -> None:
    """Interim shared-secret gate ahead of proper per-user auth.

    Fails closed: if no key is configured, every request is rejected rather
    than silently letting traffic through.
    """
    settings = get_settings()
    if not settings.api_key or x_jarvis_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

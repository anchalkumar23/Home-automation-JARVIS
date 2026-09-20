from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.calendar import router as calendar_router
from app.routers.chat import router as chat_router
from app.routers.gmail import router as gmail_router
from app.routers.tasks import router as tasks_router
from app.routers.transcribe import router as transcribe_router
from app.routers.uploads import router as uploads_router
from app.security import require_session
from app.services.memory import MemoryStore
from app.services.tool_runner import ToolRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    memory_store = MemoryStore(settings.database_path, settings.token_encryption_key)
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
    app.include_router(auth_router)
    gate = [Depends(require_session)]
    app.include_router(chat_router, dependencies=gate)
    app.include_router(transcribe_router, dependencies=gate)
    # gmail_router is gated per-route inside gmail.py (all four routes require
    # a session — a top-level browser navigation still carries the cookie).
    app.include_router(gmail_router)
    app.include_router(calendar_router, dependencies=gate)
    app.include_router(tasks_router, dependencies=gate)
    app.include_router(uploads_router, dependencies=gate)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "jarvis-backend"}

    return app


app = create_app()

from __future__ import annotations

from fastapi import APIRouter, Request

from app.ai.provider import generate_chat_response
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    settings = request.app.state.settings
    tool_runner = request.app.state.tool_runner
    return await generate_chat_response(payload, settings, tool_runner)

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import TaskListResponse

router = APIRouter(tags=["tasks"])


@router.get("/api/tasks", response_model=TaskListResponse)
async def list_tasks(request: Request, include_done: bool = False) -> TaskListResponse:
    store = request.app.state.memory_store
    tasks = store.list_tasks("default", include_done)
    return TaskListResponse(tasks=tasks)

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatMessage] = Field(default_factory=list)
    provider: Literal["auto", "openai", "groq", "local"] = "auto"
    user_id: str = Field(default="default", min_length=1, max_length=80)


class ToolResult(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    ok: bool = True
    error: str | None = None


class ClientAction(BaseModel):
    type: Literal[
        "open_url",
        "compose_email",
        "calendar_event_draft",
        "calendar_event_delete_confirm",
        "business_report",
        "content_draft",
        "subtitle_result",
        "file_upload_request",
        "silence_removal_result",
        "highlight_detection_result",
    ]
    url: str | None = None
    email_to: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    mailto_link: str | None = None
    event_id: str | None = None
    event_summary: str | None = None
    event_start: str | None = None
    event_end: str | None = None
    event_description: str | None = None
    event_location: str | None = None
    event_attendees: list[str] | None = None
    report_topic: str | None = None
    report_sections: list[dict[str, str]] | None = None
    report_sources: list[str] | None = None
    content_topic: str | None = None
    content_format: str | None = None
    content_platform: str | None = None
    content_body: str | None = None
    content_sources: list[str] | None = None
    subtitle_file_path: str | None = None
    subtitle_content: str | None = None
    upload_purpose: str | None = None
    silence_output_path: str | None = None
    silence_original_duration: float | None = None
    silence_new_duration: float | None = None
    silence_removed_seconds: float | None = None
    silence_segment_count: int | None = None
    highlight_clips: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str | None = None
    tools_used: list[ToolResult] = Field(default_factory=list)
    action: ClientAction | None = None
    error: str | None = None
    image_url: str | None = None
    language: str = "en"


class TranscribeResponse(BaseModel):
    text: str


class UploadResponse(BaseModel):
    file_path: str
    file_name: str


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


class CalendarEventPayload(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    start: str
    end: str
    description: str = Field(default="")
    location: str = Field(default="")
    attendees: list[str] = Field(default_factory=list)
    time_zone: str | None = None


class CalendarEventResponse(BaseModel):
    ok: bool
    event_id: str | None = None


class DeleteEventResponse(BaseModel):
    ok: bool


class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool
    due_at: str | None = None
    priority: str = "medium"
    created_at: str


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]

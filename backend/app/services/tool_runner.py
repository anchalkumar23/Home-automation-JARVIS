from __future__ import annotations

from typing import Any

from app.ai.tools import TOOL_REGISTRY
from app.schemas import ClientAction, ToolResult
from app.services.memory import MemoryStore


class ToolRunner:
    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    def run(self, name: str, arguments: dict[str, Any], user_id: str) -> ToolResult:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            return ToolResult(name=name, arguments=arguments, ok=False, error=f"Tool '{name}' is not allowed.")

        try:
            result = tool(arguments, user_id, self.memory_store)
            return ToolResult(name=name, arguments=arguments, result=result, ok=True)
        except Exception as exc:
            return ToolResult(name=name, arguments=arguments, ok=False, error=str(exc))

    @staticmethod
    def extract_action(tool_results: list[ToolResult]) -> ClientAction | None:
        """Extract the first client action from tool results."""
        for tool_result in tool_results:
            if not tool_result.ok or not isinstance(tool_result.result, dict):
                continue
            action = tool_result.result.get("action")
            if not isinstance(action, dict):
                continue
            action_type = action.get("type")
            if action_type == "open_url" and action.get("url"):
                return ClientAction(type="open_url", url=str(action["url"]))
            if action_type == "compose_email":
                return ClientAction(
                    type="compose_email",
                    email_to=action.get("email_to") or "",
                    email_subject=action.get("email_subject") or "",
                    email_body=action.get("email_body") or "",
                    mailto_link=action.get("mailto_link") or "",
                )
            if action_type == "calendar_event_draft":
                return ClientAction(
                    type="calendar_event_draft",
                    event_id=action.get("event_id"),
                    event_summary=action.get("event_summary") or "",
                    event_start=action.get("event_start") or "",
                    event_end=action.get("event_end") or "",
                    event_description=action.get("event_description") or "",
                    event_location=action.get("event_location") or "",
                    event_attendees=action.get("event_attendees") or [],
                )
            if action_type == "calendar_event_delete_confirm":
                return ClientAction(
                    type="calendar_event_delete_confirm",
                    event_id=action.get("event_id") or "",
                    event_summary=action.get("event_summary") or "",
                    event_start=action.get("event_start") or "",
                )
            if action_type == "business_report":
                return ClientAction(
                    type="business_report",
                    report_topic=action.get("report_topic") or "",
                    report_sections=action.get("report_sections") or [],
                    report_sources=action.get("report_sources") or [],
                )
            if action_type == "content_draft":
                return ClientAction(
                    type="content_draft",
                    content_topic=action.get("content_topic") or "",
                    content_format=action.get("content_format") or "",
                    content_platform=action.get("content_platform"),
                    content_body=action.get("content_body") or "",
                    content_sources=action.get("content_sources") or [],
                )
            if action_type == "subtitle_result":
                return ClientAction(
                    type="subtitle_result",
                    subtitle_file_path=action.get("subtitle_file_path") or "",
                    subtitle_content=action.get("subtitle_content") or "",
                )
            if action_type == "file_upload_request":
                return ClientAction(
                    type="file_upload_request",
                    upload_purpose=action.get("upload_purpose") or "",
                )
            if action_type == "silence_removal_result":
                return ClientAction(
                    type="silence_removal_result",
                    silence_output_path=action.get("silence_output_path") or "",
                    silence_original_duration=action.get("silence_original_duration"),
                    silence_new_duration=action.get("silence_new_duration"),
                    silence_removed_seconds=action.get("silence_removed_seconds"),
                    silence_segment_count=action.get("silence_segment_count"),
                )
            if action_type == "highlight_detection_result":
                return ClientAction(
                    type="highlight_detection_result",
                    highlight_clips=action.get("highlight_clips") or [],
                )
        return None

    @staticmethod
    def extract_image_url(tool_results: list[ToolResult]) -> str | None:
        """Extract an image URL from generate_image tool results."""
        for tool_result in tool_results:
            if not tool_result.ok or not isinstance(tool_result.result, dict):
                continue
            image_url = tool_result.result.get("image_url")
            if image_url and isinstance(image_url, str):
                return image_url
        return None

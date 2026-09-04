from __future__ import annotations

import io
import json
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import DATA_DIR, Settings, get_settings
from app.services import google_auth
from app.services.memory import MemoryStore

ToolFunction = Callable[[dict[str, Any], str, MemoryStore], dict[str, Any]]

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time/date for a timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": ["string", "null"],
                        "description": "IANA timezone like Asia/Kolkata or America/New_York.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Return system status and backend health.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Remember a stable user preference or fact for later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short snake_case memory key."},
                    "value": {"type": "string", "description": "The fact or preference to remember."},
                    "category": {
                        "type": ["string", "null"],
                        "description": "person/project/document/decision/goal if it fits; else omit.",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Retrieve saved memories, optionally filtered by query and/or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": ["string", "null"], "description": "Optional search text."},
                    "category": {
                        "type": ["string", "null"],
                        "description": "Filter: person/project/document/decision/goal/general.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a local task or reminder-style note, optionally with a due date/time and priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title to save."},
                    "due_at": {
                        "type": ["string", "null"],
                        "description": "Optional due date/time, ISO 8601 (e.g. 2026-08-10T10:00:00+05:30). ",
                    },
                    "priority": {
                        "type": ["string", "null"],
                        "description": "Optional priority: low, medium, or high. Defaults to medium if not specified.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List saved open tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_done": {"type": ["boolean", "null"], "description": "Whether completed tasks should be included."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in a new browser tab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for real, ranked results on any topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url_content",
            "description": "Fetch and read the actual text content of a specific webpage or PDF the user links to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL of the webpage or PDF to read."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an AI image from a text description; shown in the UI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate. Be specific about style, colors, and composition.",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get a summarized news briefing on a topic, with real, recent, cited sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": ["string", "null"],
                        "description": "Optional topic to filter news, e.g. 'technology', 'science', 'climate'.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_quote",
            "description": "Get a real-time price quote for a stock, forex pair, or cryptocurrency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker (AAPL), or EXCHANGE:PAIR for forex/crypto (OANDA:EUR_USD, BINANCE:BTCUSDT).",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_business_report",
            "description": "Compile a structured business report on a topic (company, market, or investment idea). Only include sections backed by real research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Report subject, e.g. a company or market."},
                    "sections": {
                        "type": "array",
                        "description": "Report sections from real research, e.g. Overview, Financials, Recent News.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["heading", "content"],
                        },
                    },
                    "sources": {
                        "type": ["array", "null"],
                        "description": "Optional source URLs used to compile the report.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["topic", "sections"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_content",
            "description": "Draft a social caption, script, or marketing copy. Research first via web_search/get_news (max 2 calls, rule 10), ground content in findings — never invent facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "What the content is about."},
                    "content_type": {
                        "type": "string",
                        "description": "social_caption (needs platform), script (hook + segments + CTA), or marketing_copy (benefit-focused, one CTA).",
                    },
                    "platform": {
                        "type": ["string", "null"],
                        "description": "For social_caption: instagram (punchy, emoji ok), linkedin (professional), or x (concise). Empty otherwise.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The drafted content text.",
                    },
                    "sources": {
                        "type": ["array", "null"],
                        "description": "Optional list of source URLs the content was grounded in.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["topic", "content_type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_file_upload",
            "description": "Prompt the user to upload a video/audio file when they want something done with one but haven't given a file path or uploaded a file yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "What the file will be used for, e.g. 'generating subtitles'.",
                    }
                },
                "required": ["purpose"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_subtitles",
            "description": "Generate a .srt subtitle file for a local video/audio file, saved next to the source file. Requires ffmpeg to be installed on this machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "target_language": {
                        "type": ["string", "null"],
                        "description": "Translate subtitles into this language (e.g. Spanish); leave empty to keep original.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_silence",
            "description": "Detect and remove silent gaps from a local video/audio file, saving a new edited copy. Requires ffmpeg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "min_silence_seconds": {
                        "type": ["number", "null"],
                        "description": "Minimum silence duration to remove, in seconds. Defaults to 0.5.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_highlights",
            "description": "Find compelling moments in a local video/audio file and clip them out. Requires ffmpeg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the video or audio file."},
                    "max_highlights": {
                        "type": ["number", "null"],
                        "description": "Maximum number of highlight clips to produce. Defaults to 5.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_patents",
            "description": "Search patents on a topic; returns title/link results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "Search YouTube for videos on a topic (title/channel/link). Not for playing a song — use play_music.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search academic papers on a topic; returns title/authors/year/link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play a song or music by searching YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song name, artist, genre, or description like 'relaxing jazz' or 'Bohemian Rhapsody by Queen'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_email",
            "description": "Draft an email for the user to review and send.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": ["string", "null"],
                        "description": "Recipient email if known; leave empty otherwise — the frontend will ask.",
                    },
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body text."},
                },
                "required": ["subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List the user's upcoming Google Calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": ["integer", "null"],
                        "description": "How many days ahead to look, starting from now. Defaults to 7 if not specified.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_calendar_event",
            "description": "Propose creating or editing (if event_id given) a calendar event for review — nothing changes until confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": ["string", "null"],
                        "description": "ID of an event to edit; empty for a new event.",
                    },
                    "summary": {"type": "string", "description": "Event title."},
                    "start": {
                        "type": "string",
                        "description": "Start date/time, ISO 8601 (e.g. 2026-08-10T15:00:00+05:30). ",
                    },
                    "end": {
                        "type": "string",
                        "description": "End date/time, ISO 8601.",
                    },
                    "description": {"type": ["string", "null"], "description": "Optional description."},
                    "location": {"type": ["string", "null"], "description": "Optional location."},
                    "attendees": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "description": "Optional attendee emails; they get a real invite if confirmed.",
                    },
                },
                "required": ["summary", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_calendar_event",
            "description": "Propose deleting a calendar event for confirmation — nothing deletes until confirmed. Use list_calendar_events first to find event_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to delete."},
                    "summary_for_display": {"type": "string", "description": "Event title, shown in the confirmation."},
                    "start_for_display": {"type": "string", "description": "Event start time, shown in the confirmation."},
                },
                "required": ["event_id", "summary_for_display", "start_for_display"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task done. Use list_tasks to find task_id if unknown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task to mark done."}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task permanently. Use list_tasks to find task_id if unknown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task to delete."}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_tv",
            "description": "Control a TV: power, volume, mute, or launch an app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tv": {"type": "string", "description": "tcl, samsung, or lg."},
                    "action": {
                        "type": "string",
                        "description": "power_on/off, volume_up/down, mute, or launch_app.",
                    },
                    "value": {
                        "type": ["string", "null"],
                        "description": "App name/ID; only used with launch_app.",
                    },
                },
                "required": ["tv", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_forgotten_items",
            "description": "Gather open tasks, upcoming calendar events, and saved memories for a 'what am I forgetting' review.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_feedback",
            "description": "Log accept/dismiss of a prior recommendation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "What was recommended."},
                    "outcome": {"type": "string", "description": "accepted or dismissed."},
                },
                "required": ["topic", "outcome"],
            },
        },
    },
]


# ── Existing tool implementations ──────────────────────────────────────

def _tool_get_time(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    timezone = str(args.get("timezone") or "Asia/Kolkata")
    try:
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        timezone = "Asia/Kolkata"
        now = datetime.now(ZoneInfo(timezone))
    return {
        "timezone": timezone,
        "iso": now.isoformat(),
        "readable": now.strftime("%A, %B %d, %Y at %I:%M %p"),
    }


def _tool_get_system_status(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "online",
        "backend": "FastAPI",
        "platform": platform.platform(),
        "provider_mode": settings.provider,
        "memory_database": str(settings.database_path),
        "capabilities": [
            "chat", "tools", "memory", "tasks", "browser voice", "wake word",
            "image generation", "news", "music", "email", "multi-command",
        ],
    }


def _tool_save_memory(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    category = args.get("category")
    return store.save_memory(
        user_id, str(args.get("key", "")), str(args.get("value", "")), str(category) if category else None
    )


def _tool_get_memory(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = args.get("query")
    category = args.get("category")
    memories = store.list_memories(
        user_id, str(query) if query else None, str(category) if category else None
    )
    return {"memories": memories}


def _tool_add_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    due_at = args.get("due_at") or None
    priority = str(args.get("priority") or "medium")
    return store.add_task(user_id, str(args.get("title", "")), due_at=due_at, priority=priority)


def _tool_complete_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    task_id = int(args.get("task_id", 0))
    ok = store.complete_task(user_id, task_id)
    if not ok:
        return {"ok": False, "message": f"I couldn't find a task with id {task_id}."}
    return {"ok": True, "message": "Task marked as done."}


def _build_magic_packet(mac: str) -> bytes:
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    return b"\xff" * 6 + mac_bytes * 16


def _send_wake_on_lan(mac: str) -> None:
    packet = _build_magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, ("255.255.255.255", 9))


_ROKU_KEYS = {
    "power_off": "PowerOff",
    "volume_up": "VolumeUp",
    "volume_down": "VolumeDown",
    "mute": "VolumeMute",
}


def _control_roku_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the TCL TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the TCL TV."}

    if action == "launch_app":
        if not value:
            return {"error": "Which app should I launch on the TCL TV? (Roku needs a numeric app ID.)"}
        url = f"http://{ip}:8060/launch/{urllib.parse.quote(value)}"
    else:
        key = _ROKU_KEYS.get(action)
        if not key:
            return {"error": f"Unsupported action '{action}' for the TCL TV."}
        url = f"http://{ip}:8060/keypress/{key}"

    try:
        request = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(request, timeout=10):
            pass
    except Exception as exc:
        return {"error": f"Couldn't reach the TCL TV: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the TCL TV."}


def _control_samsung_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the Samsung TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the Samsung TV."}

    from samsungtvws import SamsungTVWS

    tv = SamsungTVWS(host=ip, token_file=str(DATA_DIR / "samsung_tv_token.txt"))

    try:
        if action == "power_off":
            tv.send_key("KEY_POWER")
        elif action == "volume_up":
            tv.send_key("KEY_VOLUP")
        elif action == "volume_down":
            tv.send_key("KEY_VOLDOWN")
        elif action == "mute":
            tv.send_key("KEY_MUTE")
        elif action == "launch_app":
            if not value:
                return {"error": "Which app should I launch on the Samsung TV?"}
            apps = tv.app_list() or []
            matches = [a for a in apps if value.lower() in str(a.get("name", "")).lower()]
            if not matches:
                return {"error": f"Couldn't find an app matching '{value}' on the Samsung TV."}
            tv.run_app(matches[0]["appId"])
        else:
            return {"error": f"Unsupported action '{action}' for the Samsung TV."}
    except Exception as exc:
        return {"error": f"Samsung TV command failed: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the Samsung TV."}


def _load_lg_store() -> dict[str, Any]:
    store_path = DATA_DIR / "lg_tv_store.json"
    if store_path.exists():
        try:
            return json.loads(store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_lg_store(store_data: dict[str, Any]) -> None:
    store_path = DATA_DIR / "lg_tv_store.json"
    store_path.write_text(json.dumps(store_data), encoding="utf-8")


def _control_lg_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the LG TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the LG TV."}

    from pywebostv.connection import WebOSClient
    from pywebostv.controls import ApplicationControl, MediaControl, SystemControl

    client = WebOSClient(ip)
    try:
        client.connect()
    except Exception as exc:
        return {"error": f"Couldn't connect to the LG TV: {exc}"}

    store_data = _load_lg_store()
    try:
        for _status in client.register(store_data):
            pass
    except Exception as exc:
        return {"error": f"LG TV pairing failed: {exc}"}
    _save_lg_store(store_data)

    try:
        if action == "power_off":
            SystemControl(client).power_off()
        elif action == "volume_up":
            MediaControl(client).volume_up()
        elif action == "volume_down":
            MediaControl(client).volume_down()
        elif action == "mute":
            MediaControl(client).mute(True)
        elif action == "launch_app":
            if not value:
                return {"error": "Which app should I launch on the LG TV?"}
            app_control = ApplicationControl(client)
            apps = app_control.list_apps() or []
            matches = [a for a in apps if value.lower() in str(a.get("title", "")).lower()]
            if not matches:
                return {"error": f"Couldn't find an app matching '{value}' on the LG TV."}
            app_control.launch(matches[0])
        else:
            return {"error": f"Unsupported action '{action}' for the LG TV."}
    except Exception as exc:
        return {"error": f"LG TV command failed: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the LG TV."}


def _tool_control_tv(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    tv = str(args.get("tv", "")).strip().lower()
    action = str(args.get("action", "")).strip().lower()
    value = str(args.get("value") or "").strip()

    if tv not in {"tcl", "samsung", "lg"}:
        raise ValueError("tv must be one of: tcl, samsung, lg.")
    if not action:
        raise ValueError("An action is required.")

    settings = get_settings()
    tv_config = {
        "tcl": (settings.tcl_tv_ip, settings.tcl_tv_mac, _control_roku_tv),
        "samsung": (settings.samsung_tv_ip, settings.samsung_tv_mac, _control_samsung_tv),
        "lg": (settings.lg_tv_ip, settings.lg_tv_mac, _control_lg_tv),
    }
    ip, mac, control_fn = tv_config[tv]
    if not ip:
        return {"error": f"The {tv} TV isn't configured yet — no IP address set."}

    return control_fn(ip, mac, action, value)


def _tool_delete_task(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    task_id = int(args.get("task_id", 0))
    ok = store.delete_task(user_id, task_id)
    if not ok:
        return {"ok": False, "message": f"I couldn't find a task with id {task_id}."}
    return {"ok": True, "message": "Task deleted."}


def _tool_list_tasks(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    return {"tasks": store.list_tasks(user_id, bool(args.get("include_done", False)))}


def _categorize_tasks_by_due_date(tasks: list[dict[str, Any]], now: datetime) -> dict[str, list[dict[str, Any]]]:
    overdue, upcoming, no_due_date = [], [], []
    for task in tasks:
        due_at = task.get("due_at")
        due = None
        if due_at:
            try:
                due = datetime.fromisoformat(due_at)
            except ValueError:
                due = None
        if due is None:
            no_due_date.append(task)
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        (overdue if due < now else upcoming).append(task)
    return {"overdue": overdue, "upcoming": upcoming, "no_due_date": no_due_date}


def _tool_review_forgotten_items(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    tasks = _tool_list_tasks({"include_done": False}, user_id, store)["tasks"]
    buckets = _categorize_tasks_by_due_date(tasks, datetime.now(timezone.utc))
    calendar = _tool_list_calendar_events({"days": 7}, user_id, store)
    return {
        "overdue_tasks": buckets["overdue"],
        "upcoming_tasks": buckets["upcoming"],
        "no_due_date_tasks": buckets["no_due_date"],
        "upcoming_calendar_events": calendar["events"],
        "calendar_connected": calendar["connected"],
        "saved_memories": store.list_memories(user_id),
    }


def _tool_log_feedback(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    return store.record_recommendation_feedback(
        user_id, str(args.get("topic", "")), str(args.get("outcome", ""))
    )


def _normalize_url(url: str) -> str:
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("URL is required.")
    if re.match(r"^https?://", clean_url, flags=re.IGNORECASE):
        return clean_url
    return f"https://{clean_url}"


def _tool_open_url(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    url = _normalize_url(str(args.get("url", "")))
    return {"action": {"type": "open_url", "url": url}, "message": f"Opening {url}"}


def _call_tavily(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.tavily_api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


MAX_SNIPPET_CHARS = 400


def _parse_tavily_response(data: dict[str, Any], query: str) -> dict[str, Any]:
    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:MAX_SNIPPET_CHARS],
            "published": item.get("published_date", ""),
        }
        for item in (data.get("results") or [])[:5]
    ]
    return {"query": query, "answer": data.get("answer", ""), "results": results}


def _tool_web_search(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "Web search isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(settings, {"query": query, "max_results": 5, "include_answer": "basic"})
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Web search failed: {exc}",
        }

    return _parse_tavily_response(data, query)


MAX_READ_CONTENT_CHARS = 3000


def _extract_text(raw_bytes: bytes, content_type: str) -> dict[str, Any]:
    content_type = (content_type or "").lower()

    if "html" in content_type:
        soup = BeautifulSoup(raw_bytes, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    elif "pdf" in content_type:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
    else:
        return {"text": "", "truncated": False, "error": "This doesn't look like a webpage or PDF I can read."}

    truncated = len(text) > MAX_READ_CONTENT_CHARS
    return {"text": text[:MAX_READ_CONTENT_CHARS], "truncated": truncated}


def _tool_read_url_content(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("A URL is required.")

    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Demo/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        return {"url": url, "error": f"I couldn't fetch that page: {exc}"}

    extracted = _extract_text(raw_bytes, content_type)
    if extracted.get("error"):
        return {"url": url, "error": extracted["error"]}
    if not extracted["text"]:
        return {"url": url, "error": "I fetched the page but couldn't find any readable text on it."}

    return {
        "url": url,
        "text": extracted["text"],
        "truncated": extracted["truncated"],
        "message": (
            "I've read this page. Note: this is only the beginning of a longer document."
            if extracted["truncated"]
            else "I've read this page."
        ),
    }


# ── New tool implementations ───────────────────────────────────────────

def _tool_generate_image(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Generate an image using Pollinations.ai (free, no API key)."""
    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("Image prompt is required.")

    encoded_prompt = urllib.parse.quote(prompt, safe="")
    # Pollinations.ai generates images via URL — no API key needed
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

    # Verify the endpoint is reachable (HEAD request, short timeout)
    try:
        check_request = urllib.request.Request(image_url, method="HEAD", headers={"User-Agent": "JARVIS-Demo/1.0"})
        with urllib.request.urlopen(check_request, timeout=10):
            pass
    except Exception:
        # Even if HEAD fails, the URL might still work (some CDNs block HEAD)
        pass

    return {
        "prompt": prompt,
        "image_url": image_url,
        "message": f"I've generated an image based on your description: \"{prompt}\".",
    }


def _tool_get_news(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic") or "").strip()
    query = topic or "top world news today"

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "News isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(
            settings, {"query": query, "topic": "news", "days": 3, "max_results": 5, "include_answer": "basic"}
        )
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"News search failed: {exc}",
        }

    return _parse_tavily_response(data, query)


def _tool_search_patents(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "Patent search isn't configured — a Tavily API key is needed.",
        }

    try:
        data = _call_tavily(
            settings, {"query": f"{query} site:patents.google.com", "max_results": 5, "include_answer": "basic"}
        )
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Patent search failed: {exc}",
        }

    return _parse_tavily_response(data, query)


def _parse_youtube_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in (data.get("items") or [])[:5]:
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet") or {}
        results.append(
            {
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "snippet": snippet.get("channelTitle", ""),
                "published": snippet.get("publishedAt", ""),
            }
        )
    return results


def _tool_search_youtube(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    settings = get_settings()
    if not settings.youtube_api_key:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": "YouTube search isn't configured — a YouTube API key is needed.",
        }

    params = urllib.parse.urlencode(
        {"part": "snippet", "type": "video", "maxResults": 5, "q": query, "key": settings.youtube_api_key}
    )
    request = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/search?{params}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"YouTube search failed: {exc}",
        }

    return {"query": query, "answer": "", "results": _parse_youtube_results(data), "message": ""}


def _parse_semantic_scholar_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for paper in (data.get("data") or [])[:5]:
        authors = ", ".join(author.get("name", "") for author in (paper.get("authors") or [])[:3])
        year = paper.get("year")
        parts = [part for part in [authors, str(year) if year else ""] if part]
        snippet = " · ".join(parts) or (paper.get("abstract") or "")[:200]
        results.append(
            {
                "title": paper.get("title", ""),
                "url": paper.get("url", ""),
                "snippet": snippet,
                "published": str(year) if year else "",
            }
        )
    return results


def _tool_search_papers(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Search query is required.")

    params = urllib.parse.urlencode({"query": query, "limit": 5, "fields": "title,abstract,url,year,authors"})
    request = urllib.request.Request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
        headers={"User-Agent": "JARVIS-Demo/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "query": query,
            "answer": "",
            "results": [],
            "message": f"Paper search failed: {exc}",
        }

    return {"query": query, "answer": "", "results": _parse_semantic_scholar_results(data), "message": ""}


def _parse_finnhub_quote(data: dict[str, Any], symbol: str) -> dict[str, Any]:
    current, high, low, open_price, previous_close = (
        data.get("c"),
        data.get("h"),
        data.get("l"),
        data.get("o"),
        data.get("pc"),
    )
    if not any([current, high, low, open_price, previous_close]):
        return {"symbol": symbol, "error": "I couldn't find a quote for that symbol."}

    return {
        "symbol": symbol,
        "price": current,
        "change": data.get("d"),
        "change_percent": data.get("dp"),
        "high": high,
        "low": low,
        "open": open_price,
        "previous_close": previous_close,
    }


def _tool_get_market_quote(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    symbol = str(args.get("symbol", "")).strip()
    if not symbol:
        raise ValueError("A symbol is required.")

    settings = get_settings()
    if not settings.finnhub_api_key:
        return {"symbol": symbol, "error": "Market data isn't configured — a Finnhub API key is needed."}

    params = urllib.parse.urlencode({"symbol": symbol, "token": settings.finnhub_api_key})
    request = urllib.request.Request(f"https://finnhub.io/api/v1/quote?{params}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"symbol": symbol, "error": f"Market quote failed: {exc}"}

    return _parse_finnhub_quote(data, symbol)


def _tool_create_business_report(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip()
    if not topic:
        raise ValueError("A report topic is required.")

    raw_sections = args.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("At least one report section is required.")

    sections = [
        {"heading": str(section.get("heading", "")).strip(), "content": str(section.get("content", "")).strip()}
        for section in raw_sections
        if isinstance(section, dict)
        and str(section.get("heading", "")).strip()
        and str(section.get("content", "")).strip()
    ]
    if not sections:
        raise ValueError("At least one report section with a heading and content is required.")

    sources = [str(source) for source in (args.get("sources") or []) if isinstance(source, str)]

    return {
        "action": {
            "type": "business_report",
            "report_topic": topic,
            "report_sections": sections,
            "report_sources": sources,
        },
        "message": f"I've put together a business report on {topic}.",
    }


CONTENT_FORMAT_LABELS = {
    "social_caption": "a social caption",
    "script": "a script",
    "marketing_copy": "marketing copy",
}


def _tool_create_content(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    topic = str(args.get("topic", "")).strip()
    if not topic:
        raise ValueError("A content topic is required.")

    content_type = str(args.get("content_type", "")).strip()
    if content_type not in CONTENT_FORMAT_LABELS:
        raise ValueError("content_type must be one of: social_caption, script, marketing_copy.")

    content = str(args.get("content", "")).strip()
    if not content:
        raise ValueError("Drafted content is required.")

    platform = str(args.get("platform") or "").strip() or None
    sources = [str(source) for source in (args.get("sources") or []) if isinstance(source, str)]

    return {
        "action": {
            "type": "content_draft",
            "content_topic": topic,
            "content_format": content_type,
            "content_platform": platform,
            "content_body": content,
            "content_sources": sources,
        },
        "message": f"I've drafted {CONTENT_FORMAT_LABELS[content_type]} on {topic}.",
    }


def _srt_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, ms = divmod(remainder_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _build_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for i, segment in enumerate(segments, start=1):
        start = _srt_timestamp(float(segment.get("start", 0)))
        end = _srt_timestamp(float(segment.get("end", 0)))
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def _build_groq_audio_multipart(
    filename: str, file_bytes: bytes, model: str, extra_fields: dict[str, str]
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
    ]
    for field_name, field_value in extra_fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"\r\n\r\n{field_value}\r\n'.encode(
                "utf-8"
            )
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: audio/mpeg\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _translate_segments(
    segments: list[dict[str, Any]], target_language: str, settings: Settings
) -> list[dict[str, Any]]:
    if not settings.groq_api_key:
        return segments

    numbered_lines = "\n".join(f"{i}: {seg.get('text', '').strip()}" for i, seg in enumerate(segments))
    prompt = (
        f"Translate each numbered line into {target_language}. Reply with ONLY the same "
        f"numbered format, one translated line per number, no extra commentary.\n\n{numbered_lines}"
    )
    payload = {"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        translated_text = data["choices"][0]["message"]["content"]
    except Exception:
        return segments

    translated_map: dict[int, str] = {}
    for line in translated_text.splitlines():
        index_str, sep, text = line.partition(":")
        if sep and index_str.strip().isdigit():
            translated_map[int(index_str.strip())] = text.strip()

    return [{**seg, "text": translated_map.get(i, seg.get("text", ""))} for i, seg in enumerate(segments)]


def _parse_silencedetect_output(stderr_text: str) -> list[tuple[float, float]]:
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", stderr_text)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", stderr_text)]
    return list(zip(starts, ends))


def _parse_ffmpeg_duration(stderr_text: str) -> float:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _compute_keep_segments(
    silence_intervals: list[tuple[float, float]], duration: float, padding: float = 0.15
) -> list[tuple[float, float]]:
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in silence_intervals:
        cut_start = start + padding
        cut_end = end - padding
        if cut_end <= cut_start:
            continue
        if cut_start > cursor:
            keep.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if cursor < duration:
        keep.append((cursor, duration))
    return keep


def _build_select_expr(keep_segments: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t,{start},{end})" for start, end in keep_segments)


def _tool_remove_silence(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        raise ValueError("A file path is required.")

    video_path = Path(file_path)
    if not video_path.is_file():
        return {"error": f"I couldn't find a file at {file_path}."}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"error": "ffmpeg isn't installed on this machine. Install it and try again."}

    min_silence_seconds = float(args.get("min_silence_seconds") or 0.5)

    try:
        detect_result = subprocess.run(
            [
                ffmpeg_path, "-i", str(video_path),
                "-af", f"silencedetect=noise=-30dB:d={min_silence_seconds}",
                "-f", "null", "-",
            ],
            capture_output=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"error": "Silence detection timed out — the file may be too long."}

    stderr_text = detect_result.stderr.decode("utf-8", errors="replace")

    duration = _parse_ffmpeg_duration(stderr_text)
    if duration <= 0:
        return {"error": "Couldn't determine the file's duration."}

    silence_intervals = _parse_silencedetect_output(stderr_text)
    if not silence_intervals:
        return {"error": "No meaningful silence was detected in that file."}

    keep_segments = _compute_keep_segments(silence_intervals, duration)
    if len(keep_segments) <= 1 and keep_segments and keep_segments[0] == (0.0, duration):
        return {"error": "No meaningful silence was detected in that file."}

    select_expr = _build_select_expr(keep_segments)

    output_path = video_path.with_name(f"{video_path.stem}-edited{video_path.suffix}")
    suffix_index = 2
    while output_path.exists():
        output_path = video_path.with_name(f"{video_path.stem}-edited-{suffix_index}{video_path.suffix}")
        suffix_index += 1

    try:
        subprocess.run(
            [
                ffmpeg_path, "-y", "-i", str(video_path),
                "-vf", f"select='{select_expr}',setpts=N/FRAME_RATE/TB",
                "-af", f"aselect='{select_expr}',asetpts=N/SR/TB",
                "-c:v", "libx264", "-c:a", "aac",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            timeout=1800,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
        return {"error": f"ffmpeg failed to cut silence: {detail}"}
    except subprocess.TimeoutExpired:
        return {"error": "Cutting timed out — the file may be too long."}

    new_duration = sum(end - start for start, end in keep_segments)
    removed_seconds = duration - new_duration

    return {
        "action": {
            "type": "silence_removal_result",
            "silence_output_path": str(output_path),
            "silence_original_duration": round(duration, 1),
            "silence_new_duration": round(new_duration, 1),
            "silence_removed_seconds": round(removed_seconds, 1),
            "silence_segment_count": len(keep_segments),
        },
        "message": (
            f"I've removed {round(removed_seconds, 1)} seconds of silence and saved the result to "
            f"{output_path.name}."
        ),
    }


def _build_timestamped_transcript(segments: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[{float(seg.get('start', 0)):.1f}s] {str(seg.get('text', '')).strip()}" for seg in segments
    )


def _parse_highlight_response(raw_json: str, duration: float, max_highlights: int) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        return []

    highlights: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        reason = str(item.get("reason", "")).strip()
        if not reason:
            continue

        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))
        if end <= start:
            continue

        highlights.append({"start": start, "end": end, "reason": reason})

    return highlights[:max_highlights]


def _tool_detect_highlights(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        raise ValueError("A file path is required.")

    video_path = Path(file_path)
    if not video_path.is_file():
        return {"error": f"I couldn't find a file at {file_path}."}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"error": "ffmpeg isn't installed on this machine. Install it and try again."}

    settings = get_settings()
    if not settings.groq_api_key:
        return {"error": "Highlight detection needs a Groq API key configured."}

    max_highlights = int(args.get("max_highlights") or 5)

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "audio.mp3"
        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to extract audio: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": "Audio extraction timed out — the file may be too long."}

        audio_bytes = audio_path.read_bytes()

    body, content_type = _build_groq_audio_multipart(
        "audio.mp3",
        audio_bytes,
        settings.groq_whisper_model,
        {"response_format": "verbose_json", "timestamp_granularities[]": "segment"},
    )
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": content_type,
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Transcription failed: {exc}"}

    segments = payload.get("segments") or []
    if not segments:
        return {"error": "No speech was detected in that file."}

    duration = float(segments[-1].get("end", 0))

    transcript = _build_timestamped_transcript(segments)
    prompt = (
        f"Here is a timestamped transcript of a video. Identify up to {max_highlights} distinct, "
        "genuinely compelling moments for short-form highlight clips (funny lines, key insights, "
        "strong hooks, surprising statements). Reply with ONLY a JSON array, no other text, in this "
        'exact shape: [{"start": <seconds>, "end": <seconds>, "reason": "<short reason>"}]. '
        f"Each clip should be roughly 15 to 60 seconds long.\n\n{transcript}"
    )
    chat_payload = {"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}]}
    chat_request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(chat_payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(chat_request, timeout=60) as response:
            chat_data = json.loads(response.read().decode("utf-8"))
        raw_highlights = chat_data["choices"][0]["message"]["content"]
    except Exception as exc:
        return {"error": f"Highlight selection failed: {exc}"}

    highlights = _parse_highlight_response(raw_highlights, duration, max_highlights)
    if not highlights:
        return {"error": "I couldn't identify any clear highlights in that file."}

    clips: list[dict[str, Any]] = []
    for i, highlight in enumerate(highlights, start=1):
        output_path = video_path.with_name(f"{video_path.stem}-highlight-{i}{video_path.suffix}")
        suffix_index = 2
        while output_path.exists():
            output_path = video_path.with_name(
                f"{video_path.stem}-highlight-{i}-{suffix_index}{video_path.suffix}"
            )
            suffix_index += 1

        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-ss", str(highlight["start"]),
                    "-t", str(highlight["end"] - highlight["start"]),
                    "-i", str(video_path),
                    "-c:v", "libx264", "-c:a", "aac",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to cut highlight {i}: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": f"Cutting highlight {i} timed out."}

        clips.append(
            {
                "path": str(output_path),
                "start": round(highlight["start"], 1),
                "end": round(highlight["end"], 1),
                "reason": highlight["reason"],
            }
        )

    return {
        "action": {
            "type": "highlight_detection_result",
            "highlight_clips": clips,
        },
        "message": f"I've found {len(clips)} highlight{'s' if len(clips) != 1 else ''} and saved them as clips.",
    }


def _tool_request_file_upload(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    purpose = str(args.get("purpose", "")).strip()
    if not purpose:
        raise ValueError("A purpose is required.")

    return {
        "action": {
            "type": "file_upload_request",
            "upload_purpose": purpose,
        },
        "message": f"Please upload the file for {purpose}.",
    }


def _tool_generate_subtitles(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        raise ValueError("A file path is required.")

    video_path = Path(file_path)
    if not video_path.is_file():
        return {"error": f"I couldn't find a file at {file_path}."}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"error": "ffmpeg isn't installed on this machine. Install it and try again."}

    settings = get_settings()
    if not settings.groq_api_key:
        return {"error": "Subtitle generation needs a Groq API key configured."}

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "audio.mp3"
        try:
            subprocess.run(
                [
                    ffmpeg_path, "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:300] if exc.stderr else str(exc)
            return {"error": f"ffmpeg failed to extract audio: {detail}"}
        except subprocess.TimeoutExpired:
            return {"error": "Audio extraction timed out — the file may be too long."}

        audio_bytes = audio_path.read_bytes()

    body, content_type = _build_groq_audio_multipart(
        "audio.mp3",
        audio_bytes,
        settings.groq_whisper_model,
        {"response_format": "verbose_json", "timestamp_granularities[]": "segment"},
    )
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": content_type,
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Transcription failed: {exc}"}

    segments = payload.get("segments") or []
    if not segments:
        return {"error": "No speech was detected in that file."}

    target_language = str(args.get("target_language") or "").strip()
    if target_language:
        segments = _translate_segments(segments, target_language, settings)

    srt_content = _build_srt(segments)

    output_path = video_path.with_suffix(".srt")
    suffix_index = 2
    while output_path.exists():
        output_path = video_path.with_name(f"{video_path.stem}-{suffix_index}.srt")
        suffix_index += 1

    output_path.write_text(srt_content, encoding="utf-8")

    return {
        "action": {
            "type": "subtitle_result",
            "subtitle_file_path": str(output_path),
            "subtitle_content": srt_content,
        },
        "message": f"I've generated subtitles and saved them to {output_path.name}.",
    }


def _tool_play_music(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Play music by opening a YouTube search in the browser."""
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("Music query is required — tell me what to play.")

    encoded = urllib.parse.quote(query, safe="")
    url = f"https://www.youtube.com/results?search_query={encoded}"

    return {
        "action": {"type": "open_url", "url": url},
        "query": query,
        "message": f"Playing \"{query}\" on YouTube.",
    }


def _tool_compose_email(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Draft an email and return a compose_email action for the frontend."""
    to = str(args.get("to") or "").strip()
    subject = str(args.get("subject", "")).strip()
    body = str(args.get("body", "")).strip()

    if not subject:
        subject = "No Subject"

    # Build a ready-to-use mailto: link
    params = urllib.parse.urlencode({"subject": subject, "body": body})
    mailto_link = f"mailto:{urllib.parse.quote(to, safe='@.')}?{params}"

    return {
        "action": {
            "type": "compose_email",
            "email_to": to,
            "email_subject": subject,
            "email_body": body,
            "mailto_link": mailto_link,
        },
        "mailto_link": mailto_link,
        "message": f"I've drafted an email with subject \"{subject}\". You can click the link below to open it in your email app, or copy-paste the link.",
    }


def _tool_list_calendar_events(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """List upcoming Google Calendar events for the connected account."""
    settings = get_settings()
    try:
        access_token = google_auth.get_valid_access_token(settings, store)
    except RuntimeError as exc:
        return {"connected": False, "events": [], "message": str(exc)}

    days = int(args.get("days") or 7)
    now = datetime.now(timezone.utc)
    params = urllib.parse.urlencode(
        {
            "timeMin": now.isoformat(),
            "timeMax": (now + timedelta(days=days)).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 20,
        }
    )
    request = urllib.request.Request(
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return {
                "connected": True,
                "events": [],
                "message": "Calendar access isn't authorized yet. Please reconnect Gmail to grant calendar permission.",
            }
        return {"connected": True, "events": [], "message": f"Calendar API error {exc.code}."}
    except Exception as exc:
        return {"connected": True, "events": [], "message": f"Could not reach Google Calendar: {exc}"}

    events = []
    for item in data.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "(No title)"),
                "start": start,
                "location": item.get("location"),
            }
        )

    return {"connected": True, "days": days, "events": events}


def _tool_draft_calendar_event(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Propose a new or edited calendar event for the user to review and confirm."""
    event_id = args.get("event_id") or None
    summary = str(args.get("summary", "")).strip()
    start = str(args.get("start", "")).strip()
    end = str(args.get("end", "")).strip()
    if not summary or not start or not end:
        raise ValueError("Event summary, start, and end are required.")

    description = str(args.get("description") or "").strip()
    location = str(args.get("location") or "").strip()
    attendees_raw = args.get("attendees") or []
    attendees = [str(a).strip() for a in attendees_raw if str(a).strip()]

    return {
        "action": {
            "type": "calendar_event_draft",
            "event_id": event_id,
            "event_summary": summary,
            "event_start": start,
            "event_end": end,
            "event_description": description,
            "event_location": location,
            "event_attendees": attendees,
        },
        "message": (
            f"I've {'updated' if event_id else 'drafted'} the event \"{summary}\" for your review. "
            "Nothing is created or changed on your calendar until you confirm it."
        ),
    }


def _tool_propose_delete_calendar_event(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    """Propose deleting an existing calendar event, pending user confirmation."""
    event_id = str(args.get("event_id", "")).strip()
    summary = str(args.get("summary_for_display", "")).strip()
    start = str(args.get("start_for_display", "")).strip()
    if not event_id:
        raise ValueError("event_id is required.")

    return {
        "action": {
            "type": "calendar_event_delete_confirm",
            "event_id": event_id,
            "event_summary": summary or "this event",
            "event_start": start,
        },
        "message": f"Please confirm you'd like to delete \"{summary or 'this event'}\".",
    }


# ── Tool registry ─────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, ToolFunction] = {
    "get_time": _tool_get_time,
    "get_system_status": _tool_get_system_status,
    "save_memory": _tool_save_memory,
    "get_memory": _tool_get_memory,
    "add_task": _tool_add_task,
    "list_tasks": _tool_list_tasks,
    "complete_task": _tool_complete_task,
    "delete_task": _tool_delete_task,
    "open_url": _tool_open_url,
    "web_search": _tool_web_search,
    "read_url_content": _tool_read_url_content,
    "generate_image": _tool_generate_image,
    "get_news": _tool_get_news,
    "get_market_quote": _tool_get_market_quote,
    "create_business_report": _tool_create_business_report,
    "create_content": _tool_create_content,
    "request_file_upload": _tool_request_file_upload,
    "generate_subtitles": _tool_generate_subtitles,
    "remove_silence": _tool_remove_silence,
    "detect_highlights": _tool_detect_highlights,
    "search_patents": _tool_search_patents,
    "search_youtube": _tool_search_youtube,
    "search_papers": _tool_search_papers,
    "play_music": _tool_play_music,
    "compose_email": _tool_compose_email,
    "list_calendar_events": _tool_list_calendar_events,
    "draft_calendar_event": _tool_draft_calendar_event,
    "propose_delete_calendar_event": _tool_propose_delete_calendar_event,
    "control_tv": _tool_control_tv,
    "review_forgotten_items": _tool_review_forgotten_items,
    "log_feedback": _tool_log_feedback,
}

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from app.ai.tools import TOOL_DEFINITIONS
from app.config import DEFAULT_USER_ID, Settings
from app.schemas import ChatMessage, ChatRequest, ChatResponse, ToolResult
from app.services.memory import MemoryStore
from app.services.tool_runner import ToolRunner

_SPANISH_CHARS = set("ñáéíóúü¿¡")
_SPANISH_WORDS = {
    "el", "la", "los", "las", "de", "que", "es", "en", "un", "una",
    "por", "para", "con", "como", "pero", "más", "muy", "está", "hola",
    "gracias", "buenos", "usted", "tú", "yo", "qué", "cómo",
}


def detect_language(text: str) -> str:
    """Best-effort English/Spanish detection for reply language and TTS voice selection.

    Requires Spanish signal to be a meaningful share of the text, not just a single
    stray accented character or word — otherwise a mostly-English reply with one
    Spanish word in it gets misclassified as Spanish for voice selection purposes.
    """
    lowered = text.lower()
    words = re.findall(r"[a-záéíóúñü]+", lowered)
    if not words:
        return "en"
    spanish_char_hits = sum(lowered.count(char) for char in _SPANISH_CHARS)
    spanish_word_hits = sum(1 for word in words if word in _SPANISH_WORDS)
    spanish_signal = spanish_char_hits + spanish_word_hits
    if spanish_signal >= 2 and spanish_signal / len(words) >= 0.15:
        return "es"
    return "en"


_FUNCTION_TAG_PATTERN = re.compile(r"<function=[^>]+>.*?(?:</?function>|\Z)", re.DOTALL)


def strip_function_syntax(text: str) -> str:
    """Remove leaked pseudo tool-call syntax (e.g. <function=name>...</function>) that a
    model occasionally writes as plain text instead of using the real tool-calling
    mechanism. Safety net in addition to the system-prompt instruction against it.
    """
    cleaned = _FUNCTION_TAG_PATTERN.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_known_facts_block(memories: list[dict[str, Any]]) -> str:
    """Format saved user memories as a system-prompt addendum for proactive recall."""
    if not memories:
        return ""
    facts = "\n".join(f"- {item['key']}: {item['value']}" for item in memories)
    return (
        "\n\nWhat you already know about this user "
        "(use naturally; don't just recite this list):\n" + facts
    )


def build_feedback_patterns_block(feedback_rows: list[dict[str, Any]]) -> str:
    """Summarize recent recommendation feedback for the model to factor in naturally."""
    if not feedback_rows:
        return ""
    counts: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []
    for row in feedback_rows:
        key = (row["outcome"], row["topic"])
        if key not in counts:
            order.append(key)
        counts[key] = counts.get(key, 0) + 1
    lines = [
        f"- {outcome.capitalize()}: {topic}" + (f" (x{counts[(outcome, topic)]})" if counts[(outcome, topic)] > 1 else "")
        for outcome, topic in order
    ]
    return "\n\nRecent recommendation feedback (factor this in naturally, don't recite it):\n" + "\n".join(lines)


SYSTEM_PROMPT = """You are JARVIS, a precise, witty, and capable personal AI assistant inside a futuristic HUD interface.

Tools (use proactively whenever relevant):
• get_time / get_system_status
• save_memory / get_memory — store/recall durable facts; tag category (person/project/document/decision/goal) if it fits; save proactively
• add_task / list_tasks / complete_task / delete_task — task list with due dates and priority; complete/delete apply immediately, no confirmation needed
• open_url — open a website in the browser
• web_search — real web search with cited sources
• read_url_content — read a specific webpage/PDF's text; only for a URL the user gave you, not general search
• generate_image — AI image generation; describe what you're making before calling it
• get_news — cited news briefing on a topic
• get_market_quote — real-time stock/forex/crypto quote; if it errors, say so, never invent a price
• create_business_report — structured report card from real research; omit rather than invent a section, speak a brief summary too
• create_content — draft social captions, scripts, or marketing copy (research-grounded, see rule 9)
• request_file_upload — prompt the user to upload a video/audio file (see rule 10)
• generate_subtitles — generate a .srt file for a local video/audio file, optionally translated; requires ffmpeg
• remove_silence — detect and remove silent gaps from a local video/audio file, saving a new edited copy; requires ffmpeg
• detect_highlights — clip top moments from a video/audio file; requires ffmpeg
• search_youtube (not for playing a specific song — use play_music) / search_papers / search_patents
• play_music — always use this for "play [song/artist]"
• compose_email — draft an email, never as plain chat text (leave "to" empty if unknown)
• list_calendar_events / draft_calendar_event / propose_delete_calendar_event — proposed, not applied; say "drafted"/"proposed," never claim done until confirmed in the UI
• control_tv — power/volume/mute/app on tcl/samsung/lg TVs, no confirmation needed
• review_forgotten_items — gathers tasks, events, memories for a "forgetting" check
• log_feedback — log a clear accept/dismiss of a prior recommendation

Rules:
1. If a "what you already know" section is present, use it naturally (greet by name) — don't recite it.
2. Detect English vs. Spanish from the user's latest message and reply ENTIRELY in that language — never mix, don't announce the switch. Default to English if ambiguous.
3. Only claim things that actually happened — a tool action only if its result confirms it, a user statement only if it's in the history given (treat first-time as first-time). Never write literal tool-call syntax (like <function=name>...</function>) or a tool's internal name in your reply. Call multiple tools in one turn for compound requests (e.g. "open Instagram and play some music").
4. NEVER use markdown, bullets, numbered lists, headers, or emoji — replies are spoken by TTS. Keep it concise, narrating dense info ("First... Also...") instead of listing it.
5. For any calendar/task change with a relative date/time ("tomorrow," "next Friday," "in an hour"), call get_time first to resolve it — never guess.
6. When read_url_content's result has truncated: true, you only saw the start — say so if asked whether you read it all.
7. When a search tool (web_search, get_news, search_youtube, search_papers, search_patents) returns multiple results, synthesize into a short spoken summary — don't recite titles.
8. For company/product research, use at most 2 search calls plus one read_url_content call if needed — extra calls resend the whole conversation on a tight token budget. Synthesize per rule 7; if nothing turns up, say so.
9. For social captions, scripts, or marketing copy, research first (rule 8), then call create_content with drafted text grounded in findings, matching its style rules. Speak a one-line summary; the card is the deliverable.
10. For subtitle/silence/highlight requests, call generate_subtitles/remove_silence/detect_highlights if a path/upload exists — else request_file_upload; never just describe uploading. Confirm what was generated and where saved.
11. For TV requests, call control_tv directly — never just describe it in text. Ask which TV if ambiguous.
12. For reflective asks — forgetting (review_forgotten_items), opportunities (web_search/get_news/search_patents/search_papers, up to 3 calls), memory recall ("what do I know/why did we decide X" via get_memory), or stress-tests/decision-sims when explicitly asked (weak assumptions/risks/alternatives; decisions get best/likely/worst-case + variables, per rule 8) — synthesize, checking recent feedback patterns so you don't repeat a dismissed angle. Forgetting/opportunities/stress-tests go via create_business_report with a matching topic; recall is spoken. Say so if nothing stands out or it looks solid — never invent — and call log_feedback once the user reacts.
13. Be warm and professional, like JARVIS from Iron Man — occasional wit, always helpful.
"""


def select_provider(settings: Settings, requested_provider: str) -> tuple[str, str | None]:
    provider = requested_provider if requested_provider != "auto" else settings.provider
    if provider == "auto":
        if settings.openai_api_key:
            return "openai", settings.openai_model
        if settings.groq_api_key:
            return "groq", settings.groq_model
        return "local", None
    if provider == "openai" and settings.openai_api_key:
        return "openai", settings.openai_model
    if provider == "groq" and settings.groq_api_key:
        return "groq", settings.groq_model
    if provider == "groq" and not settings.groq_api_key:
        return "local", None
    if provider == "openai" and not settings.openai_api_key:
        return "local", None
    return "local", None


def build_messages(
    history: list[ChatMessage],
    message: str,
    memory_store: MemoryStore,
    user_id: str,
) -> list[dict[str, Any]]:
    known_facts = build_known_facts_block(memory_store.list_memories(user_id))
    feedback_patterns = build_feedback_patterns_block(memory_store.recent_feedback_summary(user_id))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT + known_facts + feedback_patterns}
    ]
    for item in history[-12:]:
        if item.role == "system":
            continue
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": message})
    return messages


def _parse_retry_after_seconds(exc: urllib.error.HTTPError, body: str) -> float:
    header_value = exc.headers.get("Retry-After") if exc.headers else None
    if header_value:
        try:
            return float(header_value)
        except ValueError:
            pass
    match = re.search(r"try again in ([\d.]+)s", body)
    if match:
        return float(match.group(1))
    return 5.0


def post_json(url: str, api_key: str, payload: dict[str, Any], retries: int = 1) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "JARVIS-Demo/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        # Rate limits (429) are transient — Groq's free tier has a low tokens-per-minute
        # cap. Groq's error body tells us exactly how long to wait ("try again in 31.65s"),
        # so honor that instead of a blind fixed delay that's often too short — a 4-second
        # wait against a 30+ second requirement just retries straight into the same 429.
        if exc.code == 429 and retries > 0:
            wait_seconds = min(_parse_retry_after_seconds(exc, body), 10)
            time.sleep(wait_seconds)
            return post_json(url, api_key, payload, retries=retries - 1)
        raise RuntimeError(f"Provider HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise RuntimeError(f"Provider request failed: {exc}") from exc


def provider_endpoint(provider: str) -> str:
    if provider == "openai":
        return "https://api.openai.com/v1/chat/completions"
    return "https://api.groq.com/openai/v1/chat/completions"


def provider_key(settings: Settings, provider: str) -> str:
    if provider == "openai":
        return settings.openai_api_key
    return settings.groq_api_key


def parse_tool_arguments(raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        loaded = json.loads(raw_arguments)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def call_model_once(
    settings: Settings,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
    }
    return post_json(provider_endpoint(provider), provider_key(settings, provider), payload)


def run_remote_agent(
    request: ChatRequest,
    settings: Settings,
    runner: ToolRunner,
    provider: str,
    model: str,
) -> ChatResponse:
    messages = build_messages(request.history, request.message, runner.memory_store, DEFAULT_USER_ID)
    tool_results: list[ToolResult] = []

    for _ in range(5):
        response = call_model_once(settings, provider, model, messages)
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("Provider returned no choices.")

        assistant_message = choices[0].get("message") or {}
        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            raw_answer = assistant_message.get("content") or "I completed the request."
            answer = strip_function_syntax(raw_answer) or "I completed the request."
            return ChatResponse(
                answer=answer,
                provider=provider,
                model=model,
                tools_used=tool_results,
                action=runner.extract_action(tool_results),
                image_url=runner.extract_image_url(tool_results),
                language=detect_language(answer),
            )

        messages.append(assistant_message)
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = str(function.get("name") or "")
            arguments = parse_tool_arguments(function.get("arguments"))
            result = runner.run(name, arguments, DEFAULT_USER_ID)
            tool_results.append(result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": name,
                    "content": result.model_dump_json(),
                }
            )

    return ChatResponse(
        answer="I ran the requested tools, but the model did not produce a final response. Please try again.",
        provider=provider,
        model=model,
        tools_used=tool_results,
        action=runner.extract_action(tool_results),
        image_url=runner.extract_image_url(tool_results),
        error="tool_loop_limit_reached",
    )


# ── Local fallback helpers ─────────────────────────────────────────────

def extract_memory_fact(message: str) -> tuple[str, str] | None:
    patterns = [
        r"remember that (?P<key>.*?) is (?P<value>.+)$",
        r"remember (?P<key>.*?) is (?P<value>.+)$",
        r"my (?P<key>.*?) is (?P<value>.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            key = re.sub(r"\W+", "_", match.group("key").strip().lower()).strip("_")
            value = match.group("value").strip().rstrip(".")
            if key and value:
                return key, value
    return None


def extract_url(message: str) -> str | None:
    url_match = re.search(r"https?://\S+", message, flags=re.IGNORECASE)
    if url_match:
        return url_match.group(0).rstrip(".,)")

    open_match = re.search(r"\bopen\s+([\w.-]+\.[a-z]{2,})(?:\s|$)", message, flags=re.IGNORECASE)
    if open_match:
        return open_match.group(1)
    return None


def clean_task_title(message: str) -> str:
    cleaned = re.sub(r"\b(add|create|save)\b", "", message, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(task|todo|reminder|remind me to)\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .") or message.strip()


def local_answer_from_tool(name: str, result: ToolResult) -> str:
    if not result.ok:
        return f"I tried to run {name}, but it failed: {result.error}"

    data = result.result if isinstance(result.result, dict) else {}
    if name == "get_time":
        return f"It is {data.get('readable')} in {data.get('timezone')}."
    if name == "get_system_status":
        return "All systems are online. Backend, local tools, memory, tasks, browser voice, wake word, image generation, news, music, and email are available."
    if name == "save_memory":
        return f"Memory saved: {data.get('key')} is {data.get('value')}."
    if name == "get_memory":
        memories = data.get("memories") or []
        if not memories:
            return "I do not have any saved memories for that yet."
        rendered = "; ".join(f"{item['key']}: {item['value']}" for item in memories[:5])
        return f"Here is what I remember: {rendered}."
    if name == "add_task":
        return f"Task added: {data.get('title')}."
    if name == "list_tasks":
        tasks = data.get("tasks") or []
        if not tasks:
            return "There are no open tasks saved."
        rendered = "; ".join(str(item["title"]) for item in tasks[:6])
        return f"Your open tasks are: {rendered}."
    if name == "open_url":
        return data.get("message") or "Opening the requested URL."
    if name == "web_search":
        if data.get("answer"):
            return data["answer"]
        results = data.get("results") or []
        if results:
            return f"I found this: {results[0]['title']} — {results[0]['snippet']}"
        return data.get("message") or "I could not find useful search results for that."
    if name == "read_url_content":
        if data.get("error"):
            return data["error"]
        excerpt = (data.get("text") or "")[:300]
        return f"Here's what I found: {excerpt}"
    if name == "generate_image":
        return data.get("message") or "I've generated the image for you."
    if name == "get_news":
        if data.get("answer"):
            return data["answer"]
        results = data.get("results") or []
        if results:
            return "Here's what's happening: " + "; ".join(r["title"] for r in results[:4]) + "."
        return data.get("message") or "I couldn't fetch the news right now."
    if name == "play_music":
        return data.get("message") or "Playing music on YouTube."
    if name == "compose_email":
        return data.get("message") or "I've drafted an email for you to review."
    return "Done."


# ── Multi-command splitter for local fallback ──────────────────────────

def split_commands(text: str) -> list[str]:
    """Split a compound request into sub-commands for local processing."""
    # Split on ' and also ', ' and then ', ' also ', ' and '
    parts = re.split(r"\s+(?:and also|and then|also|and)\s+", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def run_single_local_command(text: str, runner: ToolRunner, user_id: str) -> tuple[str, list[ToolResult]]:
    """Run a single local command and return (answer, tool_results)."""
    lowered = text.lower()
    tool_results: list[ToolResult] = []

    # Memory save
    memory_fact = extract_memory_fact(text)
    if memory_fact:
        key, value = memory_fact
        result = runner.run("save_memory", {"key": key, "value": value}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("save_memory", result), tool_results

    # Memory recall
    if "what do you remember" in lowered or "remember about" in lowered:
        result = runner.run("get_memory", {"query": text if "about" in lowered else ""}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("get_memory", result), tool_results

    # Image generation
    if re.search(r"\b(generate|create|draw|make|paint)\b.*\b(image|picture|photo|art|illustration)\b", lowered):
        prompt = re.sub(r"\b(generate|create|draw|make|paint)\b\s*(an?|the|me)?\s*(image|picture|photo|art|illustration)\s*(of|about|showing|with)?\s*", "", text, flags=re.IGNORECASE).strip()
        result = runner.run("generate_image", {"prompt": prompt or text}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("generate_image", result), tool_results

    # News
    if "news" in lowered or "headline" in lowered or "what's happening" in lowered:
        topic = re.sub(r"\b(get|show|tell|give|what's|whats|the|me|latest|today's|todays)\b", "", text, flags=re.IGNORECASE)
        topic = re.sub(r"\b(news|headlines?|happening)\b", "", topic, flags=re.IGNORECASE).strip()
        result = runner.run("get_news", {"topic": topic}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("get_news", result), tool_results

    # Music
    if re.search(r"\b(play|listen|music|song)\b", lowered):
        query = re.sub(r"^(play|listen to|put on)\s+", "", text, flags=re.IGNORECASE).strip()
        query = re.sub(r"\s*(music|song|for me|please)\s*$", "", query, flags=re.IGNORECASE).strip()
        result = runner.run("play_music", {"query": query or "popular music"}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("play_music", result), tool_results

    # Email
    if re.search(r"\b(email|mail|write.*email|send.*email|compose)\b", lowered):
        subject = re.sub(r"\b(write|send|compose|an?|email|mail|to)\b", "", text, flags=re.IGNORECASE).strip()
        result = runner.run("compose_email", {"to": "", "subject": subject or "No Subject", "body": ""}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("compose_email", result), tool_results

    # Time
    if "time" in lowered or "date" in lowered:
        result = runner.run("get_time", {"timezone": "Asia/Kolkata"}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("get_time", result), tool_results

    # Status
    if "status" in lowered or "diagnostic" in lowered or "system" in lowered:
        result = runner.run("get_system_status", {}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("get_system_status", result), tool_results

    # Open URL
    url = extract_url(text)
    if url and ("open" in lowered or lowered.startswith("go to")):
        result = runner.run("open_url", {"url": url}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("open_url", result), tool_results

    # Web search
    if lowered.startswith("search") or "look up" in lowered or "web search" in lowered:
        query = re.sub(r"^(search|web search|look up)\s+", "", text, flags=re.IGNORECASE).strip()
        result = runner.run("web_search", {"query": query or text}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("web_search", result), tool_results

    # Read a specific URL's content
    url = extract_url(text)
    if url and re.search(r"\b(read|summarize|summarise)\b", lowered):
        result = runner.run("read_url_content", {"url": url}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("read_url_content", result), tool_results

    # Tasks
    if "task" in lowered or "todo" in lowered or "remind me" in lowered:
        if "list" in lowered or "show" in lowered:
            result = runner.run("list_tasks", {}, user_id)
            tool_results.append(result)
            return local_answer_from_tool("list_tasks", result), tool_results
        result = runner.run("add_task", {"title": clean_task_title(text)}, user_id)
        tool_results.append(result)
        return local_answer_from_tool("add_task", result), tool_results

    return "", tool_results


def run_local_agent(request: ChatRequest, runner: ToolRunner) -> ChatResponse:
    text = request.message.strip()

    # Split into sub-commands for multi-tasking
    commands = split_commands(text)
    all_answers: list[str] = []
    all_tool_results: list[ToolResult] = []

    for cmd in commands:
        answer, results = run_single_local_command(cmd, runner, DEFAULT_USER_ID)
        if answer:
            all_answers.append(answer)
        all_tool_results.extend(results)

    if all_answers:
        combined_answer = " ".join(all_answers)
        return ChatResponse(
            answer=combined_answer,
            provider="local",
            tools_used=all_tool_results,
            action=runner.extract_action(all_tool_results),
            image_url=runner.extract_image_url(all_tool_results),
        )

    # No tool matched — general fallback
    return ChatResponse(
        answer=(
            "I am online in local mode. Add an OpenAI or Groq API key for full reasoning. "
            "I can handle time, status, memory, tasks, web search, opening URLs, "
            "image generation, news, music, and email."
        ),
        provider="local",
        tools_used=all_tool_results,
    )


async def generate_chat_response(request: ChatRequest, settings: Settings, runner: ToolRunner) -> ChatResponse:
    provider, model = select_provider(settings, request.provider)
    if provider == "local" or not model:
        return run_local_agent(request, runner)

    try:
        return await asyncio.to_thread(run_remote_agent, request, settings, runner, provider, model)
    except Exception as exc:
        fallback = run_local_agent(request, runner)
        fallback.error = str(exc)
        fallback.provider = f"local_fallback_after_{provider}_error"
        fallback.model = model
        is_rate_limit = "429" in str(exc) or "rate_limit" in str(exc)
        if is_rate_limit and fallback.answer.startswith("I am online in local mode"):
            fallback.answer = (
                "I'm temporarily rate-limited on my AI provider after a few requests in quick "
                "succession. Please try again in about a minute for a full answer."
            )
        return fallback

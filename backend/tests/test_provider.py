from app.ai.provider import detect_language


def test_detect_language_spanish_via_accents_and_punctuation():
    assert detect_language("Hola, ¿cómo estás hoy?") == "es"


def test_detect_language_spanish_via_stopwords():
    assert detect_language("Muchas gracias por tu ayuda con esto") == "es"


def test_detect_language_english_default():
    assert detect_language("Remember that my favorite color is red") == "en"


def test_detect_language_mostly_english_with_trailing_spanish_word_stays_english():
    text = (
        "I'm functioning within normal parameters, thank you for asking. "
        "No system issues or malfunctions to report. By the way, I've taken "
        "note of our conversation switch from English to Spanish. If you "
        "continue in Spanish, I'll respond accordingly. "
        "¿Qué te gustaría hacer a continuación?"
    )
    assert detect_language(text) == "en"


from app.ai.provider import strip_function_syntax


def test_strip_function_syntax_removes_self_closing_tag():
    assert strip_function_syntax("Sure, here you go. <function=get_system_status></function>") == "Sure, here you go."


def test_strip_function_syntax_removes_malformed_unclosed_tag():
    text = 'Saved. <function=save_memory>{"last_conversation": "Madrid"}<function> Anything else?'
    result = strip_function_syntax(text)
    assert "<function" not in result
    assert "Saved." in result
    assert "Anything else?" in result


def test_strip_function_syntax_removes_tag_with_stray_quote():
    text = 'La hora en Madrid es: <function=get_time>{"timezone": "Europe/Madrid"}"</function>'
    result = strip_function_syntax(text)
    assert "<function" not in result
    assert "La hora en Madrid es:" in result


def test_strip_function_syntax_leaves_normal_text_unchanged():
    assert strip_function_syntax("Hello, how can I help you today?") == "Hello, how can I help you today?"


from app.ai.provider import build_known_facts_block


def test_build_known_facts_block_empty():
    assert build_known_facts_block([]) == ""


def test_build_known_facts_block_lists_facts():
    memories = [
        {"key": "name", "value": "Anchal"},
        {"key": "favorite_color", "value": "red"},
    ]
    block = build_known_facts_block(memories)
    assert "- name: Anchal" in block
    assert "- favorite_color: red" in block
    assert "use naturally" in block


from app.ai.provider import build_feedback_patterns_block


def test_build_feedback_patterns_block_empty():
    assert build_feedback_patterns_block([]) == ""


def test_build_feedback_patterns_block_lists_dismissed_and_accepted():
    rows = [
        {"topic": "EV-market opportunities", "outcome": "dismissed"},
        {"topic": "studio-automation stress-test", "outcome": "accepted"},
    ]
    block = build_feedback_patterns_block(rows)
    assert "Dismissed: EV-market opportunities" in block
    assert "Accepted: studio-automation stress-test" in block


def test_build_feedback_patterns_block_counts_repeats():
    rows = [
        {"topic": "EV-market opportunities", "outcome": "dismissed"},
        {"topic": "EV-market opportunities", "outcome": "dismissed"},
    ]
    block = build_feedback_patterns_block(rows)
    assert "Dismissed: EV-market opportunities (x2)" in block


from app.ai.provider import build_messages, SYSTEM_PROMPT
from app.services.memory import MemoryStore


def test_build_messages_includes_known_facts(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_memory("default", "name", "Anchal")

    messages = build_messages([], "hello", store, "default")

    assert "name: Anchal" in messages[0]["content"]


def test_build_messages_without_memories_omits_block(tmp_path):
    store = MemoryStore(tmp_path / "test.db")

    messages = build_messages([], "hello", store, "default")

    assert messages[0]["content"] == SYSTEM_PROMPT


import json

from app.ai.tools import TOOL_DEFINITIONS


def test_system_prompt_and_tool_definitions_stay_within_token_budget():
    # SYSTEM_PROMPT + all tool schemas are resent on every single request, and Groq's free
    # tier caps at 8,000 tokens/minute. Two increments already blew past a comfortable
    # budget here by adding one verbose tool description, causing live rate-limit failures.
    # This catches that during development instead.
    approx_tokens = (len(SYSTEM_PROMPT) + len(json.dumps(TOOL_DEFINITIONS))) // 4
    assert approx_tokens < 4500, (
        f"System prompt + tool definitions are ~{approx_tokens} tokens, over the 4500 "
        "budget — trim SYSTEM_PROMPT or a tool's description before adding more."
    )


def test_no_single_tool_description_is_excessively_verbose():
    for tool in TOOL_DEFINITIONS:
        name = tool["function"]["name"]
        description = tool["function"]["description"]
        approx_tokens = len(description) // 4
        assert approx_tokens < 100, (
            f"'{name}' tool description is ~{approx_tokens} tokens (over 100) — this is "
            "resent on every request, so keep it concise and move detailed guidance into "
            "parameter descriptions or a system prompt rule instead."
        )

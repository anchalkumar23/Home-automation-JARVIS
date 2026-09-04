# AI Content Creation — Increment 5a: Trend-Researched Content Creation

## Context

This begins Section 4 of `AGENT.md` (AI Content Creation), started while Studio Automation (§2) is blocked pending the client's Home Assistant/network details. Section 4 spans several distinct output types (YouTube videos, podcasts, social media content, short-form videos, marketing materials, blog articles, product descriptions, presentations, scripts) — too broad for one increment, so it's decomposed the same way prior sections were.

- **5a (this increment)**: Social captions, YouTube/podcast scripts, and marketing/product copy — all researched against real current information before being written, not generated from the model's own assumptions.
- **Later**: Blog articles (more document-like, furthest from this app's voice-first design), presentations (structurally different — multi-slide, not prose).

Prior art: the user's other project, `agentic-os-personal` (`content-os/` subfolder), already implements a trend-research-to-content pipeline (research collectors → AI ranking → platform-styled generation, grounded in real sources with citation enforcement). It's Node.js and architecturally separate from this Python/FastAPI project, but its patterns translate directly: research before writing, ground content in real sources rather than the model's assumptions, and use platform-specific style rules (length, hooks, hashtag conventions) rather than one generic prompt for everything.

## Scope

**In scope:**
1. A new `create_content(topic, content_type, platform, research_notes)` tool covering three content types: `social_caption` (Instagram/LinkedIn/X), `script` (YouTube/podcast), and `marketing_copy`.
2. A research-first requirement: the model researches the topic via `web_search`/`get_news` (capped at 2 calls, matching the economy rule already established for company research in rule 10) before calling this tool, and the generated content must be grounded in what was actually found — never fabricated claims or made-up statistics.
3. A new `content_draft` `ClientAction` type and a new `ContentDraftCard` frontend component (editable/copyable, following `EmailDraftCard`'s pattern) — content renders as a card, not spoken text, since real output (hashtags, line breaks, script structure) can't be spoken cleanly under the existing no-markdown voice rule. JARVIS still speaks a one-line summary of what it made.
4. Per-content-type style guidance baked into the tool description: social captions get platform-specific hook/length/hashtag conventions; scripts get an intro hook + segments + call-to-action structure; marketing copy stays short and benefit-focused.

**Out of scope:**
- Blog articles, presentations — later sub-increments.
- Actual video/audio production (Section 5, AI Video Editing) — this increment produces the written script/copy, not the video itself.
- Persistence/saved content history — ephemeral for now, matching every on-demand feature built so far (search, news, research, business reports).
- Trend *discovery* as a standalone browsing feature (e.g. "show me trending topics") — research happens per-request, scoped to whatever topic the user asks about, not a general trend feed like the reference project's ranked article list.

## Design

### Tool: `create_content`

`backend/app/ai/tools.py` gains `_tool_create_content(args, user_id, store)`. Like `create_business_report`, this has no external side effect — it validates and packages already-researched content into a renderable action, so it needs no confirmation gate.

Parameters:
- `topic` (string, required) — what the content is about.
- `content_type` (string, required) — one of `social_caption`, `script`, `marketing_copy`.
- `platform` (string, optional) — for `social_caption`: `instagram`, `linkedin`, or `x`. Ignored for other content types.
- `content` (string, required) — the actual generated text, already written by the model per the style rules below.
- `sources` (array of strings, optional) — URLs the content was grounded in.

The tool itself doesn't call the LLM again to generate content — the model writes the content directly as a tool argument (the same pattern `create_business_report`'s `sections` argument already uses), and the tool just validates and wraps it into an action:
```python
{
    "action": {
        "type": "content_draft",
        "content_topic": topic,
        "content_format": content_type,
        "content_platform": platform,
        "content_body": content,
        "content_sources": sources,
    },
    "message": f"I've drafted {content_type_label} on {topic}.",
}
```

### Tool definition and style guidance

```
name: create_content
description: "Draft social media captions, video/podcast scripts, or marketing copy — always after researching the topic with web_search/get_news first (at most 2 calls, per rule 10's economy guidance), and always grounded in what was actually found. Never invent statistics, quotes, or claims not backed by the research.

Style per content_type:
- social_caption: platform-aware. instagram: short, punchy hook in the first line, emoji-friendly, 3-5 relevant hashtags at the end. linkedin: professional tone, no emoji-heavy style, a clear insight or takeaway, 1-2 hashtags. x: concise, fits a single post, at most 1-2 hashtags.
- script: spoken-word structure — an opening hook (first 5-10 seconds), 2-4 body segments, a closing call-to-action. Written to be read aloud, not as a formal document.
- marketing_copy: short, benefit-focused, one clear call-to-action, no filler."
parameters:
  topic: string, required
  content_type: string, required, enum [social_caption, script, marketing_copy]
  platform: string, optional, enum [instagram, linkedin, x]
  content: string, required — the actual drafted content
  sources: array of string (URLs), optional
```

### System prompt

A new numbered rule (after rule 10, renumbering rule 11) directs: when asked to create social content, a script, or marketing copy, research the topic first (per rule 10's 2-call economy limit) using web_search or get_news, then call create_content with the actual drafted text as the `content` argument, styled per the content type's rules in the tool description. Never fabricate facts, statistics, or quotes not backed by the research. Speak a one-line summary alongside the tool call — the card is the deliverable, not a replacement for acknowledging what was made.

### Schema and action-extraction changes

`backend/app/schemas.py`'s `ClientAction` gains `"content_draft"` to its `type` Literal, plus `content_topic`, `content_format` (holds `social_caption`/`script`/`marketing_copy` — named `content_format` rather than `content_type` to avoid confusion with `ClientAction.type`, the action-type discriminator), `content_platform`, `content_body`, `content_sources`. `backend/app/services/tool_runner.py`'s `extract_action()` gains a matching branch, following the established pattern.

### Frontend

`frontend/components/message-cards.tsx` gains `ContentDraftCard` — a titled card (topic + content type/platform badge) showing the drafted content in a monospace block with a copy button (reusing the existing `CopyButton` internal component), plus a sources list styled consistently with `SearchSourcesCard`/`BusinessReportCard`. `frontend/components/jarvis-interface.tsx` adds a render branch for `content_draft`, following the same pattern as every other action type.

### Testing

No new pure logic distinct from the existing `compose_email`/`draft_calendar_event`/`create_business_report` pattern (validate and package already-generated data) — verified manually, consistent with those.

### Manual verification plan

1. Ask "Write an Instagram caption about `<a real, current topic>`." Confirm JARVIS researches it first (visible in tool-call metadata), then a content card appears with a real, platform-appropriate caption (hook, hashtags) grounded in something findable about the topic — not generic filler.
2. Ask for a LinkedIn caption and an X post on the same topic — confirm each reflects that platform's distinct style (LinkedIn: professional/insight-driven; X: concise).
3. Ask "Write a YouTube script about `<a real topic>`." Confirm it has a hook, body segments, and a call-to-action, written to be read aloud.
4. Ask for marketing copy for a product/service. Confirm it's short and benefit-focused.
5. Confirm the content card includes a working copy button, and that JARVIS's spoken/text reply itself stays voice-safe (no bullets/hashtags in the actual spoken text — those belong in the card).
6. Ask about a topic where little real information exists — confirm JARVIS either says so or keeps the content generic/honest rather than inventing specific claims.
7. Quickly re-verify business reports (4c) and company research (4b) still work unaffected.

## Explicitly deferred to future increments

- Blog articles.
- Presentations.
- Actual video/audio production (Section 5).
- Saved content history.
- Standalone trend-discovery/browsing feature.

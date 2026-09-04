# Business Intelligence — Increment 4c: Business Reports

## Context

This is the third sub-increment of Business Intelligence (§15), following 4a (real-time market data) and 4b (company/competitor research). It closes out the buildable part of §15 by giving JARVIS's research a structured, document-like output — a real business report — rather than only a spoken narrative.

- **4a (done)**: Real-time market data.
- **4b (done)**: Company/competitor research (multi-angle search + synthesis, prompt-only).
- **4c (this increment)**: Business reports — a structured visual card compiled from real research.
- **Blocked, deferred**: Sales insights / customer analytics — no CRM or sales data source connected; needs client input first.

The core tension driving this design: a "report" implies structure (sections, headings), but the voice-first system prompt rule (14) bans bullets and headers from spoken/text chat replies, since every reply is also read aloud by TTS. The resolution, confirmed with the user: reports render as a structured **visual card** (which can use real headings, since it's UI, not spoken text) alongside a brief spoken summary in the chat reply itself — the same pattern already established for email drafts and calendar events.

## Scope

**In scope:**
1. A new `create_business_report(topic, sections, sources)` tool. No external side effect — purely packages already-gathered research into a renderable structure, so (like `compose_email`/`draft_calendar_event`) it needs no human-confirmation gate.
2. A new `business_report` `ClientAction` type, with `report_topic`, `report_sections` (list of `{heading, content}`), and `report_sources` (list of URLs) fields.
3. A new frontend `BusinessReportCard` component, rendered via the existing `action`-based card pattern.
4. A new system prompt rule: only call this tool with sections backed by real tool results (from `web_search`, `get_market_quote`, `read_url_content`), never fabricated content, and always pair it with a brief spoken summary — not a silent card with no verbal acknowledgment.

**Out of scope:**
- Persistence/saved report history — confirmed as ephemeral for this increment, matching every other on-demand feature built so far. No new database storage.
- Sales insights / customer analytics — blocked pending client input on data source.
- Export (PDF, copy-to-clipboard, etc.) for the report card — a possible future increment if usage shows it's wanted.

## Design

### Tool: `create_business_report`

`backend/app/ai/tools.py` gains `_tool_create_business_report(args, user_id, store)`. It validates `topic` (non-empty) and `sections` (non-empty list of `{heading, content}` objects), then returns:
```python
{
    "action": {
        "type": "business_report",
        "report_topic": topic,
        "report_sections": sections,
        "report_sources": sources,  # optional list of URLs
    },
    "message": f"I've put together a business report on {topic}.",
}
```
This mirrors `_tool_compose_email`/`_tool_draft_calendar_event`'s existing pattern of packaging structured data into an `action` for the frontend to render — no network call, no external side effect, so no confirmation step is needed per this project's established safety boundary (confirmation is only required for actions with real-world consequences).

### Tool definition

```
name: create_business_report
description: "Compile a structured business report after researching a topic (a company, market, or investment idea) using web_search, get_market_quote, and/or read_url_content. Only call this with sections backed by what you actually found — never fabricate content. Still give a brief spoken summary in your reply; this tool produces a visual card, it doesn't replace speaking to the user."
parameters:
  topic: string, required
  sections: array of { heading: string, content: string }, required
  sources: array of string (URLs), optional
```

### Schema and action-extraction changes

`backend/app/schemas.py`'s `ClientAction` gains `"business_report"` to its `type` Literal, plus `report_topic: str | None`, `report_sections: list[dict] | None`, `report_sources: list[str] | None`. `backend/app/services/tool_runner.py`'s `extract_action()` gains a branch mapping a `business_report` action dict to the typed `ClientAction`, following the exact pattern already used for the other action types.

### System prompt

A new tool bullet (`create_business_report`) and a new numbered rule: when the user asks for a report, summary document, or overview of a company/market/investment idea, research it first (per rule 20's multi-angle approach), then call `create_business_report` with sections drawn only from what was actually found — if a section has nothing to report (e.g. no financial data for a private company), omit that section rather than inventing content. The tool call should accompany a short spoken summary, not stand alone silently.

### Frontend

`frontend/components/message-cards.tsx` gains `BusinessReportCard`, rendered the same way `EmailDraftCard`/`CalendarEventDraftCard` already are — a titled card showing the topic, each section as a heading + paragraph, and a sources list styled consistently with the existing `SearchSourcesCard`. `frontend/components/jarvis-interface.tsx` adds a render branch for `message.action?.type === "business_report"`, following the exact pattern of the existing action-type branches.

### Testing

No new pure logic worth unit-testing — the tool only validates and packages already-gathered data, the same as `compose_email`/`draft_calendar_event`, neither of which have dedicated test files. Verified manually.

### Manual verification plan

1. Ask "Give me a business report on `<a real, findable company>`." Expected: JARVIS researches it (visible via tool calls), speaks a brief summary, and a structured report card appears with real sections (not fabricated placeholders).
2. Confirm the report card shows real headings/structure (this is allowed, since it's a card, not spoken text) while the chat reply text itself stays voice-safe (no bullets/headers in the spoken/text portion).
3. Ask for a report on something with real market data available (a public company) — confirm a financials/market-data section reflects a real `get_market_quote` result.
4. Ask for a report on something where a section genuinely has nothing to report — confirm that section is omitted rather than filled with invented content.
5. Confirm sources in the card are real, clickable links.
6. Quickly re-verify 4a (market data) and 4b (research) still work unaffected.

## Explicitly deferred to future increments

- Saved/retrievable report history.
- Report export (PDF, copy, etc.).
- Sales insights / customer analytics (blocked pending client input on data source).

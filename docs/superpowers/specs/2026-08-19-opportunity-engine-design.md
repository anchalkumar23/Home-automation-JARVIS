# Opportunity Engine — Increment 8b

## Context

The second of the client's "10 Core Functions" (`AGENT.md`), built on-demand for the same reason as "What Am I Forgetting?" (8a): Studio Automation (7a) is still blocked on the client providing TV IP/MAC details, so this fills the gap using only existing infrastructure — no new integrations, no client input needed.

The client's original description: "actively look for connections between new technologies, consumer needs, regulatory changes, new companies, emerging markets, patents, search trends, and unsolved problems, and surface specific, evidence-backed opportunities." Continuous/proactive monitoring for this is out of scope for now (same reasoning as 8a's deferred proactive triggering) — this increment builds the on-demand version.

## Scope

**In scope:**
1. A new system-prompt rule instructing JARVIS to research a user-given topic across `web_search`, `get_news`, `search_patents`, and `search_papers`, looking specifically for connections between technology, regulation, unmet needs, patent activity, and market trends — then present findings via the **existing** `create_business_report` tool (topic "Opportunities in X"), one specific evidence-backed opportunity per section.
2. A slightly larger research budget than rule 10's general 2-call limit, since cross-referencing multiple tool *kinds* (web/news/patents/papers) is the actual value proposition here.
3. Honest "nothing concrete found" behavior — if research doesn't surface anything, say so rather than manufacturing filler, matching rule 14's precedent.

**Out of scope:**
- No new tool, no new `TOOL_DEFINITIONS` entry, no new schema, no new frontend component — entirely reuses `create_business_report`'s existing card and the four existing research tools.
- Proactive/scheduled scanning — this is topic-driven only, triggered by the user naming a market/product/idea. No "surprise me" or context-inferred mode (per the confirmed trigger-scope decision).
- Patent/paper search depth tuning, dedicated opportunity-scoring, or any persistence of past opportunities surfaced — none of that exists as a data source yet.

## Design

### System prompt rule

Inserted as rule 15 (pushing the personality rule to 16):

> 15. For opportunity-finding requests ("find opportunities in X," "what's promising in the Y market"), research across web_search/get_news/search_patents/search_papers — up to 3 calls across different tool kinds, more generous than rule 10 since cross-referencing tech/regulation/patents/market is the point — then present via create_business_report (topic "Opportunities in X"), one specific evidence-backed opportunity per section. If nothing concrete turns up, say so rather than inventing one.

No new tool is defined; `create_business_report` already accepts an arbitrary topic and arbitrary sections, so it's reused exactly as rule 14 reuses it for "What You Might Be Forgetting."

### Token budget

This costs roughly one rule's worth of characters (~350-450 chars, no `TOOL_DEFINITIONS` growth at all, since no new tool schema is added). Current headroom after 8a is ~351 chars / ~88 tokens — this rule will likely need a few characters trimmed elsewhere to fit, following the same measure-then-trim approach used throughout this session.

### Testing

No new pure-function logic is introduced (this is prompt-only), so no new unit tests are needed — consistent with how rule-only changes elsewhere in this project (e.g. the file-upload rule fix) weren't unit tested, only manually verified. The existing token-budget guard tests (`test_provider.py`) must still pass.

### Manual verification plan

1. Ask "find opportunities in [some market/topic]." Confirm JARVIS researches across multiple tool kinds (visible via `tools_used` including at least 2 of web_search/get_news/search_patents/search_papers) and produces an "Opportunities in X" report card with specific, sourced opportunities — not generic advice.
2. Ask about an obscure/narrow topic where little real information exists. Confirm JARVIS says it didn't find anything concrete rather than fabricating opportunities.
3. Quickly re-verify plain web_search, get_news, and business reports still work unaffected.

## Explicitly deferred to future increments

- Proactive/continuous opportunity scanning (this is Early Warning System / Global Radar territory, and needs scheduling infrastructure this project doesn't have yet).
- Persisting/tracking previously surfaced opportunities over time (Second Brain / Learning System territory).

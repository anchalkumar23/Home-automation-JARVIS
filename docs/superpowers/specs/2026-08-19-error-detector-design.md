# Error Detector / Decision Simulator — Increment 8c

## Context

The third and fourth of the client's "10 Core Functions" (`AGENT.md`, items 4-5), combined into one increment since they're closely related — stress-testing a plan and simulating a decision's outcomes are the same underlying behavior (don't just agree, reason about what could go wrong or vary) applied to slightly different framings. Built on-demand, same as 8a/8b, using only existing infrastructure.

## Scope

**In scope:**
1. A new system-prompt rule, triggered only when the user explicitly asks for it (e.g. "stress-test this plan," "what could go wrong with X," "simulate this decision") — not a standing trait applied to every plan mentioned in conversation.
2. For a stress-test request: identify weak assumptions, risks, and more efficient alternatives.
3. For a decision-simulation request: break the outcome into best-case / likely-case / worst-case scenarios plus the key variables that could change which one happens.
4. Ground critique in research (`web_search`/`get_news`, same budget as rule 10) when the topic benefits from outside information.
5. Present the result via the **existing** `create_business_report` tool (topic "Stress Test: X" or "Decision Simulation: X").
6. Honest "looks solid" behavior — if the plan genuinely holds up, say so rather than inventing problems, matching the honesty rule already established in 8a/8b.

**Out of scope:**
- No new tool, no new `TOOL_DEFINITIONS` entry, no new schema, no new frontend component — reuses `create_business_report` exactly as 8a/8b do.
- Standing/always-on critique of every plan mentioned in casual conversation — explicitly rejected in favor of explicit-trigger-only, per the confirmed trigger-style decision.
- Tracking whether past critiques/simulations turned out to be accurate — that's Learning System territory, no data source for it yet.

## Design

### System prompt rule

Inserted as rule 16 (pushing the personality rule to 17):

> 16. For stress-test/decision-simulation requests ("stress-test this plan," "what could go wrong with X," "simulate this decision"), don't just agree — identify weak assumptions, risks, and better alternatives; for a specific decision, break it into best-case/likely/worst-case outcomes and the key variables that could change them. Ground it in research (web_search/get_news, rule 10 budget) when it helps, then present via create_business_report (topic "Stress Test: X" or "Decision Simulation: X"). If the plan looks genuinely solid, say so — don't invent problems.

No new tool is defined; `create_business_report` already accepts an arbitrary topic and arbitrary sections, reused exactly as rules 14 and 15 already do.

### Token budget

Current headroom is ~10 characters after the Opportunity Engine rule — this rule (~450+ chars) will require trimming existing text elsewhere to fit, using the same measure-then-trim approach as every prior round this session.

### Testing

No new pure-function logic (prompt-only change), so no new unit tests — consistent with rules 14/15. The existing token-budget guard tests in `test_provider.py` must still pass.

### Manual verification plan

1. Describe a plan with an obvious flaw and ask JARVIS to stress-test it. Confirm it identifies the actual weakness (not generic boilerplate) and presents via a "Stress Test: X" report card.
2. Ask JARVIS to simulate a decision (e.g. "simulate the outcome of switching vendors for X"). Confirm the report card has distinct best-case/likely/worst-case sections and names the variables that could change the outcome.
3. Describe a genuinely solid plan with no real flaws and ask for a stress test. Confirm JARVIS says it holds up rather than manufacturing fake problems.
4. Mention a plan in passing without asking for a stress test or simulation. Confirm JARVIS does NOT unprompted critique it — the rule should stay silent unless explicitly triggered.
5. Quickly re-verify Opportunity Engine and "What Am I Forgetting?" still work unaffected.

## Explicitly deferred to future increments

- Standing/always-on critique mode (could be a future opt-in setting).
- Tracking prediction accuracy over time (Learning System).

# Business Intelligence — Increment 4b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable thorough, multi-angle company/competitor research by reusing existing tools (`web_search`, `read_url_content`), and fix a real bug this behavior surfaces — the Sources card only showing the first of several search calls in a reply.

**Architecture:** Prompt-only backend change (a new system prompt rule) plus one frontend fix (`searchSources()` aggregates across all search-shaped tool calls in a reply instead of just the first). No new backend tool, no new Python logic.

**Tech Stack:** No new dependencies. Plain TypeScript array operations on the frontend.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: System prompt rule for company/competitor research

**Files:**
- Modify: `backend/app/ai/provider.py:115-116` (append rule 20)

- [ ] **Step 1: Add rule 20**

Modify `backend/app/ai/provider.py`, replacing the end of `SYSTEM_PROMPT` (current lines 115-116, rule 19 and the closing `"""`):
```python
19. For get_market_quote, build the symbol correctly for the asset class: plain ticker for stocks (AAPL), EXCHANGE:BASE_QUOTE for forex (OANDA:EUR_USD), EXCHANGE:PAIR for crypto (BINANCE:BTCUSDT). If the tool result has an error, say so plainly rather than making up a price.
20. When asked to research a company, competitor, or product, don't rely on a single generic web_search — run a few different search angles (what the company does, recent news or developments, funding or market position/competitors) and, if one result looks like the authoritative source (the official site, a substantial recent article), read it in full with read_url_content before answering. Synthesize what you found into a short spoken briefing (per rule 18). If a specific angle turns up nothing (e.g. funding details aren't found), say so plainly rather than guessing or inventing numbers.
"""
```

- [ ] **Step 2: Run the test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions (this is a prompt-text-only change).

---

### Task 2: Frontend — aggregate sources across multiple search calls

**Files:**
- Modify: `frontend/components/jarvis-interface.tsx:545-549` (`searchSources` helper)

- [ ] **Step 1: Rewrite `searchSources` to aggregate and dedupe**

Modify `frontend/components/jarvis-interface.tsx`, replacing the `searchSources` helper (current lines 545-549):
```tsx
  const searchSources = (msg: Message): SearchResult[] => {
    const calls = msg.toolsUsed?.filter((t) => SOURCE_TOOL_NAMES.has(t.name) && t.ok) ?? []
    const all = calls.flatMap((call) => {
      const results = (call.result as { results?: SearchResult[] } | undefined)?.results
      return Array.isArray(results) ? results : []
    })
    const seen = new Set<string>()
    return all.filter((result) => {
      if (seen.has(result.url)) return false
      seen.add(result.url)
      return true
    })
  }
```

This changes `.find()` (first match only) to `.filter()` (every matching call), flattens all their `results` arrays together, then deduplicates by `url` — since different search angles can surface the same page (e.g. a company's official site appearing in more than one query). `readSourceUrl` (the next helper, for `read_url_content`) is untouched — it only ever needs one URL, not a list.

- [ ] **Step 2: Typecheck**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\frontend"
npx tsc --noEmit
```
Expected: no output (no type errors).

---

### Task 3: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart the backend**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
  $procId = $_
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 4
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too.

- [ ] **Step 2: Multi-angle research**

Ask "Research `<a real, findable company>` for me." Expected: the reply covers more than one angle — what they do, something recent, and (if findable) funding/market position — not a one-line shallow answer.

- [ ] **Step 3: Sources aggregation**

Check the Sources list under that reply — confirm it includes links that plausibly came from more than one distinct search (not just whatever a single `web_search` call happened to return).

- [ ] **Step 4: Honest gaps**

Ask about a company/topic where a specific angle (e.g. funding) genuinely isn't findable. Expected: JARVIS says it couldn't find that piece, not a fabricated number.

- [ ] **Step 5: Voice-safe formatting**

Confirm the reply reads as natural spoken sentences — no bullets, no recited list.

- [ ] **Step 6: Regression check — single search still works**

Ask a plain one-off question like "search for `<something>`." Expected: the Sources list still shows correctly for a single `web_search` call, confirming the aggregation fix didn't break the single-call case.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 4: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Company/Competitor Research" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 3's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Business reports.
- Sales insights / customer analytics (blocked pending client input on data source).

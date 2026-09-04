# Productivity Foundation — Increment 2b: Calendar Read

## Context

Increment 2a (Gmail OAuth + real send) is complete: `backend/app/services/google_auth.py` handles the OAuth consent flow and token refresh via `google_auth_oauthlib.flow.Flow`, tokens live in a single-row `oauth_tokens` table in the existing SQLite `MemoryStore`, and email sending is a user-clicked UI action (`POST /api/gmail/send`), never something the AI model can trigger on its own. That scope was `gmail.send` only.

This increment adds read-only Google Calendar access so JARVIS can answer "what's on my calendar" style questions in conversation. Unlike email sending, calendar *reading* is non-destructive, so it's exposed as a normal AI-callable tool — the same pattern as `get_news`, `get_time`, `web_search`, etc.

Because the existing Gmail connection was authorized under the narrower `gmail.send`-only scope, adding calendar access requires the user to reconnect and re-consent to the combined scope set — Google does not allow silently expanding an existing grant. The user has confirmed this one-time reconnect is acceptable.

## Scope

**In scope:**
1. Widen the OAuth scope requested during connection to include `calendar.readonly` alongside the existing `gmail.send`, requested together in one consent flow.
2. A new `list_calendar_events` tool, callable by the AI model, that returns upcoming events from the user's primary calendar (default lookahead: 7 days, per the user's choice).
3. Graceful handling when the stored connection doesn't yet have calendar permission (pre-reconnect) — a clear message rather than a raw API error.
4. A small tooltip update on the existing "Connect Gmail" header button to reflect that it now grants both Mail and Calendar access.

**Out of scope (deferred):**
- Calendar *write* access (creating/editing events) — increment 2c.
- Task/reminder redesign — increment 2d.
- Any dedicated calendar UI panel — chat-based Q&A only for this increment, per the user's choice; a visual panel can follow later once read access is proven out.
- Any AI-autonomous calendar modification — this increment is read-only end to end.

## Design

### OAuth scope widening

`backend/app/services/google_auth.py` currently has a single `GMAIL_SEND_SCOPE` constant used everywhere `_make_flow` builds a `Flow`. This becomes a `REQUIRED_SCOPES` list containing both `https://www.googleapis.com/auth/gmail.send` and `https://www.googleapis.com/auth/calendar.readonly`, used consistently in `_make_flow`, and as the fallback default (`credentials.scopes or REQUIRED_SCOPES`) in both `exchange_code` and `get_valid_access_token`. No other function in this file changes — `get_valid_access_token` already reads whatever scopes are actually stored per-connection, so it naturally handles both pre- and post-reconnect states without modification.

Because this constant change is used by `build_auth_url`, the very next click of the existing "Connect Gmail" button automatically requests both scopes together — no changes needed to the `/api/gmail/auth-url` endpoint, the callback, or the frontend connect flow itself.

### `list_calendar_events` tool

Added to `backend/app/ai/tools.py`, following the same self-contained pattern as the existing `get_news`/`web_search` tools (their own inline `urllib` call, no separate service file). It:
- Accepts an optional `days` parameter (nullable in the schema, matching the established pattern for optional tool parameters), defaulting to 7 when omitted.
- Calls `google_auth.get_valid_access_token` to get a valid (refreshed if needed) access token.
- Calls the Calendar API's `events.list` for the `primary` calendar with `timeMin`/`timeMax` spanning now through `days` ahead, `singleEvents=true`, `orderBy=startTime`.
- Returns a simple list of `{summary, start, location}` per event for the model to summarize conversationally.

Registered in both `TOOL_DEFINITIONS` (the schema the model sees) and `TOOL_REGISTRY` (the name-to-function mapping `ToolRunner` uses) — the same two places every existing tool is registered.

### Error handling

- Not connected at all (no stored tokens): `get_valid_access_token` already raises `RuntimeError("Gmail is not connected...")` — caught and returned as a tool result the model can relay.
- Connected, but only under the old `gmail.send`-only scope (hasn't reconnected yet): the Calendar API returns an HTTP 403. The tool catches this specifically and returns a clear "please reconnect to grant calendar access" message, rather than surfacing a raw API error or generic failure.
- Other Calendar API errors (network issues, malformed response): caught generically and returned as a tool error, consistent with how other network-calling tools in this codebase already behave.

### System prompt

One line added to the existing tool bullet list in `SYSTEM_PROMPT` (matching the format of every other listed tool). No new numbered behavior rule is needed — the existing "use tools whenever the user's request matches a tool's purpose" rule already covers when to reach for it.

### Frontend

The "Connect Gmail" header button's `title` tooltip is updated to read something like "Connected as `<email>` (Mail + Calendar)" once connected, and "Connect Google to send email and read your calendar" beforehand — clarifying that one connection now covers both without renaming the visible button label.

### Testing

The existing `test_build_auth_url_includes_client_id_and_scope` test in `backend/tests/test_google_auth.py` is extended to assert both `gmail.send` and `calendar.readonly` appear in the generated consent URL — a cheap, valuable regression check on the scope-widening change. The actual Calendar API call inside `list_calendar_events` is not unit-tested, consistent with how this codebase has never unit-tested other tools' real network calls (`get_news`, `web_search`) — verified manually instead, per the plan below.

### Manual verification plan

1. Reconnect Gmail via the header button — confirm Google's consent screen now lists both mail-send and calendar-read permissions, and after approving, the callback page and header tooltip reflect the combined connection.
2. Ask "What's on my calendar this week?" — confirm it lists actual upcoming events from the connected Google account (create a test event beforehand if the calendar is empty).
3. Ask with an explicit range, e.g. "What's on my calendar today?" or "next 3 days" — confirm the `days` parameter is respected.
4. If feasible, test the pre-reconnect error path: hit the tool before reconnecting (or by temporarily reverting the scope) to confirm the 403 case produces a clear reconnect prompt rather than a crash or raw error text.

## Explicitly deferred to future increments

- 2c: Calendar write (create/edit events).
- 2d: Task/reminder redesign.
- A dedicated calendar UI panel.
- Everything else in `AGENT.md` beyond Section 1 and this productivity sub-sequence.

# Productivity Foundation — Increment 2a: Gmail OAuth & Real Send

## Context

Increment 1 (Core AI Assistant foundation — persistent memory, bilingual EN/ES, Whisper voice input, voice UX polish) is complete and tested. This starts Section 14 of `AGENT.md` (Productivity Assistant). That section is too broad for one increment (calendar, email, tasks, reminders, notes), so it's decomposed into a sequence:

- **2a (this increment)**: Gmail OAuth + real email sending.
- **2b**: Calendar read (reuses 2a's OAuth infrastructure with an added scope).
- **2c**: Calendar write (create/edit events).
- **2d**: Task/reminder redesign (due dates/times) — unrelated to OAuth, can slot in independently.

Today, JARVIS's `compose_email` tool only drafts a subject/body and shows a `mailto:` link — it cannot actually send email. `add_task`/`list_tasks` are backed by a minimal SQLite table (title + done only).

A reference OAuth implementation exists at `C:\Anchal\Fiverr\agentic-os-personal\content-os\server\google\` (Node.js/Express, `googleapis` npm package, `gmail.readonly` scope only). It is not directly portable (different language/stack — JARVIS's backend is Python/FastAPI), but its OAuth flow shape (build consent URL → exchange code → store tokens with silent refresh) and its documented Google Cloud Console setup steps are a useful reference.

Research into current Python patterns confirmed: Google's own `google-auth` + `google-auth-oauthlib` libraries are still the standard 2026 approach for this exact scenario, and hand-rolling OAuth token refresh is a known source of silent auth bugs — worth the two added dependencies rather than reimplementing it. One reference project (NOVA-Personal-AI-Assistant) builds in human-in-the-loop approval before sending email, which aligns with how `compose_email`'s draft-then-confirm UI already works today.

## Scope

**In scope:**
1. A new Google Cloud Console project and OAuth client (fresh project for JARVIS, not reusing `agentic-os-personal`'s).
2. An in-app "Connect Gmail" flow: a header button opens Google's consent screen; a backend callback completes the token exchange and stores credentials.
3. A real `POST /api/gmail/send` endpoint that sends a MIME email via the Gmail API, using the `gmail.send`-scoped, auto-refreshed credentials.
4. A "Send via Gmail" button added to the existing email-draft form, alongside the existing "Open in Mail App" (`mailto:`) option — both remain available.
5. Connection-status visibility (a header indicator/button showing connected vs. not, and which address).

**Out of scope (deferred to later increments):**
- Calendar read/write (2b/2c).
- Task/reminder redesign (2d).
- Reading/searching the inbox (only `gmail.send` scope is requested — no read access).
- Any AI-autonomous sending. The model's `compose_email` tool continues to only draft; actually sending is a direct, user-clicked UI action calling the backend endpoint, never something the LLM decides or triggers on its own. This is a deliberate safety boundary, not a temporary limitation.

## Design

### Google Cloud Console setup (manual, one-time, done by the user)

A new Google Cloud project is created specifically for JARVIS. Steps (to be written in full, exact detail in the implementation plan): create the project, enable the Gmail API, configure the OAuth consent screen (External, the user's own account added as a test user), request scope `https://www.googleapis.com/auth/gmail.send` only, create an OAuth Client ID of type "Web application" with authorized redirect URI `http://127.0.0.1:8000/api/gmail/callback`. The resulting Client ID and Client Secret are pasted into `backend/.env` (never committed, matching the project's existing secret-handling convention).

### OAuth flow

`backend/app/services/google_auth.py` (new) wraps `google_auth_oauthlib.flow.Flow` (the web-flow class — not `InstalledAppFlow`, which assumes blocking CLI usage) to: build the consent URL, exchange an authorization code for tokens on callback, and load/auto-refresh stored credentials for use by the send endpoint. `google-auth` and `google-auth-oauthlib` are added as new dependencies specifically to avoid hand-rolling token refresh; the actual Gmail API call itself still uses the project's existing raw-`urllib` HTTP style (matching `post_json` in `provider.py`), not the full `google-api-python-client` SDK.

Token storage reuses the existing SQLite database (`MemoryStore`'s connection), adding a new `oauth_tokens` table holding a single row (access token, refresh token, expiry, scopes) — single-user, so no per-user keying needed. This keeps one database and one connection-management pattern rather than introducing a second storage mechanism.

### Backend endpoints (new `backend/app/routers/gmail.py`)

- `GET /api/gmail/auth-url` — returns the Google consent URL for the frontend to open.
- `GET /api/gmail/callback` — receives the authorization code, exchanges it for tokens, stores them, shows a plain confirmation page.
- `GET /api/gmail/status` — returns `{connected: bool, email: string | null}`.
- `POST /api/gmail/send` — accepts `{to, subject, body}`, loads/refreshes stored credentials, builds a MIME message via Python's stdlib `email` module, base64url-encodes it, and calls Gmail's `users.messages.send` via `urllib`. Returns success or a clear error (not connected, expired/revoked token, Gmail API error).

### Frontend

- A new "Gmail" header button (next to the existing Voice/Wake buttons) reflects connection status from `/api/gmail/status` on load; clicking it when disconnected opens the consent URL in a new tab.
- The existing email-draft form (already rendered when `compose_email` produces a draft) gains a "Send via Gmail" button next to the existing "Open in Mail App" link. Clicking it calls `POST /api/gmail/send` directly — this is a UI action, not routed through the LLM tool-calling loop. Success or failure is shown as a message in the comms log, reusing the same message-injection pattern built for voice errors in increment 1c.

### Error handling

- Not connected when "Send via Gmail" is clicked: inline comms-log message prompting the user to connect Gmail first (with a way to trigger the connect flow from there).
- Refresh token expired or revoked: the send attempt fails with a clear "Gmail connection expired — please reconnect" message rather than a silent or cryptic failure.
- Gmail API errors (e.g. invalid recipient): surfaced as the actual API error message, not swallowed.

### Testing plan

OAuth consent requires a real browser and the user's actual Google account, so that part is inherently manual, human-tested — consistent with every increment so far. What's unit-testable: the MIME-message-construction and base64url-encoding logic (pure function, given `to`/`subject`/`body` produces the expected encoded payload structure), following the same TDD pattern used for `detect_language`/`build_known_facts_block`/`build_multipart_body` in earlier increments.

Manual verification: connect Gmail via the header button (real consent screen), confirm the status indicator updates; draft an email via chat, click "Send via Gmail," confirm it actually arrives in the recipient's inbox; disconnect/revoke access via Google's account settings and confirm the app surfaces a clear reconnect prompt rather than failing silently.

## Explicitly deferred to future increments

- 2b: Calendar read.
- 2c: Calendar write.
- 2d: Task/reminder redesign (due dates/times).
- Everything else in `AGENT.md` beyond Section 1 and this productivity sub-sequence.

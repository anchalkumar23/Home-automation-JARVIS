# Real Authentication (single-password login) — Increment 9a

## Context

The security review (2026-09-05) identified missing authentication as the single CRITICAL finding, patched with an interim shared-secret header (`X-Jarvis-Key`) as a stopgap. That patch explicitly deferred real auth to its own increment — this is that increment.

Since JARVIS is built for one person (not a multi-tenant product), this doesn't need accounts, signup, or per-user identity — just a real login gate that replaces the header trick with something a browser can't leak via XSS and that supports proper session revocation.

## Scope

**In scope:**
1. A single password (not per-user credentials), set once via a setup script, stored as a salted hash — never plaintext, never reversible.
2. A login screen in the frontend; nothing else gates access to the app.
3. Real server-side sessions (a `sessions` table), issued as an httpOnly, Secure, SameSite=Lax cookie on login — invisible to JavaScript, unlike the interim key which lived in a `NEXT_PUBLIC_` env var visible to any visitor's DevTools.
4. Rate limiting on the login endpoint: 5 attempts / 15 minutes per IP.
5. A logout endpoint that deletes the session server-side (real revocation, not just "the client forgets the token").
6. Removing the interim `X-Jarvis-Key` mechanism entirely — this replaces it, not layers on top.
7. Removing the client-supplied `user_id` field from `ChatRequest` — since there's only ever one real user, `user_id` becomes a hardcoded server-side constant once a session is verified, closing the "self-asserted identity" finding from the security review without building unneeded multi-user infrastructure.

**Out of scope:**
- Multi-user accounts, roles, or permissions — explicitly not needed per the client's own answer ("it's for him only").
- Password reset flows — there's one password; if forgotten, regenerate it via the same setup script used to set it initially (a local/physical-access operation, not a web flow).
- Email verification, 2FA — no email/identity involved, doesn't apply.
- Any change to the Gmail/Calendar OAuth flow (`google_auth.py`) — that's a separate concern (the app's own connection to Google's APIs), unrelated to who's allowed to use the app.

## Design

### Password storage

`backend/app/services/auth.py` (new):
- `hash_password(password: str) -> str` — PBKDF2-HMAC-SHA256 via Python's stdlib `hashlib.pbkdf2_hmac` (600,000 iterations, per current OWASP guidance for PBKDF2-SHA256), random 16-byte salt, returns `"<salt_hex>:<hash_hex>"`. No new dependency — stdlib only.
- `verify_password(password: str, stored: str) -> bool` — recomputes and compares using `hmac.compare_digest` (constant-time, avoids timing attacks).

`backend/scripts/set_password.py` (new, run manually once): prompts for a password (via `getpass`, not echoed), hashes it, prints the line to paste into `.env` as `JARVIS_PASSWORD_HASH=...`. Not a web endpoint — deliberately a local script, since changing the login password is a physical-access operation for a single-user app, not something the app itself needs a UI for.

### Sessions

New table in `backend/app/services/memory.py` (same file as `tasks`/`memories`/`oauth_tokens` — no new module needed, this is exactly the kind of small persistent state that already lives there):

```sql
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL
)
```

`MemoryStore` gains:
- `create_session(ttl_days: int = 30) -> str` — generates `secrets.token_urlsafe(32)`, inserts with `expires_at` = now + ttl, returns the token.
- `session_valid(token: str) -> bool` — looks up the token, checks `expires_at` hasn't passed. (A session found-but-expired is treated the same as not-found — no special-cased response, avoiding an oracle for "does this old token exist.")
- `delete_session(token: str) -> None` — for logout.
- Expired-session cleanup: opportunistically delete rows where `expires_at < now` inside `create_session` (piggybacking on an already-open connection rather than a separate cron/scheduled job, which this project doesn't have).

### Routes

`backend/app/routers/auth.py` (new):
- `POST /api/auth/login` — body `{password: str}`. Rate-limited (in-process dict of `{ip: [attempt_timestamps]}`, 5 attempts/15 min — acceptable for a single-instance deployment; no new dependency). On success: verify against `JARVIS_PASSWORD_HASH`, create a session, set the cookie (`httponly=True, secure=True, samesite="lax", max_age=30 days`), return `{ok: true}`. On failure: generic `401 {"detail": "Incorrect password"}` — never reveal whether the failure was rate-limiting vs. wrong password beyond a distinct 429 for the former.
- `POST /api/auth/logout` — deletes the session row, clears the cookie.
- `GET /api/auth/status` — returns `{authenticated: bool}` for the frontend to check on load (this route itself is NOT gated, obviously — it's how the frontend knows whether to show the login screen).

### Session-check dependency

`backend/app/security.py` — replace `require_api_key` with `require_session`:
```python
async def require_session(request: Request) -> None:
    token = request.cookies.get("jarvis_session")
    if not token or not request.app.state.memory_store.session_valid(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
```
Applied exactly where `require_api_key` was applied today (`main.py`'s router-level `dependencies=gate`, and the three per-route gates in `gmail.py`) — same shape, different mechanism. `/api/gmail/callback` and `/health` stay ungated, same reasoning as before (browser-redirect target from Google; harmless status check).

### `user_id` simplification

`backend/app/schemas.py` — remove `user_id` from `ChatRequest` entirely. `backend/app/routers/chat.py` and everywhere `request.user_id` is read (`provider.py`) uses a single module-level constant (`DEFAULT_USER_ID = "default"`) instead. This directly closes the "unverified client-supplied user_id" MEDIUM finding — there's no longer a field to spoof, because there's no field.

### Frontend

- A new top-level gate in `jarvis-interface.tsx` (or a small new `LoginScreen` component in `message-cards.tsx`'s style): on mount, call `GET /api/auth/status`; if not authenticated, render a minimal password-entry form instead of the main UI.
- Login form POSTs to `/api/auth/login` with `credentials: "include"` (so the Set-Cookie response is honored) and re-checks status on success.
- Every existing `fetch` call to the backend adds `credentials: "include"` (needed for the httpOnly cookie to be sent cross-origin, since frontend :3000 and backend :8000 are different origins even on localhost).
- `frontend/lib/api.ts` — remove `JARVIS_API_KEY`/`apiHeaders()` (no longer needed, cookies are automatic); keep the file only if something else still needs it, otherwise delete it (CLAUDE.md: remove dead code).
- A logout button somewhere reachable in the UI (small — a menu item is enough, no dedicated screen needed).

### CORS

`backend/app/main.py` — `allow_credentials=True` is already set (required for cookies to work cross-origin); no change needed there, but this is the point where that setting starts actually mattering rather than being inert.

### Token budget

None — this doesn't touch `SYSTEM_PROMPT` or `TOOL_DEFINITIONS` at all, it's pure infrastructure below the LLM layer.

### Testing

- `test_auth.py` (new): `hash_password`/`verify_password` roundtrip, wrong password rejected, `MemoryStore.create_session`/`session_valid`/`delete_session` (valid, expired, deleted, unknown-token cases).
- Rate limiting: a unit test hitting the login rate-limiter helper directly (6th attempt within the window rejected, resets after the window).
- Existing tests that construct `ChatRequest`/call `/api/chat` need `user_id` removed from their payloads.

### Manual verification plan

1. Fresh start with no session cookie: confirm the login screen appears, not the main UI.
2. Wrong password: confirm a clear rejection, no hint about what's wrong beyond "incorrect password."
3. Correct password: confirm the main UI loads and stays loaded across a page refresh (cookie persists).
4. Try 6 wrong-password attempts within 15 minutes: confirm the 6th is rate-limited, not just rejected.
5. Log out: confirm the login screen reappears and previously-authenticated requests now fail.
6. Confirm every existing feature (chat, calendar, Gmail, tasks, TV control) still works once logged in — this is a pure infrastructure swap, nothing about their behavior should change.
7. Confirm `document.cookie` in the browser console does NOT show the session token (proves httpOnly is actually working, not just configured).

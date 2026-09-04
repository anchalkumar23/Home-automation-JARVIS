# Productivity Foundation — Increment 2c: Calendar Write

## Context

Increment 2b (Calendar read) is complete: `list_calendar_events` is an AI-callable tool, and the OAuth scope covers `gmail.send` + `calendar.readonly`. This increment adds the ability to create, edit, and delete Google Calendar events.

Unlike reading, writing has real-world consequences — a created event blocks time on the user's actual calendar and, if it has attendees, sends them real invitation emails. Per increment 2a's established safety boundary (the AI never autonomously sends email — it only drafts, and a human clicks "send"), the user confirmed this increment should follow the same pattern: the AI proposes a calendar change, a human confirms it via the UI before anything actually happens on the real calendar. The user also confirmed the fuller scope of create + edit + delete together (rather than deferring edit/delete to a later increment), and that attendee support is in scope, with the understanding that adding attendees means real people receive real invite emails when a draft is confirmed.

## Scope

**In scope:**
1. `draft_calendar_event` — an AI-callable tool that proposes creating a new event, or editing an existing one (distinguished by an optional `event_id`). Never creates or modifies anything directly — it returns a draft the UI renders for confirmation.
2. `propose_delete_calendar_event` — an AI-callable tool that proposes deleting an existing event, shown as a simple confirmation rather than a full draft card.
3. A small necessary addition to the existing `list_calendar_events` tool (2b): each returned event now includes its `id`, since editing/deleting requires knowing which specific event is being referenced.
4. Three new backend endpoints (create/update/delete) that perform the actual Google Calendar API calls, triggered only by a direct user action in the UI — never by the AI tool-calling loop.
5. A new `CalendarEventDraftCard` frontend component (create/edit) and a delete-confirmation UI, both calling the new endpoints directly and reporting outcomes via the existing comms-log message pattern.
6. Attendee support: the draft can include attendee email addresses; confirming the event sends them real Google Calendar invitations (the default, expected behavior of adding attendees).
7. A system-prompt addition instructing the model to check the current time (via the existing `get_time` tool) before drafting an event with a relative date like "tomorrow," rather than guessing.

**Out of scope:**
- Any path where the AI can create, edit, or delete a real calendar event without a human confirming first — this boundary is absolute, matching the email-sending precedent.
- Recurring events, multiple calendars (only the `primary` calendar), or reminders/notifications settings beyond Google's defaults.
- A dedicated calendar UI panel (still chat-based, per 2b's scope decision, now extended to writes via draft cards).

## Design

### Tools

`draft_calendar_event(event_id?, summary, start, end, description?, location?, attendees?)` — added to `backend/app/ai/tools.py` following the existing tool pattern. It does not call any Google API itself; it simply returns an action object (`type: "calendar_event_draft"`) carrying all the fields plus whether `event_id` was provided (edit) or not (create), for the frontend to render as an editable card. This mirrors exactly how `compose_email` already works — the tool drafts, it doesn't act.

`propose_delete_calendar_event(event_id, summary_for_display, start_for_display)` — similarly returns an action (`type: "calendar_event_delete_confirm"`) with just enough display info for a clear "Delete '<summary>' on <start>?" confirmation — no draft-editing needed for a deletion.

`list_calendar_events` (from 2b) is modified to include each event's `id` in its returned data — a small, targeted addition to existing code (per the project's practice of fixing what's in the way rather than avoiding touching it), needed so the model can say "delete the 3pm meeting" and actually have an `event_id` to pass to `propose_delete_calendar_event`.

### Backend endpoints

A new `backend/app/routers/calendar.py`, parallel to the existing `gmail.py`, all reusing `google_auth.get_valid_access_token`:
- `POST /api/calendar/events` — creates a new event via the Calendar API's `events.insert`. Attendees, if present, trigger real invitation emails (Google's default behavior when an event has attendees) — this is intentional per the scope above, not an oversight.
- `PATCH /api/calendar/events/{event_id}` — updates an existing event via `events.patch`.
- `DELETE /api/calendar/events/{event_id}` — deletes an event via `events.delete`.

The logic that builds the Calendar API's event JSON body from a draft's fields (summary/start/end/description/location/attendees) is a small pure function, following the same testable-helper pattern as increment 2a's MIME-message-building code.

### Frontend

`CalendarEventDraftCard` (new component, mirrors the existing `EmailDraftCard`): editable summary/start/end/description/location fields, an attendees input (comma-separated email addresses), and a primary button reading "Create Event" or "Save Changes" depending on whether an `event_id` is present. Submitting calls the corresponding new backend endpoint directly — not through the AI tool-calling loop — and reports success/failure as a comms-log message, reusing the `pushSystemMessage` helper already built in increment 2a.

A smaller delete-confirmation UI (Confirm/Cancel) handles the `calendar_event_delete_confirm` action type, calling the new `DELETE` endpoint on confirm.

### System prompt

Two additions to `SYSTEM_PROMPT`: a tool-list mention for both new tools (matching the existing bullet format), and a behavior rule that any calendar creation/edit/deletion request must go through these tools — never claimed as done without the tool confirming it — and that relative dates ("tomorrow," "next Friday") should be resolved using `get_time` first rather than guessed.

### Error handling

- Not connected / insufficient scope: same pattern as `list_calendar_events` — a clear message rather than a raw API error, since the same 403-on-missing-scope situation applies to write operations too.
- Invalid or missing event_id on edit/delete (e.g., stale reference from an old conversation): the Calendar API's own 404 is surfaced as a clear "that event could no longer be found" message rather than a crash.
- Attendee email validation: minimal (non-empty, contains "@") — Google's own API will reject genuinely malformed addresses, and this is a personal single-user tool, not a public-facing form.

### Manual verification plan

1. Ask JARVIS to schedule something ("Schedule a team sync tomorrow at 3pm for 30 minutes") — confirm the draft card appears with correctly resolved date/time (verifying the `get_time`-first behavior), edit a field, click "Create Event," confirm it actually appears on the real Google Calendar.
2. Ask to add an attendee to a new event draft — confirm on creation, verify the invited person actually receives a Google Calendar invitation email.
3. Ask "what's on my calendar" (2b), then ask to reschedule or edit one of the listed events — confirm the draft card appears in edit mode with the existing event's details pre-filled, and saving actually updates the real event.
4. Ask to delete an event — confirm the delete-confirmation UI appears (not a full draft card), and confirming actually removes it from the real calendar.
5. Verify canceling a draft or delete-confirmation does not modify anything on the real calendar.

## Explicitly deferred to future increments

- 2d: Task/reminder redesign.
- Recurring events, multiple calendars, reminder/notification customization.
- Everything else in `AGENT.md` beyond Section 1 and this productivity sub-sequence.

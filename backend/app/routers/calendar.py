from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import CalendarEventPayload, CalendarEventResponse, DeleteEventResponse
from app.services import google_auth

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def build_event_body(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    time_zone: str | None = None,
) -> dict[str, Any]:
    start_obj: dict[str, str] = {"dateTime": start}
    end_obj: dict[str, str] = {"dateTime": end}
    if time_zone:
        start_obj["timeZone"] = time_zone
        end_obj["timeZone"] = time_zone

    body: dict[str, Any] = {
        "summary": summary,
        "start": start_obj,
        "end": end_obj,
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]
    return body


def _calendar_request(access_token: str, url: str, method: str, body: dict[str, Any] | None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="That event could no longer be found.") from exc
        raise HTTPException(status_code=502, detail=f"Google Calendar error {exc.code}: {body_text}") from exc


def _access_token_or_raise(request: Request) -> str:
    settings = request.app.state.settings
    store = request.app.state.memory_store
    try:
        return google_auth.get_valid_access_token(settings, store)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/events", response_model=CalendarEventResponse)
async def create_event(payload: CalendarEventPayload, request: Request) -> CalendarEventResponse:
    access_token = _access_token_or_raise(request)
    body = build_event_body(
        payload.summary,
        payload.start,
        payload.end,
        payload.description,
        payload.location,
        payload.attendees,
        payload.time_zone,
    )
    data = _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}?sendUpdates=all", "POST", body)
    return CalendarEventResponse(ok=True, event_id=data.get("id"))


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(event_id: str, payload: CalendarEventPayload, request: Request) -> CalendarEventResponse:
    access_token = _access_token_or_raise(request)
    body = build_event_body(
        payload.summary,
        payload.start,
        payload.end,
        payload.description,
        payload.location,
        payload.attendees,
        payload.time_zone,
    )
    data = _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}/{event_id}?sendUpdates=all", "PATCH", body)
    return CalendarEventResponse(ok=True, event_id=data.get("id"))


@router.delete("/events/{event_id}", response_model=DeleteEventResponse)
async def delete_event(event_id: str, request: Request) -> DeleteEventResponse:
    access_token = _access_token_or_raise(request)
    _calendar_request(access_token, f"{CALENDAR_EVENTS_URL}/{event_id}?sendUpdates=all", "DELETE", None)
    return DeleteEventResponse(ok=True)

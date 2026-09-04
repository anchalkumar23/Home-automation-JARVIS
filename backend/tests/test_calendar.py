from app.routers.calendar import build_event_body


def test_build_event_body_minimal():
    body = build_event_body("Team sync", "2026-08-10T15:00:00+05:30", "2026-08-10T15:30:00+05:30")

    assert body["summary"] == "Team sync"
    assert body["start"] == {"dateTime": "2026-08-10T15:00:00+05:30"}
    assert body["end"] == {"dateTime": "2026-08-10T15:30:00+05:30"}
    assert "description" not in body
    assert "location" not in body
    assert "attendees" not in body


def test_build_event_body_with_optional_fields():
    body = build_event_body(
        "Team sync",
        "2026-08-10T15:00:00+05:30",
        "2026-08-10T15:30:00+05:30",
        description="Weekly check-in",
        location="Room 4",
        attendees=["a@example.com", "b@example.com"],
    )

    assert body["description"] == "Weekly check-in"
    assert body["location"] == "Room 4"
    assert body["attendees"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]


def test_build_event_body_with_time_zone():
    body = build_event_body(
        "Team sync",
        "2026-08-10T15:00",
        "2026-08-10T15:30",
        time_zone="Asia/Kolkata",
    )

    assert body["start"] == {"dateTime": "2026-08-10T15:00", "timeZone": "Asia/Kolkata"}
    assert body["end"] == {"dateTime": "2026-08-10T15:30", "timeZone": "Asia/Kolkata"}

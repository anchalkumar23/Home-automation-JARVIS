from app.services.memory import MemoryStore


def test_get_google_tokens_returns_none_when_not_connected(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.get_google_tokens() is None


def test_save_and_get_google_tokens_roundtrip(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_google_tokens(
        access_token="access123",
        refresh_token="refresh456",
        expiry="2026-01-01T00:00:00+00:00",
        scopes="https://www.googleapis.com/auth/gmail.send",
        email="user@example.com",
    )

    result = store.get_google_tokens()

    assert result["access_token"] == "access123"
    assert result["refresh_token"] == "refresh456"
    assert result["email"] == "user@example.com"


def test_save_google_tokens_upserts_single_row(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_google_tokens(
        access_token="first", refresh_token="r1", expiry="", scopes="", email=None,
    )
    store.save_google_tokens(
        access_token="second", refresh_token="r2", expiry="", scopes="", email="a@b.com",
    )

    result = store.get_google_tokens()

    assert result["access_token"] == "second"
    assert result["email"] == "a@b.com"


def test_add_task_with_due_at_and_priority(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.add_task("default", "Call the dentist", due_at="2026-08-10T10:00:00+05:30", priority="high")

    assert result["due_at"] == "2026-08-10T10:00:00+05:30"
    assert result["priority"] == "high"


def test_add_task_defaults_priority_to_medium(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.add_task("default", "Buy milk")

    assert result["priority"] == "medium"
    assert result["due_at"] is None


def test_list_tasks_sorts_by_due_date_with_nulls_last(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.add_task("default", "No due date")
    store.add_task("default", "Due later", due_at="2026-08-15T10:00:00+05:30")
    store.add_task("default", "Due sooner", due_at="2026-08-10T10:00:00+05:30")

    tasks = store.list_tasks("default")

    assert [t["title"] for t in tasks] == ["Due sooner", "Due later", "No due date"]


def test_complete_task_marks_done(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    task = store.add_task("default", "Finish report")

    result = store.complete_task("default", task["id"])

    assert result is True
    tasks = store.list_tasks("default", include_done=True)
    assert tasks[0]["done"] is True


def test_complete_task_returns_false_for_unknown_id(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.complete_task("default", 999) is False


def test_delete_task_removes_row(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    task = store.add_task("default", "Temporary task")

    result = store.delete_task("default", task["id"])

    assert result is True
    assert store.list_tasks("default", include_done=True) == []


def test_delete_task_returns_false_for_unknown_id(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.delete_task("default", 999) is False


def test_save_memory_with_category(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.save_memory("default", "project_x_lead", "Sarah", category="person")

    assert result["category"] == "person"


def test_save_memory_without_category_defaults_to_general(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.save_memory("default", "favorite_color", "blue")

    assert result["category"] == "general"


def test_list_memories_filters_by_category(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_memory("default", "project_x_lead", "Sarah", category="person")
    store.save_memory("default", "project_x_deadline", "October", category="goal")

    memories = store.list_memories("default", category="person")

    assert [m["key"] for m in memories] == ["project_x_lead"]


def test_list_memories_filters_by_general_category(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_memory("default", "favorite_color", "blue")
    store.save_memory("default", "project_x_lead", "Sarah", category="person")

    memories = store.list_memories("default", category="general")

    assert [m["key"] for m in memories] == ["favorite_color"]


def test_list_memories_combines_category_and_query(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.save_memory("default", "project_x_lead", "Sarah runs Project X", category="person")
    store.save_memory("default", "project_y_lead", "Tom runs Project Y", category="person")

    memories = store.list_memories("default", query="project x", category="person")

    assert [m["key"] for m in memories] == ["project_x_lead"]


def test_record_recommendation_feedback_roundtrip(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    result = store.record_recommendation_feedback("default", "EV-market opportunities", "dismissed")

    assert result == {"topic": "EV-market opportunities", "outcome": "dismissed"}


def test_recent_feedback_summary_orders_most_recent_first(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    store.record_recommendation_feedback("default", "EV-market opportunities", "dismissed")
    store.record_recommendation_feedback("default", "studio-automation stress-test", "accepted")

    summary = store.recent_feedback_summary("default")

    assert [row["topic"] for row in summary] == ["studio-automation stress-test", "EV-market opportunities"]


def test_recent_feedback_summary_respects_limit(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    for i in range(5):
        store.record_recommendation_feedback("default", f"topic {i}", "dismissed")

    summary = store.recent_feedback_summary("default", limit=2)

    assert len(summary) == 2


def test_create_session_returns_a_valid_session(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    token = store.create_session()

    assert store.session_valid(token) is True


def test_session_valid_rejects_unknown_token(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    assert store.session_valid("not-a-real-token") is False


def test_session_valid_rejects_expired_session(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    token = store.create_session(ttl_days=-1)

    assert store.session_valid(token) is False


def test_delete_session_invalidates_it(tmp_path):
    store = MemoryStore(tmp_path / "test.db")
    token = store.create_session()

    store.delete_session(token)

    assert store.session_valid(token) is False

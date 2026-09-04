from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


class MemoryStore:
    def __init__(self, database_path: Path, encryption_key: str = "") -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        # Falls back to a process-local key when none is configured (e.g. tests) —
        # data stays encrypted at rest either way, just not decryptable across restarts
        # without a persistent TOKEN_ENCRYPTION_KEY in .env.
        self._fernet = Fernet(encryption_key.encode() if encryption_key else Fernet.generate_key())
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, key)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    due_at TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expiry TEXT,
                    scopes TEXT,
                    email TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._migrate_tasks_columns(connection)
            self._migrate_memories_columns(connection)
            connection.commit()

    def _migrate_tasks_columns(self, connection: sqlite3.Connection) -> None:
        """CREATE TABLE IF NOT EXISTS is a no-op on tables that already exist, so a
        database created before due_at/priority were added needs those columns
        backfilled explicitly. SQLite has no ADD COLUMN IF NOT EXISTS, so check first.
        """
        existing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "due_at" not in existing_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN due_at TEXT")
        if "priority" not in existing_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium'")

    def _migrate_memories_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(memories)")}
        if "category" not in existing_columns:
            connection.execute("ALTER TABLE memories ADD COLUMN category TEXT")

    CATEGORIES = ("person", "project", "document", "decision", "goal", "general")

    def save_memory(
        self, user_id: str, key: str, value: str, category: str | None = None
    ) -> dict[str, str]:
        normalized_key = key.strip().lower().replace(" ", "_")
        clean_value = value.strip()
        if not normalized_key or not clean_value:
            raise ValueError("Memory key and value are required.")
        clean_category = category.strip().lower() if category and category.strip() else None
        if clean_category == "general":
            clean_category = None
        if clean_category is not None and clean_category not in self.CATEGORIES:
            clean_category = None

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (user_id, key, value, category)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, normalized_key, clean_value, clean_category),
            )
            connection.commit()
        return {"key": normalized_key, "value": clean_value, "category": clean_category or "general"}

    def list_memories(
        self, user_id: str, query: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]

        if query:
            pattern = f"%{query.strip().lower()}%"
            conditions.append("(LOWER(key) LIKE ? OR LOWER(value) LIKE ?)")
            params.extend([pattern, pattern])

        if category:
            clean_category = category.strip().lower()
            if clean_category == "general":
                conditions.append("category IS NULL")
            else:
                conditions.append("category = ?")
                params.append(clean_category)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT key, value, category, created_at FROM memories
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT 20
                """,
                params,
            ).fetchall()
        return [{**dict(row), "category": row["category"] or "general"} for row in rows]

    def add_task(
        self, user_id: str, title: str, due_at: str | None = None, priority: str = "medium"
    ) -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required.")
        clean_priority = priority if priority in ("low", "medium", "high") else "medium"

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (user_id, title, due_at, priority) VALUES (?, ?, ?, ?)",
                (user_id, clean_title, due_at, clean_priority),
            )
            connection.commit()
            task_id = int(cursor.lastrowid)
        return {
            "id": task_id,
            "title": clean_title,
            "done": False,
            "due_at": due_at,
            "priority": clean_priority,
        }

    def list_tasks(self, user_id: str, include_done: bool = False) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if include_done:
                rows = connection.execute(
                    """
                    SELECT id, title, done, due_at, priority, created_at FROM tasks
                    WHERE user_id = ?
                    ORDER BY (due_at IS NULL), due_at ASC, created_at DESC
                    LIMIT 30
                    """,
                    (user_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, title, done, due_at, priority, created_at FROM tasks
                    WHERE user_id = ? AND done = 0
                    ORDER BY (due_at IS NULL), due_at ASC, created_at DESC
                    LIMIT 30
                    """,
                    (user_id,),
                ).fetchall()
        return [{**dict(row), "done": bool(row["done"])} for row in rows]

    def save_google_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expiry: str,
        scopes: str,
        email: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO oauth_tokens (id, access_token, refresh_token, expiry, scopes, email, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expiry = excluded.expiry,
                    scopes = excluded.scopes,
                    email = excluded.email,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    self._fernet.encrypt(access_token.encode()).decode(),
                    self._fernet.encrypt(refresh_token.encode()).decode(),
                    expiry,
                    scopes,
                    email,
                ),
            )
            connection.commit()

    def get_google_tokens(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT access_token, refresh_token, expiry, scopes, email FROM oauth_tokens WHERE id = 1"
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["access_token"] = self._fernet.decrypt(data["access_token"].encode()).decode()
        data["refresh_token"] = self._fernet.decrypt(data["refresh_token"].encode()).decode()
        return data

    def record_recommendation_feedback(self, user_id: str, topic: str, outcome: str) -> dict[str, str]:
        clean_outcome = outcome.strip().lower()
        clean_topic = topic.strip()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO recommendation_feedback (user_id, topic, outcome) VALUES (?, ?, ?)",
                (user_id, clean_topic, clean_outcome),
            )
            connection.commit()
        return {"topic": clean_topic, "outcome": clean_outcome}

    def recent_feedback_summary(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT topic, outcome, created_at FROM recommendation_feedback
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def complete_task(self, user_id: str, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_task(self, user_id: str, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            connection.commit()
        return cursor.rowcount > 0

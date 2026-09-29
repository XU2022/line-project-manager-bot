"""Deterministic, business-neutral task storage operations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from .database import Database


def _iso_now(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


class TaskService:
    def __init__(self, database: Database, *, timezone: str = "Asia/Tokyo"):
        self.database = database
        self.timezone = timezone

    def register_member(
        self, member_id: str, display_name: str, roles: Iterable[str] = ()
    ) -> None:
        member_id = member_id.strip()
        display_name = display_name.strip()
        if not member_id or not display_name:
            raise ValueError("member_id and display_name are required")
        if len(display_name) > 80:
            raise ValueError("display_name must be at most 80 characters")
        timestamp = _iso_now(self.timezone)
        roles_json = json.dumps(sorted(set(roles)), ensure_ascii=False)
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO members (
                    member_id, display_name, roles_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(member_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    roles_json=excluded.roles_json,
                    active=1,
                    updated_at=excluded.updated_at
                """,
                (member_id, display_name, roles_json, timestamp, timestamp),
            )

    def get_member(self, member_id: str) -> sqlite3.Row | None:
        with self.database.session() as connection:
            return connection.execute(
                "SELECT * FROM members WHERE member_id=? AND active=1", (member_id,)
            ).fetchone()

    def find_member_by_name(self, display_name: str) -> sqlite3.Row | None:
        with self.database.session() as connection:
            return connection.execute(
                """
                SELECT * FROM members
                WHERE display_name=? COLLATE NOCASE AND active=1
                """,
                (display_name.strip(),),
            ).fetchone()

    def get_task(self, task_id: str) -> sqlite3.Row | None:
        with self.database.session() as connection:
            return connection.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id.upper(),)
            ).fetchone()

    def can_modify_task(self, task_id: str, actor_id: str) -> bool:
        task = self.get_task(task_id)
        member = self.get_member(actor_id)
        if task is None or member is None:
            return False
        roles = set(json.loads(member["roles_json"]))
        return (
            "admin" in roles
            or task["created_by"] == actor_id
            or task["owner_id"] == actor_id
        )

    def create_task(
        self,
        *,
        name: str,
        created_by: str,
        owner_id: str | None = None,
        due_at: str | None = None,
        stage: str = "planning",
        workflow_name: str = "default",
        notes: str | None = None,
    ) -> sqlite3.Row:
        name = name.strip()
        if not name:
            raise ValueError("task name is required")
        if len(name) > 200:
            raise ValueError("task name must be at most 200 characters")
        if len(stage) > 64:
            raise ValueError("stage must be at most 64 characters")
        timestamp = _iso_now(self.timezone)
        with self.database.session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM settings WHERE key='task_sequence'"
            ).fetchone()
            sequence = int(row["value"]) + 1 if row else 1
            connection.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES ('task_sequence', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (str(sequence), timestamp),
            )
            task_id = f"TASK-{sequence:04d}"
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, name, workflow_name, stage, status, owner_id,
                    due_at, notes, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    name,
                    workflow_name,
                    stage,
                    owner_id,
                    due_at,
                    notes,
                    created_by,
                    timestamp,
                    timestamp,
                ),
            )
            self._event(connection, task_id, created_by, "created", timestamp)
            return connection.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()

    def update_task(
        self,
        task_id: str,
        *,
        actor_id: str,
        stage: str | None = None,
        owner_id: str | None = None,
        due_at: str | None = None,
        status: str | None = None,
        notes: str | None = None,
    ) -> sqlite3.Row:
        allowed_statuses = {"open", "blocked", "completed", "cancelled"}
        if status is not None and status not in allowed_statuses:
            raise ValueError(f"unsupported status: {status}")

        fields: dict[str, str | None] = {}
        for key, value in {
            "stage": stage,
            "owner_id": owner_id,
            "due_at": due_at,
            "status": status,
            "notes": notes,
        }.items():
            if value is not None:
                fields[key] = value
        if not fields:
            raise ValueError("at least one update is required")

        timestamp = _iso_now(self.timezone)
        if status == "completed":
            fields["completed_at"] = timestamp
        if status == "cancelled":
            fields["cancelled_at"] = timestamp
        fields["updated_at"] = timestamp

        assignments = ", ".join(f"{key}=?" for key in fields)
        values = list(fields.values()) + [task_id]
        with self.database.session() as connection:
            result = connection.execute(
                f"UPDATE tasks SET {assignments} WHERE task_id=?", values
            )
            if result.rowcount != 1:
                raise KeyError(task_id)
            self._event(connection, task_id, actor_id, "updated", timestamp, fields)
            return connection.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()

    def list_tasks(self, *, include_closed: bool = False) -> list[sqlite3.Row]:
        query = "SELECT * FROM tasks"
        parameters: tuple[str, ...] = ()
        if not include_closed:
            query += " WHERE status NOT IN (?, ?)"
            parameters = ("completed", "cancelled")
        query += " ORDER BY due_at IS NULL, due_at, task_id"
        with self.database.session() as connection:
            return list(connection.execute(query, parameters))

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        task_id: str,
        actor_id: str,
        event_type: str,
        timestamp: str,
        details: dict | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO task_events (
                event_key, task_id, actor_id, event_type, occurred_at, details_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                task_id,
                actor_id,
                event_type,
                timestamp,
                json.dumps(details or {}, ensure_ascii=False),
            ),
        )

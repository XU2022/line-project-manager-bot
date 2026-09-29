from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from line_project_manager import Database, ReminderRunner, TaskService, reminders_due
from line_project_manager.line_gateway import LineQuota


class CoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "tasks.sqlite3")
        self.database.initialize_default()
        self.service = TaskService(self.database)
        self.service.register_member("U_EXAMPLE_ALICE", "Alice", ["admin"])
        self.service.register_member("U_EXAMPLE_BOB", "Bob", ["contributor"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_update_and_close_task(self) -> None:
        task = self.service.create_task(
            name="Demo task",
            created_by="U_EXAMPLE_ALICE",
            owner_id="U_EXAMPLE_BOB",
            due_at="2026-10-15T18:00:00+09:00",
        )
        self.assertEqual(task["task_id"], "TASK-0001")
        self.assertEqual(task["status"], "open")

        updated = self.service.update_task(
            "TASK-0001",
            actor_id="U_EXAMPLE_BOB",
            stage="review",
            status="completed",
        )
        self.assertEqual(updated["stage"], "review")
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(self.service.list_tasks(), [])

    def test_previous_day_noon_reminder(self) -> None:
        self.service.create_task(
            name="Demo task",
            created_by="U_EXAMPLE_ALICE",
            owner_id="U_EXAMPLE_BOB",
            due_at="2026-10-15T18:00:00+09:00",
        )
        zone = ZoneInfo("Asia/Tokyo")
        with self.database.session() as connection:
            before = reminders_due(
                connection, datetime(2026, 10, 14, 11, 59, tzinfo=zone)
            )
            due = reminders_due(
                connection, datetime(2026, 10, 14, 12, 0, tzinfo=zone)
            )
        self.assertEqual(before, [])
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].scheduled_at, "2026-10-14T12:00:00+09:00")
        with self.database.session() as connection:
            late = reminders_due(
                connection, datetime(2026, 10, 15, 12, 0, tzinfo=zone)
            )
        self.assertEqual(late, [])

    def test_reminder_runner_sends_once_and_records_cost(self) -> None:
        self.service.create_task(
            name="Demo task",
            created_by="U_EXAMPLE_ALICE",
            owner_id="U_EXAMPLE_BOB",
            due_at="2026-10-15T18:00:00+09:00",
        )
        client = FakePushClient(usage=10, limit=200)
        runner = ReminderRunner(
            database=self.database,
            push_client=client,
            group_id="C_EXAMPLE_GROUP",
            estimated_push_cost=3,
        )
        now = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        first = runner.run(now)
        second = runner.run(now)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["candidates"], 0)
        self.assertEqual(len(client.calls), 1)
        with self.database.session() as connection:
            dispatch = connection.execute(
                "SELECT status, quota_cost FROM reminder_dispatches"
            ).fetchone()
        self.assertEqual((dispatch["status"], dispatch["quota_cost"]), ("sent", 3))

    def test_reminder_runner_respects_budget(self) -> None:
        self.service.create_task(
            name="Demo task",
            created_by="U_EXAMPLE_ALICE",
            owner_id="U_EXAMPLE_BOB",
            due_at="2026-10-15T18:00:00+09:00",
        )
        client = FakePushClient(usage=199, limit=200)
        runner = ReminderRunner(
            database=self.database,
            push_client=client,
            group_id="C_EXAMPLE_GROUP",
            estimated_push_cost=3,
        )
        now = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        result = runner.run(now)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(client.calls, [])


class FakePushClient:
    def __init__(self, *, usage: int, limit: int | None):
        self._quota = LineQuota(limit=limit, usage=usage)
        self.calls = []

    def quota(self):
        return self._quota

    def push_reminder(self, group_id, text, owner_id, *, retry_key):
        self.calls.append((group_id, text, owner_id, retry_key))
        return "request-id"


if __name__ == "__main__":
    unittest.main()

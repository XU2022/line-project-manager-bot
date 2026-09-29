"""Pure reminder planning; delivery is intentionally handled elsewhere."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .line_gateway import LineApiError


@dataclass(frozen=True)
class ReminderCandidate:
    task_id: str
    task_name: str
    owner_id: str
    due_at: str
    scheduled_at: str


def _parse(value: str, timezone: ZoneInfo) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def reminders_due(
    connection: sqlite3.Connection,
    now: datetime,
    *,
    timezone: str = "Asia/Tokyo",
    reminder_hour: int = 12,
) -> list[ReminderCandidate]:
    """Return open tasks whose previous-day noon reminder is due and unsent."""
    zone = ZoneInfo(timezone)
    current = now.astimezone(zone)
    rows = connection.execute(
        """
        SELECT task_id, name, owner_id, due_at
        FROM tasks
        WHERE status IN ('open', 'blocked')
          AND owner_id IS NOT NULL
          AND due_at IS NOT NULL
        ORDER BY due_at, task_id
        """
    ).fetchall()

    candidates: list[ReminderCandidate] = []
    for row in rows:
        due = _parse(row["due_at"], zone)
        scheduled = datetime.combine(
            due.date() - timedelta(days=1), time(reminder_hour), tzinfo=zone
        )
        key = f"{row['task_id']}:previous-day:{scheduled.isoformat()}"
        exists = connection.execute(
            """
            SELECT 1 FROM reminder_dispatches
            WHERE dispatch_key=? AND status IN ('sent', 'skipped')
            """,
            (key,),
        ).fetchone()
        if (
            scheduled.date() == current.date()
            and scheduled <= current < due
            and not exists
        ):
            candidates.append(
                ReminderCandidate(
                    task_id=row["task_id"],
                    task_name=row["name"],
                    owner_id=row["owner_id"],
                    due_at=due.isoformat(timespec="seconds"),
                    scheduled_at=scheduled.isoformat(timespec="seconds"),
                )
            )
    return candidates


class ReminderRunner:
    def __init__(
        self,
        *,
        database,
        push_client,
        group_id: str,
        timezone: str = "Asia/Tokyo",
        reminder_hour: int = 12,
        monthly_budget: int = 200,
        estimated_push_cost: int = 1,
    ):
        self.database = database
        self.push_client = push_client
        self.group_id = group_id
        self.timezone = timezone
        self.reminder_hour = reminder_hour
        self.monthly_budget = monthly_budget
        self.estimated_push_cost = estimated_push_cost

    def run(self, now: datetime) -> dict[str, int]:
        with self.database.session() as connection:
            candidates = reminders_due(
                connection,
                now,
                timezone=self.timezone,
                reminder_hour=self.reminder_hour,
            )
        result = {"candidates": len(candidates), "sent": 0, "skipped": 0, "failed": 0}
        if not candidates:
            return result
        try:
            quota = self.push_client.quota()
        except LineApiError:
            result["failed"] = len(candidates)
            for candidate in candidates:
                self._record(candidate, "failed", now, 0)
            return result

        effective_limit = self.monthly_budget
        if quota.limit is not None:
            effective_limit = min(effective_limit, quota.limit)
        projected_usage = quota.usage
        for candidate in candidates:
            if projected_usage + self.estimated_push_cost > effective_limit:
                self._record(candidate, "skipped", now, 0)
                result["skipped"] += 1
                continue
            retry_key = str(uuid.uuid5(uuid.NAMESPACE_URL, self._dispatch_key(candidate)))
            text = (
                f"，任务 {candidate.task_id}“{candidate.task_name}”将在明天截止，"
                "请确认当前进度。"
            )
            try:
                self.push_client.push_reminder(
                    self.group_id,
                    text,
                    candidate.owner_id,
                    retry_key=retry_key,
                )
            except LineApiError:
                self._record(candidate, "failed", now, 0)
                result["failed"] += 1
                continue
            projected_usage += self.estimated_push_cost
            self._record(candidate, "sent", now, self.estimated_push_cost)
            result["sent"] += 1
        return result

    @staticmethod
    def _dispatch_key(candidate: ReminderCandidate) -> str:
        return f"{candidate.task_id}:previous-day:{candidate.scheduled_at}"

    def _record(
        self, candidate: ReminderCandidate, status: str, now: datetime, quota_cost: int
    ) -> None:
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO reminder_dispatches (
                    dispatch_key, task_id, reminder_kind, scheduled_at,
                    status, sent_at, quota_cost
                ) VALUES (?, ?, 'previous-day', ?, ?, ?, ?)
                ON CONFLICT(dispatch_key) DO UPDATE SET
                    status=excluded.status,
                    sent_at=excluded.sent_at,
                    quota_cost=excluded.quota_cost
                """,
                (
                    self._dispatch_key(candidate),
                    candidate.task_id,
                    candidate.scheduled_at,
                    status,
                    now.isoformat(timespec="seconds") if status == "sent" else None,
                    quota_cost,
                ),
            )

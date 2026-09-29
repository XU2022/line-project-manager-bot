"""Language-neutral command orchestration."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from zoneinfo import ZoneInfo
from .locales import en as english_messages
from .parsers.en import EnglishCommandParser
from .tracker import TaskService

@dataclass(frozen=True)
class CommandResult:
    handled: bool
    text: str = ""

class CommandProcessor:
    def __init__(self, service: TaskService, *, default_due_hour: int = 18, parser=None, messages: ModuleType = english_messages):
        self.service = service
        self.default_due_hour = default_due_hour
        self.zone = ZoneInfo(service.timezone)
        self.parser = parser or EnglishCommandParser()
        self.messages = messages

    def handle(self, text: str, *, actor_id: str, reference: datetime | None = None) -> CommandResult:
        command = (text or "").strip()
        if not command:
            return CommandResult(False)
        if self.service.get_member(actor_id) is None:
            return CommandResult(True, self.messages.UNKNOWN_MEMBER)
        now = (reference or datetime.now(self.zone)).astimezone(self.zone)
        if self.parser.is_list(command):
            return CommandResult(True, self._list_tasks())
        if self.parser.is_create(command):
            return CommandResult(True, self._create(command, actor_id, now))
        task_id = self.parser.task_id(command)
        if not task_id:
            return CommandResult(False)
        if self.parser.wants_cancel(command):
            return CommandResult(True, self._set_status(task_id, actor_id, "cancelled"))
        if self.parser.wants_complete(command):
            return CommandResult(True, self._set_status(task_id, actor_id, "completed"))
        if self.parser.wants_update(command):
            return CommandResult(True, self._update(command, task_id, actor_id, now))
        return CommandResult(False)

    def _owner_id(self, command: str, actor_id: str) -> tuple[bool, str | bool | None]:
        mentioned, reference = self.parser.owner_reference(command)
        if not mentioned:
            return False, None
        if reference == "me":
            return True, actor_id
        member = self.service.find_member_by_name(reference or "")
        return True, member["member_id"] if member else False

    def _create(self, command: str, actor_id: str, now: datetime) -> str:
        name = self.parser.task_name(command)
        if not name:
            return self.messages.MISSING_NAME
        owner_mentioned, owner_id = self._owner_id(command, actor_id)
        if owner_id is False:
            return self.messages.UNKNOWN_OWNER
        try:
            due_at = self.parser.due_at(command, now, self.default_due_hour)
        except ValueError:
            return self.messages.INVALID_DUE
        try:
            task = self.service.create_task(name=name, created_by=actor_id, owner_id=owner_id if owner_mentioned else None, due_at=due_at, stage=self.parser.stage(command) or "planning")
        except (ValueError, KeyError):
            return self.messages.INCOMPLETE_TASK
        return self.messages.CREATED + "\n" + self._task_summary(task)

    def _update(self, command: str, task_id: str, actor_id: str, now: datetime) -> str:
        if self.service.get_task(task_id) is None:
            return self.messages.NOT_FOUND.format(task_id=task_id)
        if not self.service.can_modify_task(task_id, actor_id):
            return self.messages.FORBIDDEN
        owner_mentioned, owner_id = self._owner_id(command, actor_id)
        if owner_id is False:
            return self.messages.UNKNOWN_OWNER
        try:
            due_at = self.parser.due_at(command, now, self.default_due_hour)
        except ValueError:
            return self.messages.INVALID_DUE
        changes = {"stage": self.parser.stage(command), "due_at": due_at, "status": self.parser.status(command)}
        if owner_mentioned:
            changes["owner_id"] = owner_id
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return self.messages.NO_CHANGES
        task = self.service.update_task(task_id, actor_id=actor_id, **changes)
        return self.messages.UPDATED + "\n" + self._task_summary(task)

    def _set_status(self, task_id: str, actor_id: str, status: str) -> str:
        if self.service.get_task(task_id) is None:
            return self.messages.NOT_FOUND.format(task_id=task_id)
        if not self.service.can_modify_task(task_id, actor_id):
            return self.messages.FORBIDDEN
        task = self.service.update_task(task_id, actor_id=actor_id, status=status)
        return self.messages.STATUS_CHANGED.format(status=self.messages.STATUS_NAMES[status]) + "\n" + self._task_summary(task)

    def _list_tasks(self) -> str:
        tasks = self.service.list_tasks()
        if not tasks:
            return self.messages.NO_OPEN_TASKS
        lines = [self.messages.TASK_LIST.format(count=len(tasks))]
        shown = 0
        for task in tasks:
            summary = self._task_summary(task)
            suffix = "\n" + self.messages.MORE_TASKS.format(count=len(tasks) - shown - 1)
            if len("\n".join(lines + [summary, suffix])) > 4800:
                lines.append(self.messages.MORE_TASKS.format(count=len(tasks) - shown))
                break
            lines.append(summary)
            shown += 1
        return "\n".join(lines)

    def _task_summary(self, task) -> str:
        owner = self.messages.UNASSIGNED
        if task["owner_id"]:
            member = self.service.get_member(task["owner_id"])
            owner = member["display_name"] if member else self.messages.UNASSIGNED
        return self.messages.SUMMARY.format(task_id=task["task_id"], name=task["name"], owner=owner, stage=self.messages.STAGE_NAMES.get(task["stage"], task["stage"]), status=self.messages.STATUS_NAMES.get(task["status"], task["status"]), due=self._display_due(task["due_at"]))

    def _display_due(self, value: str | None) -> str:
        if not value:
            return self.messages.NO_DUE
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self.zone)
        return parsed.astimezone(self.zone).strftime("%Y-%m-%d %H:%M")

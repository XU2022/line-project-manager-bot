"""Small deterministic command layer for common Chinese task messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .tracker import TaskService


TASK_ID_RE = re.compile(r"\bTASK-\d{4,}\b", re.I)
QUOTED_NAME_RE = re.compile(r"[\"“「『](.+?)[\"”」』]")
FULL_DATE_RE = re.compile(
    r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?"
    r"(?:[ T　]*(\d{1,2})(?::|时)(\d{1,2})?分?)?"
)
SHORT_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})月(\d{1,2})日"
    r"(?:[ T　]*(\d{1,2})(?::|时)(\d{1,2})?分?)?"
)

STAGE_NAMES = {
    "planning": "规划",
    "execution": "执行",
    "review": "审核",
    "delivery": "交付",
}
STATUS_NAMES = {
    "open": "进行中",
    "blocked": "受阻",
    "completed": "已完成",
    "cancelled": "已取消",
}


@dataclass(frozen=True)
class CommandResult:
    handled: bool
    text: str = ""


class CommandProcessor:
    def __init__(self, service: TaskService, *, default_due_hour: int = 18):
        self.service = service
        self.default_due_hour = default_due_hour
        self.zone = ZoneInfo(service.timezone)

    def handle(
        self, text: str, *, actor_id: str, reference: datetime | None = None
    ) -> CommandResult:
        command = (text or "").strip()
        if not command:
            return CommandResult(False)
        actor = self.service.get_member(actor_id)
        if actor is None:
            return CommandResult(True, "你还不是已登记的项目成员。")
        now = (reference or datetime.now(self.zone)).astimezone(self.zone)

        if re.search(r"(?:查询|查看|列出|当前).{0,4}任务|任务列表", command):
            return CommandResult(True, self._list_tasks())
        if re.match(r"^(?:新增|创建)(?:一个)?任务", command):
            return CommandResult(True, self._create(command, actor_id, now))

        task_match = TASK_ID_RE.search(command)
        if not task_match:
            return CommandResult(False)
        task_id = task_match.group(0).upper()

        if re.search(r"取消|作废", command):
            return CommandResult(True, self._set_status(task_id, actor_id, "cancelled"))
        if re.search(r"完成|已完成", command):
            return CommandResult(True, self._set_status(task_id, actor_id, "completed"))
        if re.search(r"更新|修改|改为|负责人|截止|阶段|受阻|恢复", command):
            return CommandResult(True, self._update(command, task_id, actor_id, now))
        return CommandResult(False)

    def _create(self, command: str, actor_id: str, now: datetime) -> str:
        name = self._task_name(command)
        if not name:
            return "请给任务一个名称，例如：新增任务“演示任务”，由我负责。"
        owner_id = self._owner_id(command, actor_id)
        if owner_id is False:
            return "没有找到指定负责人，请先登记该成员。"
        try:
            due_at = self._due_at(command, now)
        except ValueError:
            return "截止时间无效，请检查年月日和时间。"
        stage = self._stage(command) or "planning"
        try:
            task = self.service.create_task(
                name=name,
                created_by=actor_id,
                owner_id=owner_id,
                due_at=due_at,
                stage=stage,
            )
        except (ValueError, KeyError):
            return "任务信息不完整，未建立任务。"
        return "已建立任务。\n" + self._task_summary(task)

    def _update(
        self, command: str, task_id: str, actor_id: str, now: datetime
    ) -> str:
        if self.service.get_task(task_id) is None:
            return f"没有找到任务 {task_id}。"
        if not self.service.can_modify_task(task_id, actor_id):
            return "你没有权限修改这个任务。"
        owner_id = self._owner_id(command, actor_id)
        if owner_id is False:
            return "没有找到指定负责人，请先登记该成员。"
        stage = self._stage(command)
        try:
            due_at = self._due_at(command, now)
        except ValueError:
            return "截止时间无效，请检查年月日和时间。"
        status = None
        if "受阻" in command or re.search(r"\bblocked\b", command, re.I):
            status = "blocked"
        elif "恢复" in command or "继续" in command:
            status = "open"

        changes = {
            "stage": stage,
            "due_at": due_at,
            "status": status,
        }
        if self._mentions_owner(command):
            changes["owner_id"] = owner_id
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return "没有识别到需要更新的阶段、负责人、截止时间或状态。"
        task = self.service.update_task(task_id, actor_id=actor_id, **changes)
        return "任务已更新。\n" + self._task_summary(task)

    def _set_status(self, task_id: str, actor_id: str, status: str) -> str:
        if self.service.get_task(task_id) is None:
            return f"没有找到任务 {task_id}。"
        if not self.service.can_modify_task(task_id, actor_id):
            return "你没有权限修改这个任务。"
        task = self.service.update_task(task_id, actor_id=actor_id, status=status)
        label = STATUS_NAMES[status]
        return f"任务已{label.removeprefix('已')}。\n" + self._task_summary(task)

    def _list_tasks(self) -> str:
        tasks = self.service.list_tasks()
        if not tasks:
            return "当前没有进行中的任务。"
        lines = [f"当前任务（{len(tasks)}项）："]
        shown = 0
        for task in tasks:
            summary = self._task_summary(task)
            suffix = f"\n还有{len(tasks) - shown - 1}项未显示。"
            if len("\n".join(lines + [summary, suffix])) > 4800:
                lines.append(f"还有{len(tasks) - shown}项未显示。")
                break
            lines.append(summary)
            shown += 1
        return "\n".join(lines)

    def _task_summary(self, task) -> str:
        owner = "待定"
        if task["owner_id"]:
            member = self.service.get_member(task["owner_id"])
            owner = member["display_name"] if member else "待定"
        stage = STAGE_NAMES.get(task["stage"], task["stage"])
        status = STATUS_NAMES.get(task["status"], task["status"])
        due = self._display_due(task["due_at"])
        return (
            f"{task['task_id']}｜{task['name']}\n"
            f"负责人：{owner}；阶段：{stage}；状态：{status}；截止：{due}"
        )

    @staticmethod
    def _task_name(command: str) -> str | None:
        quoted = QUOTED_NAME_RE.search(command)
        if quoted:
            return quoted.group(1).strip()
        remainder = re.sub(r"^(?:新增|创建)(?:一个)?任务[：:\s]*", "", command)
        candidate = re.split(
            r"[，,；;]|(?=由我负责|负责人|截止|DDL|阶段)", remainder, maxsplit=1
        )[0].strip()
        return candidate or None

    def _owner_id(self, command: str, actor_id: str) -> str | bool | None:
        if re.search(r"(?:由我负责|负责人(?:是|=|：|:)我)", command):
            return actor_id
        match = re.search(
            r"(?:负责人(?:改为|是|=|：|:)?|由)\s*"
            r"([A-Za-z0-9_\-\u4e00-\u9fff]+?)(?=负责|[，,；;]|截止|阶段|$)",
            command,
        )
        if not match:
            return None
        member = self.service.find_member_by_name(match.group(1))
        return member["member_id"] if member else False

    @staticmethod
    def _mentions_owner(command: str) -> bool:
        return "负责人" in command or bool(re.search(r"由.+?负责", command))

    @staticmethod
    def _stage(command: str) -> str | None:
        match = re.search(
            r"阶段(?:改为|调整为|是|=|：|:)?\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)",
            command,
        )
        if not match:
            return None
        value = match.group(1).strip()
        reverse = {label: key for key, label in STAGE_NAMES.items()}
        return reverse.get(value, value.lower())

    def _due_at(self, command: str, now: datetime) -> str | None:
        match = FULL_DATE_RE.search(command)
        if match:
            year, month, day, hour, minute = match.groups()
        else:
            match = SHORT_DATE_RE.search(command)
            if not match:
                return None
            month, day, hour, minute = match.groups()
            year = str(now.year)
        value = datetime(
            int(year),
            int(month),
            int(day),
            int(hour) if hour is not None else self.default_due_hour,
            int(minute or 0),
            tzinfo=self.zone,
        )
        if FULL_DATE_RE.search(command) is None and value <= now:
            value = value.replace(year=value.year + 1)
        return value.isoformat(timespec="seconds")

    def _display_due(self, value: str | None) -> str:
        if not value:
            return "待定"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self.zone)
        local = parsed.astimezone(self.zone)
        return f"{local.year}-{local.month:02d}-{local.day:02d} {local:%H:%M}"

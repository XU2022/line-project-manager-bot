"""Deterministic English task-command parser."""

from __future__ import annotations
import re
from datetime import datetime

TASK_ID_RE = re.compile(r"\bTASK-\d{4,}\b", re.I)
QUOTED_NAME_RE = re.compile(r'["\u201c](.+?)["\u201d]')
FULL_DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?:[ T]+(\d{1,2})(?::(\d{1,2}))?)?\b")
SHORT_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})(?:[ T]+(\d{1,2})(?::(\d{1,2}))?)?\b")

class EnglishCommandParser:
    locale = "en"

    @staticmethod
    def is_list(command: str) -> bool:
        return bool(re.search(r"\b(?:list|show|view)(?:\s+(?:current|active))?\s+tasks?\b", command, re.I))

    @staticmethod
    def is_create(command: str) -> bool:
        return bool(re.match(r"^(?:create|add)(?:\s+a)?\s+task\b", command, re.I))

    @staticmethod
    def task_id(command: str) -> str | None:
        match = TASK_ID_RE.search(command)
        return match.group(0).upper() if match else None

    @staticmethod
    def wants_cancel(command: str) -> bool:
        return bool(re.search(r"\b(?:cancel|discard)\b", command, re.I))

    @staticmethod
    def wants_complete(command: str) -> bool:
        return bool(re.search(r"\b(?:complete|completed|done)\b", command, re.I))

    @staticmethod
    def wants_update(command: str) -> bool:
        return bool(re.search(r"\b(?:update|change|owner|due|stage|blocked|resume|reopen)\b", command, re.I))

    @staticmethod
    def task_name(command: str) -> str | None:
        quoted = QUOTED_NAME_RE.search(command)
        if quoted:
            return quoted.group(1).strip()
        remainder = re.sub(r"^(?:create|add)(?:\s+a)?\s+task\s*[:\s]*", "", command, flags=re.I)
        candidate = re.split(r"[,;]|(?=\bowner\b|\bdue\b|\bstage\b)", remainder, maxsplit=1, flags=re.I)[0].strip()
        return candidate or None

    @staticmethod
    def owner_reference(command: str) -> tuple[bool, str | None]:
        if re.search(r"\bowner\s*(?:is|=|:)?\s*me\b", command, re.I):
            return True, "me"
        match = re.search(r"\bowner\s*(?:to|is|=|:)?\s*([A-Za-z0-9_-]+)(?=\s*(?:[,;]|\bdue\b|\bstage\b|$))", command, re.I)
        return (True, match.group(1)) if match else (False, None)

    @staticmethod
    def stage(command: str) -> str | None:
        match = re.search(r"\bstage\s*(?:to|is|=|:)?\s*([A-Za-z0-9_-]+)", command, re.I)
        return match.group(1).lower() if match else None

    @staticmethod
    def status(command: str) -> str | None:
        if re.search(r"\bblocked\b", command, re.I):
            return "blocked"
        if re.search(r"\b(?:resume|reopen)\b", command, re.I):
            return "open"
        return None

    @staticmethod
    def due_at(command: str, now: datetime, default_hour: int) -> str | None:
        match = FULL_DATE_RE.search(command)
        full_date = match is not None
        if match:
            year, month, day, hour, minute = match.groups()
        else:
            match = SHORT_DATE_RE.search(command)
            if not match:
                return None
            month, day, hour, minute = match.groups()
            year = str(now.year)
        value = datetime(int(year), int(month), int(day), int(hour) if hour is not None else default_hour, int(minute or 0), tzinfo=now.tzinfo)
        if not full_date and value <= now:
            value = value.replace(year=value.year + 1)
        return value.isoformat(timespec="seconds")

CommandParser = EnglishCommandParser

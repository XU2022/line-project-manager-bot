"""Runtime configuration loaded exclusively from environment and local JSON."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class MemberConfig:
    member_id: str
    display_name: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeConfig:
    channel_secret: str = field(repr=False)
    channel_access_token: str = field(repr=False)
    allowed_group_ids: tuple[str, ...]
    database_path: Path
    member_config_path: Path
    host: str = "127.0.0.1"
    port: int = 8646
    timezone: str = "Asia/Tokyo"
    max_body_bytes: int = 1_048_576
    reminder_group_id: str = ""
    reminder_hour: int = 12
    monthly_message_limit: int = 200
    estimated_push_cost: int = 1
    bootstrap_mode: bool = False
    fallback_trigger_letter: str = "H"

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> "RuntimeConfig":
        env = environment if environment is not None else os.environ
        required = {
            "LINE_CHANNEL_SECRET": env.get("LINE_CHANNEL_SECRET", "").strip(),
            "LINE_CHANNEL_ACCESS_TOKEN": env.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip(),
            "LINE_ALLOWED_GROUPS": env.get("LINE_ALLOWED_GROUPS", "").strip(),
            "PROJECT_DB_PATH": env.get("PROJECT_DB_PATH", "").strip(),
            "MEMBER_CONFIG_PATH": env.get("MEMBER_CONFIG_PATH", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigError("missing required settings: " + ", ".join(missing))
        try:
            port = int(env.get("LINE_PORT", "8646"))
            max_body_bytes = int(env.get("MAX_WEBHOOK_BODY_BYTES", "1048576"))
            reminder_hour = int(env.get("REMINDER_HOUR", "12"))
            monthly_message_limit = int(env.get("MONTHLY_MESSAGE_LIMIT", "200"))
            estimated_push_cost = int(env.get("ESTIMATED_PUSH_COST", "1"))
        except ValueError as exc:
            raise ConfigError("LINE_PORT and MAX_WEBHOOK_BODY_BYTES must be integers") from exc
        if not 1 <= port <= 65535:
            raise ConfigError("LINE_PORT must be between 1 and 65535")
        if not 0 <= reminder_hour <= 23:
            raise ConfigError("REMINDER_HOUR must be between 0 and 23")
        if monthly_message_limit < 1 or estimated_push_cost < 1:
            raise ConfigError("message limits and costs must be positive")
        groups = tuple(
            item.strip() for item in required["LINE_ALLOWED_GROUPS"].split(",") if item.strip()
        )
        if not groups:
            raise ConfigError("LINE_ALLOWED_GROUPS must contain at least one group ID")
        bootstrap_mode = env.get("LINE_BOOTSTRAP_MODE", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if any(group != "*" and not group.startswith("C") for group in groups):
            raise ConfigError("LINE_ALLOWED_GROUPS entries must start with C or be *")
        if bootstrap_mode and "*" not in groups:
            raise ConfigError("bootstrap mode requires LINE_ALLOWED_GROUPS=*")
        if not bootstrap_mode and "*" in groups:
            raise ConfigError("LINE_ALLOWED_GROUPS=* is only allowed in bootstrap mode")
        timezone = env.get("PROJECT_TIMEZONE", "Asia/Tokyo").strip() or "Asia/Tokyo"
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(f"unknown PROJECT_TIMEZONE: {timezone}") from exc
        reminder_group = env.get("LINE_REMINDER_GROUP_ID", "").strip() or groups[0]
        if reminder_group not in groups:
            raise ConfigError("LINE_REMINDER_GROUP_ID must be an allowed group")
        fallback_trigger_letter = env.get("LINE_FALLBACK_TRIGGER_LETTER", "H").strip()
        if not re.fullmatch(r"[A-Za-z]", fallback_trigger_letter):
            raise ConfigError(
                "LINE_FALLBACK_TRIGGER_LETTER must be one ASCII letter"
            )
        return cls(
            channel_secret=required["LINE_CHANNEL_SECRET"],
            channel_access_token=required["LINE_CHANNEL_ACCESS_TOKEN"],
            allowed_group_ids=groups,
            database_path=Path(required["PROJECT_DB_PATH"]),
            member_config_path=Path(required["MEMBER_CONFIG_PATH"]),
            host=env.get("LINE_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=port,
            timezone=timezone,
            max_body_bytes=max_body_bytes,
            reminder_group_id=reminder_group,
            reminder_hour=reminder_hour,
            monthly_message_limit=monthly_message_limit,
            estimated_push_cost=estimated_push_cost,
            bootstrap_mode=bootstrap_mode,
            fallback_trigger_letter=fallback_trigger_letter.upper(),
        )


def load_members(path: str | Path) -> list[MemberConfig]:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"member configuration not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError("member configuration is not valid JSON") from exc
    raw_members = payload.get("members")
    if not isinstance(raw_members, dict) or not raw_members:
        raise ConfigError("member configuration must contain a non-empty members object")
    members: list[MemberConfig] = []
    for member_id, details in raw_members.items():
        if not isinstance(details, dict):
            raise ConfigError(f"invalid member entry: {member_id}")
        display_name = str(details.get("display_name", "")).strip()
        roles = details.get("roles", [])
        if not member_id or not display_name or not isinstance(roles, list):
            raise ConfigError(f"invalid member entry: {member_id}")
        members.append(
            MemberConfig(
                member_id=member_id,
                display_name=display_name,
                roles=tuple(str(role) for role in roles),
            )
        )
    return members

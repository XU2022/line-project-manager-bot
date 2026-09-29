"""Run one reminder scan; intended for a systemd timer."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import ConfigError, RuntimeConfig
from .database import Database
from .line_gateway import LinePushClient
from .language import load_language
from .reminders import ReminderRunner


def main() -> None:
    try:
        config = RuntimeConfig.from_env()
    except ConfigError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc
    if config.bootstrap_mode:
        raise SystemExit("configuration error: reminders are disabled in bootstrap mode")
    database = Database(config.database_path)
    database.initialize_default()
    _, messages = load_language(config.bot_locale)
    runner = ReminderRunner(
        database=database,
        push_client=LinePushClient(config.channel_access_token),
        group_id=config.reminder_group_id,
        timezone=config.timezone,
        reminder_hour=config.reminder_hour,
        monthly_budget=config.monthly_message_limit,
        estimated_push_cost=config.estimated_push_cost,
        messages=messages,
    )
    result = runner.run(datetime.now(ZoneInfo(config.timezone)))
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()

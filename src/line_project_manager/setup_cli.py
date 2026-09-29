"""Initialize and validate a local runtime without contacting LINE."""

from __future__ import annotations

from .config import ConfigError, RuntimeConfig, load_members
from .database import Database
from .tracker import TaskService


def main() -> None:
    try:
        config = RuntimeConfig.from_env()
        members = load_members(config.member_config_path)
    except ConfigError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc
    database = Database(config.database_path)
    database.initialize_default()
    service = TaskService(database, timezone=config.timezone)
    for member in members:
        service.register_member(member.member_id, member.display_name, member.roles)
    print(f"ready: database initialized; {len(members)} members registered")


if __name__ == "__main__":
    main()

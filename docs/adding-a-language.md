# Adding a language

The bot ships with English but keeps language-specific parsing and messages outside the core.

1. Copy `src/line_project_manager/parsers/en.py` to `parsers/<locale>.py`.
2. Translate command patterns and keep the exported `CommandParser` class.
3. Copy `src/line_project_manager/locales/en.py` to `locales/<locale>.py`.
4. Translate every message while preserving format fields such as `{task_id}`.
5. Add parser, command, reply, and reminder tests for the locale.
6. Set `BOT_LOCALE=<locale>` and restart the webhook service.

Do not translate database values such as `open`, `blocked`, `completed`, and `cancelled`; translate only their displayed labels. LINE gating, storage, permissions, quota handling, and reminder scheduling should remain unchanged.


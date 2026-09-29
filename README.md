# LINE Project Manager Bot

Lightweight project management for LINE group chats. It uses deterministic task commands, ignores ordinary conversation, and is not tied to a specific industry.

## Features

- Verifies LINE webhook signatures with HMAC-SHA256
- Restricts access to approved groups and members
- Uses real bot mentions by default, with a configurable letter fallback
- Creates, updates, completes, cancels, and lists generic tasks
- Stores tasks, members, events, and reminders in SQLite
- Allows only owners, creators, or administrators to modify tasks
- Reminds owners at noon on the day before a deadline
- Uses Reply for commands and Push only for scheduled reminders
- Checks LINE monthly usage and enforces a local message budget
- Deduplicates webhook deliveries and reminders
- Includes systemd, Nginx, HTTPS, and GitHub Actions examples

## How it works

```text
LINE group message
  → HTTPS webhook
  → signature verification
  → group and member allowlists
  → real @bot mention (custom letter fallback)
  → deterministic task command
  → SQLite
  → one Reply

systemd timer
  → find tasks due tomorrow
  → check LINE usage and local budget
  → one Push mentioning the owner
```

## Requirements

- Python 3.11 or later
- A LINE Official Account and Messaging API channel
- A public HTTPS webhook URL
- systemd and Nginx are recommended for Linux deployments

Runtime code uses only the Python standard library.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
```

Copy the example configuration. Never commit files containing real IDs:

```bash
cp config/members.example.json config/members.json
cp .env.example .env
```

The application does not load `.env` automatically. Export it into the current shell for local use; systemd uses `EnvironmentFile`.

Initialize the database:

```bash
set -a
. ./.env
set +a
line-project-init
```

Start the service:

```bash
line-project-bot
```

Check local health:

```bash
curl http://127.0.0.1:8646/healthz
```

See the [deployment guide](docs/deployment.md) for production instructions.

If you do not yet know the group and member IDs, follow the one-time bootstrap procedure in [LINE account setup](docs/line-account-setup.md).

## Command examples

```text
@Bot create task "Demo task", owner me, due 10-15
@Bot update TASK-0001, stage review
@Bot complete TASK-0001
@Bot cancel TASK-0001
@Bot list tasks
```

If a LINE client cannot mention the bot, set `LINE_FALLBACK_TRIGGER_LETTER`. With `P`, for example, use `P: list tasks`. The fallback works only at the start of a message.

See [commands](docs/commands.md) for the full syntax.

## Project structure

```text
config/       sanitized examples and Nginx template
docs/         LINE setup, commands, and deployment
migrations/   inspectable SQLite schema
src/          installable Python package
systemd/      webhook service and reminder timer
tests/        unit, integration, quota, and privacy tests
```

## Privacy and security

The repository contains only fictional members, tasks, and LINE identifiers. Never commit:

- Channel secrets or access tokens
- Real user, group, or room IDs
- Production databases, event records, or server logs
- Real chat screenshots or project material
- Private domains, IP addresses, or account paths

`.env`, `config/members.json`, databases, and logs are excluded by `.gitignore`. See [SECURITY.md](SECURITY.md).

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

Tests cover signature verification, message gating, permissions, task lifecycle, deduplication, quota protection, configuration, packaged schema, and public safety.

## Language extensions

English is bundled as the default locale. To add a language, create matching `parsers/<locale>.py` and `locales/<locale>.py` modules, add tests, then set `BOT_LOCALE=<locale>`. Core storage, permissions, reminders, and LINE integration do not need to change. See [adding a language](docs/adding-a-language.md).

## Status

This project is currently `0.1.0`. Validate it in a test group and test server before production use.

## License

Licensed under the [MIT License](LICENSE).

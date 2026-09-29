# Changelog

## Unreleased

- Changed the public project, bot responses, examples, and documentation to English.
- Split language-specific command parsing and messages into extensible locale modules.
- Added `BOT_LOCALE`, with English bundled as the default language.
- Added an automated check that rejects CJK text and file names from the public package.

## 0.1.0 - 2026-09-29

- Added LINE webhook signature verification and group/member allowlists.
- Added structured bot mentions as the primary gate and a configurable single-letter fallback.
- Added generic SQLite task, member, event, and reminder storage.
- Added deterministic task create, update, complete, cancel, and query commands.
- Added previous-day reminder Push with deduplication and quota protection.
- Added HTTP health and webhook endpoints.
- Added systemd, Nginx, environment, and member configuration examples.
- Added package, integration, privacy, and reminder tests.

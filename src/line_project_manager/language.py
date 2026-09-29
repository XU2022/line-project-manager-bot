"""Load a parser and message catalog without coupling them to the core."""

from __future__ import annotations
from importlib import import_module

def load_language(locale: str):
    """Load ``parsers.<locale>.CommandParser`` and ``locales.<locale>``.

    A new language only needs those two modules plus tests; task storage,
    permissions, reminders, and LINE integration remain unchanged.
    """
    normalized = locale.strip().lower().replace("-", "_")
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError("invalid bot locale")
    parser_module = import_module(f"line_project_manager.parsers.{normalized}")
    messages = import_module(f"line_project_manager.locales.{normalized}")
    return parser_module.CommandParser(), messages

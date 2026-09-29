from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from line_project_manager.config import ConfigError, RuntimeConfig, load_members
from line_project_manager.server import WebhookService


class FakeApplication:
    def process_webhook(self, raw_body: bytes, signature: str):
        self.received = (raw_body, signature)
        return [type("Reply", (), {"reply_token": "token", "text": "ok", "event_id": "event"})()]


class FakeReplyClient:
    def __init__(self):
        self.calls = []

    def reply_text(self, reply_token: str, text: str):
        self.calls.append((reply_token, text))
        return "request-id"


class ConfigAndServerTest(unittest.TestCase):
    def test_runtime_config_requires_all_secrets_and_paths(self) -> None:
        with self.assertRaises(ConfigError):
            RuntimeConfig.from_env({})

        config = RuntimeConfig.from_env(
            {
                "LINE_CHANNEL_SECRET": "secret",
                "LINE_CHANNEL_ACCESS_TOKEN": "token",
                "LINE_ALLOWED_GROUPS": "C_EXAMPLE_ONE,C_EXAMPLE_TWO",
                "PROJECT_DB_PATH": "/tmp/example/tasks.sqlite3",
                "MEMBER_CONFIG_PATH": "/tmp/example/members.json",
                "LINE_PORT": "9000",
                "LINE_FALLBACK_TRIGGER_LETTER": "p",
            }
        )
        self.assertEqual(config.allowed_group_ids, ("C_EXAMPLE_ONE", "C_EXAMPLE_TWO"))
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.fallback_trigger_letter, "P")
        self.assertNotIn("secret", repr(config))
        self.assertNotIn("token", repr(config))

    def test_fallback_trigger_must_be_one_ascii_letter(self) -> None:
        base = {
            "LINE_CHANNEL_SECRET": "secret",
            "LINE_CHANNEL_ACCESS_TOKEN": "token",
            "LINE_ALLOWED_GROUPS": "C_EXAMPLE_GROUP",
            "PROJECT_DB_PATH": "/tmp/example/tasks.sqlite3",
            "MEMBER_CONFIG_PATH": "/tmp/example/members.json",
            "LINE_FALLBACK_TRIGGER_LETTER": "任务",
        }
        with self.assertRaises(ConfigError):
            RuntimeConfig.from_env(base)

    def test_wildcard_group_requires_explicit_bootstrap_mode(self) -> None:
        base = {
            "LINE_CHANNEL_SECRET": "secret",
            "LINE_CHANNEL_ACCESS_TOKEN": "token",
            "LINE_ALLOWED_GROUPS": "*",
            "PROJECT_DB_PATH": "/tmp/example/tasks.sqlite3",
            "MEMBER_CONFIG_PATH": "/tmp/example/members.json",
        }
        with self.assertRaises(ConfigError):
            RuntimeConfig.from_env(base)
        enabled = dict(base, LINE_BOOTSTRAP_MODE="true")
        config = RuntimeConfig.from_env(enabled)
        self.assertTrue(config.bootstrap_mode)

    def test_member_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.json"
            path.write_text(
                json.dumps(
                    {
                        "members": {
                            "U_EXAMPLE_ALICE": {
                                "display_name": "Alice",
                                "roles": ["admin"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            members = load_members(path)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].display_name, "Alice")

    def test_webhook_service_delivers_generated_reply(self) -> None:
        application = FakeApplication()
        client = FakeReplyClient()
        service = WebhookService(application, client)
        delivered = service.process(b"body", "signature")
        self.assertEqual(delivered, 1)
        self.assertEqual(client.calls, [("token", "ok")])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from line_project_manager import (
    BotApplication,
    CommandProcessor,
    Database,
    GateConfig,
    TaskService,
)
from line_project_manager.line_gateway import webhook_signature


SECRET = "example-channel-secret-for-tests"
GROUP = "C_EXAMPLE_GROUP"
MEMBER = "U_EXAMPLE_ALICE"


def webhook(text: str, *, event_id: str = "example-event", mention: bool = False) -> bytes:
    message = {"id": f"message-{event_id}", "type": "text", "text": text}
    if mention:
        message["mention"] = {
            "mentionees": [
                {
                    "index": 0,
                    "length": 11,
                    "type": "user",
                    "userId": "U_EXAMPLE_BOT",
                    "isSelf": True,
                }
            ]
        }
    payload = {
        "destination": "U_EXAMPLE_BOT",
        "events": [
            {
                "type": "message",
                "webhookEventId": event_id,
                "deliveryContext": {"isRedelivery": False},
                "replyToken": f"reply-{event_id}",
                "source": {"type": "group", "groupId": GROUP, "userId": MEMBER},
                "message": message,
            }
        ],
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class ApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "tasks.sqlite3")
        self.database.initialize_default()
        self.service = TaskService(self.database)
        self.service.register_member(MEMBER, "Alice", ["admin"])
        processor = CommandProcessor(self.service)
        self.application = BotApplication(
            database=self.database,
            command_processor=processor,
            gate_config=GateConfig.create(
                allowed_group_ids=[GROUP], allowed_member_ids=[MEMBER]
            ),
            channel_secret=SECRET,
        )
        self.reference = datetime(2026, 10, 1, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def process(self, body: bytes):
        return self.application.process_webhook(
            body,
            webhook_signature(body, SECRET),
            reference=self.reference,
        )

    def test_end_to_end_create_returns_one_reply(self) -> None:
        body = webhook('H: create task "Demo task", owner me, due 10-15')
        replies = self.process(body)
        self.assertEqual(len(replies), 1)
        self.assertIn("TASK-0001", replies[0].text)
        self.assertEqual(len(self.service.list_tasks()), 1)

    def test_redelivery_does_not_repeat_operation_or_reply(self) -> None:
        body = webhook('H: create task "Demo task", owner me')
        self.assertEqual(len(self.process(body)), 1)
        self.assertEqual(self.process(body), [])
        self.assertEqual(len(self.service.list_tasks()), 1)

    def test_untriggered_chat_is_silent(self) -> None:
        self.assertEqual(self.process(webhook("ordinary group chat")), [])

    def test_structured_mention_reaches_command_processor(self) -> None:
        body = webhook(
            '@ExampleBot create task "Demo task", owner me',
            event_id="mention-event",
            mention=True,
        )
        replies = self.process(body)
        self.assertEqual(len(replies), 1)
        self.assertIn("TASK-0001", replies[0].text)

    def test_bootstrap_mode_returns_ids_without_creating_task(self) -> None:
        bootstrap = BotApplication(
            database=self.database,
            command_processor=CommandProcessor(self.service),
            gate_config=GateConfig.create(allowed_group_ids=["*"]),
            channel_secret=SECRET,
            bootstrap_mode=True,
        )
        body = webhook("H: identity", event_id="bootstrap-event")
        replies = bootstrap.process_webhook(
            body,
            webhook_signature(body, SECRET),
            reference=self.reference,
        )
        self.assertEqual(len(replies), 1)
        self.assertIn(GROUP, replies[0].text)
        self.assertIn(MEMBER, replies[0].text)
        self.assertEqual(self.service.list_tasks(), [])


if __name__ == "__main__":
    unittest.main()

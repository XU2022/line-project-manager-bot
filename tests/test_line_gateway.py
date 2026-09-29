from __future__ import annotations

import json
import unittest

from line_project_manager import (
    GateConfig,
    InvalidSignature,
    accepted_messages,
)
from line_project_manager.line_gateway import webhook_signature


SECRET = "example-channel-secret-for-tests"
GROUP = "C_EXAMPLE_GROUP"
MEMBER = "U_EXAMPLE_ALICE"


def body_for(text: str, *, mention: bool = False, group: str = GROUP) -> bytes:
    message = {"id": "example-message", "type": "text", "text": text}
    if mention:
        message["mention"] = {
            "mentionees": [
                {
                    "index": 0,
                    "length": 12,
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
                "webhookEventId": "example-event",
                "deliveryContext": {"isRedelivery": False},
                "replyToken": "example-reply-token",
                "source": {"type": "group", "groupId": group, "userId": MEMBER},
                "message": message,
            }
        ],
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class LineGatewayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = GateConfig.create(
            allowed_group_ids=[GROUP], allowed_member_ids=[MEMBER]
        )

    def accept(self, body: bytes):
        return accepted_messages(
            body, webhook_signature(body, SECRET), SECRET, self.config
        )

    def test_prefix_at_start_is_accepted_and_removed(self) -> None:
        accepted = self.accept(body_for(" H：新增任务 Demo"))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].text, "新增任务 Demo")
        self.assertEqual(accepted[0].trigger, "fallback_prefix")

    def test_prefix_in_middle_is_not_a_trigger(self) -> None:
        self.assertEqual(self.accept(body_for("聊天内容 H：新增任务 Demo")), [])

    def test_structured_self_mention_is_accepted(self) -> None:
        accepted = self.accept(body_for("@ExampleBot 新增任务 Demo", mention=True))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].trigger, "mention")
        self.assertEqual(accepted[0].text, "新增任务 Demo")

    def test_custom_fallback_letter_replaces_default(self) -> None:
        self.config = GateConfig.create(
            allowed_group_ids=[GROUP],
            allowed_member_ids=[MEMBER],
            fallback_trigger_letter="P",
        )
        accepted = self.accept(body_for("p：查询当前任务"))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].text, "查询当前任务")
        self.assertEqual(accepted[0].trigger, "fallback_prefix")
        self.assertEqual(self.accept(body_for("H：查询当前任务")), [])

    def test_mention_has_priority_over_fallback_prefix(self) -> None:
        accepted = self.accept(body_for("@ExampleBot 查询当前任务", mention=True))
        self.assertEqual(accepted[0].trigger, "mention")

    def test_invalid_fallback_letter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GateConfig.create(
                allowed_group_ids=[GROUP], fallback_trigger_letter="TASK"
            )

    def test_ordinary_chat_and_other_group_are_ignored(self) -> None:
        self.assertEqual(self.accept(body_for("ordinary chat")), [])
        self.assertEqual(self.accept(body_for("H: task", group="C_OTHER_GROUP")), [])

    def test_invalid_signature_is_rejected_before_parsing(self) -> None:
        with self.assertRaises(InvalidSignature):
            accepted_messages(b"not-json", "invalid", SECRET, self.config)


if __name__ == "__main__":
    unittest.main()

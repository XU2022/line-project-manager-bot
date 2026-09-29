"""Application orchestration from verified LINE webhook to one reply instruction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from zoneinfo import ZoneInfo

from .command_processor import CommandProcessor
from .locales import en as english_messages
from .database import Database
from .line_gateway import GateConfig, accepted_messages


@dataclass(frozen=True)
class ReplyInstruction:
    reply_token: str
    text: str
    event_id: str


class BotApplication:
    def __init__(
        self,
        *,
        database: Database,
        command_processor: CommandProcessor,
        gate_config: GateConfig,
        channel_secret: str,
        timezone: str = "Asia/Tokyo",
        bootstrap_mode: bool = False,
        messages: ModuleType = english_messages,
    ):
        self.database = database
        self.command_processor = command_processor
        self.gate_config = gate_config
        self.channel_secret = channel_secret
        self.timezone = ZoneInfo(timezone)
        self.bootstrap_mode = bootstrap_mode
        self.messages = messages

    def process_webhook(
        self, raw_body: bytes, signature: str, *, reference: datetime | None = None
    ) -> list[ReplyInstruction]:
        messages = accepted_messages(
            raw_body, signature, self.channel_secret, self.gate_config
        )
        replies: list[ReplyInstruction] = []
        now = (reference or datetime.now(self.timezone)).astimezone(self.timezone)
        for message in messages:
            if not message.event_id or not message.reply_token:
                continue
            if not self._claim_event(message.event_id, now):
                continue
            if self.bootstrap_mode:
                if message.text.strip().lower() in {"identity", "show identity"}:
                    text = self.messages.BOOTSTRAP_INFO.format(
                        group_id=message.group_id, member_id=message.member_id
                    )
                else:
                    text = self.messages.BOOTSTRAP_ONLY
                replies.append(
                    ReplyInstruction(
                        reply_token=message.reply_token,
                        text=text,
                        event_id=message.event_id,
                    )
                )
                continue
            result = self.command_processor.handle(
                message.text, actor_id=message.member_id, reference=now
            )
            if not result.handled:
                text = self.messages.UNKNOWN_OPERATION
            else:
                text = result.text
            if text:
                replies.append(
                    ReplyInstruction(
                        reply_token=message.reply_token,
                        text=text,
                        event_id=message.event_id,
                    )
                )
        return replies

    def _claim_event(self, event_id: str, now: datetime) -> bool:
        with self.database.session() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO webhook_events (event_id, processed_at)
                VALUES (?, ?)
                """,
                (event_id, now.isoformat(timespec="seconds")),
            )
            return result.rowcount == 1

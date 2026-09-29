"""Application orchestration from verified LINE webhook to one reply instruction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .commands import CommandProcessor
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
    ):
        self.database = database
        self.command_processor = command_processor
        self.gate_config = gate_config
        self.channel_secret = channel_secret
        self.timezone = ZoneInfo(timezone)
        self.bootstrap_mode = bootstrap_mode

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
                if message.text.strip() in {"身份", "查看身份", "identity"}:
                    text = (
                        f"群组ID：{message.group_id}\n"
                        f"成员ID：{message.member_id}\n"
                        "请保存到服务器的本地配置，随后关闭引导模式。"
                    )
                else:
                    text = "当前处于引导模式，只接受“身份”命令。"
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
                text = "没有识别到任务操作。可以使用：新增任务、更新任务、完成、取消或查询任务。"
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

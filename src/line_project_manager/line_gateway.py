"""Small LINE Messaging API boundary with strict webhook gating."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
QUOTA_ENDPOINT = "https://api.line.me/v2/bot/message/quota"
USAGE_ENDPOINT = "https://api.line.me/v2/bot/message/quota/consumption"


class InvalidSignature(ValueError):
    """Raised when a webhook signature is missing or invalid."""


class LineApiError(RuntimeError):
    """Raised when LINE rejects a reply request."""


@dataclass(frozen=True)
class GateConfig:
    allowed_group_ids: frozenset[str]
    allowed_member_ids: frozenset[str] = frozenset()
    command_prefixes: tuple[str, ...] = ("H:", "H：", "h:", "h：")
    allow_bot_mention: bool = True

    @classmethod
    def create(
        cls,
        *,
        allowed_group_ids: Iterable[str],
        allowed_member_ids: Iterable[str] = (),
        fallback_trigger_letter: str = "H",
    ) -> "GateConfig":
        letter = fallback_trigger_letter.strip()
        if len(letter) != 1 or not letter.isascii() or not letter.isalpha():
            raise ValueError("fallback trigger must be one ASCII letter")
        upper = letter.upper()
        lower = letter.lower()
        return cls(
            allowed_group_ids=frozenset(allowed_group_ids),
            allowed_member_ids=frozenset(allowed_member_ids),
            command_prefixes=(f"{upper}:", f"{upper}：", f"{lower}:", f"{lower}："),
        )


@dataclass(frozen=True)
class AcceptedMessage:
    event_id: str
    group_id: str
    member_id: str
    reply_token: str
    text: str
    trigger: str
    is_redelivery: bool


def webhook_signature(raw_body: bytes, channel_secret: str) -> str:
    digest = hmac.new(
        channel_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_signature(raw_body: bytes, signature: str, channel_secret: str) -> None:
    if not signature or not channel_secret:
        raise InvalidSignature("missing webhook signature or channel secret")
    expected = webhook_signature(raw_body, channel_secret)
    if not hmac.compare_digest(signature, expected):
        raise InvalidSignature("invalid webhook signature")


def _has_self_mention(message: dict[str, Any]) -> bool:
    mention = message.get("mention") or {}
    mentionees = mention.get("mentionees") or []
    return any(
        item.get("type") == "user" and item.get("isSelf") is True
        for item in mentionees
        if isinstance(item, dict)
    )


def _without_self_mentions(message: dict[str, Any], text: str) -> str:
    mention = message.get("mention") or {}
    spans: list[tuple[int, int]] = []
    for item in mention.get("mentionees") or []:
        if not isinstance(item, dict) or item.get("isSelf") is not True:
            continue
        index = item.get("index")
        length = item.get("length")
        if isinstance(index, int) and isinstance(length, int) and index >= 0 and length > 0:
            spans.append((index, length))
    result = text
    for index, length in sorted(spans, reverse=True):
        if index <= len(result):
            result = result[:index] + result[index + length :]
    return result.strip()


def _prefixed_text(text: str, prefixes: tuple[str, ...]) -> str | None:
    stripped = text.lstrip()
    for prefix in prefixes:
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].lstrip()
    return None


def accepted_messages(
    raw_body: bytes,
    signature: str,
    channel_secret: str,
    config: GateConfig,
) -> list[AcceptedMessage]:
    """Verify the raw request first, then return only explicitly triggered events."""
    verify_signature(raw_body, signature, channel_secret)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("webhook body is not valid UTF-8 JSON") from exc

    accepted: list[AcceptedMessage] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict) or event.get("type") != "message":
            continue
        message = event.get("message") or {}
        source = event.get("source") or {}
        if message.get("type") != "text" or source.get("type") != "group":
            continue

        group_id = source.get("groupId", "")
        member_id = source.get("userId", "")
        if "*" not in config.allowed_group_ids and group_id not in config.allowed_group_ids:
            continue
        if config.allowed_member_ids and member_id not in config.allowed_member_ids:
            continue

        text = message.get("text", "")
        if config.allow_bot_mention and _has_self_mention(message):
            command_text = _without_self_mentions(message, text)
            trigger = "mention"
        else:
            command_text = _prefixed_text(text, config.command_prefixes)
            trigger = "fallback_prefix"
            if command_text is None:
                continue
        if not command_text:
            continue

        accepted.append(
            AcceptedMessage(
                event_id=event.get("webhookEventId", ""),
                group_id=group_id,
                member_id=member_id,
                reply_token=event.get("replyToken", ""),
                text=command_text,
                trigger=trigger,
                is_redelivery=bool(
                    (event.get("deliveryContext") or {}).get("isRedelivery", False)
                ),
            )
        )
    return accepted


class LineReplyClient:
    def __init__(self, access_token: str, *, timeout: float = 30.0):
        if not access_token:
            raise ValueError("access token is required")
        self._access_token = access_token
        self._timeout = timeout

    def reply_text(self, reply_token: str, text: str) -> str:
        if not reply_token:
            raise ValueError("reply token is required")
        if not text or len(text) > 5000:
            raise ValueError("reply text must contain 1 to 5000 characters")
        payload = json.dumps(
            {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            REPLY_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.headers.get("X-Line-Request-Id", "")
        except urllib.error.HTTPError as exc:
            raise LineApiError(f"LINE reply failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LineApiError("LINE reply service is unavailable") from exc


@dataclass(frozen=True)
class LineQuota:
    limit: int | None
    usage: int


class LinePushClient:
    def __init__(self, access_token: str, *, timeout: float = 30.0):
        if not access_token:
            raise ValueError("access token is required")
        self._access_token = access_token
        self._timeout = timeout

    def quota(self) -> LineQuota:
        limit_payload = self._request(QUOTA_ENDPOINT)
        usage_payload = self._request(USAGE_ENDPOINT)
        limit = (
            int(limit_payload["value"])
            if limit_payload.get("type") == "limited"
            else None
        )
        return LineQuota(limit=limit, usage=int(usage_payload.get("totalUsage", 0)))

    def push_reminder(
        self, group_id: str, text: str, owner_id: str, *, retry_key: str
    ) -> str:
        payload = {
            "to": group_id,
            "messages": [
                {
                    "type": "textV2",
                    "text": "{owner}" + text,
                    "substitution": {
                        "owner": {
                            "type": "mention",
                            "mentionee": {"type": "user", "userId": owner_id},
                        }
                    },
                }
            ],
        }
        return self._request(PUSH_ENDPOINT, payload=payload, retry_key=retry_key).get(
            "requestId", ""
        )

    def _request(
        self, url: str, *, payload: dict | None = None, retry_key: str = ""
    ) -> dict:
        data = None
        method = "GET"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            method = "POST"
            headers["Content-Type"] = "application/json"
        if retry_key:
            headers["X-Line-Retry-Key"] = retry_key
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read().decode("utf-8")
                result = json.loads(body) if body else {}
                request_id = response.headers.get("X-Line-Request-Id", "")
                if request_id:
                    result["requestId"] = request_id
                return result
        except urllib.error.HTTPError as exc:
            raise LineApiError(f"LINE API failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LineApiError("LINE API is unavailable") from exc

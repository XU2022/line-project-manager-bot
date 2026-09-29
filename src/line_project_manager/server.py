"""Minimal threaded HTTP server for the LINE webhook endpoint."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .application import BotApplication
from .commands import CommandProcessor
from .config import ConfigError, RuntimeConfig, load_members
from .database import Database
from .line_gateway import GateConfig, InvalidSignature, LineApiError, LineReplyClient
from .tracker import TaskService


LOGGER = logging.getLogger("line_project_manager")


class WebhookService:
    def __init__(self, application: BotApplication, reply_client: LineReplyClient):
        self.application = application
        self.reply_client = reply_client

    def process(self, raw_body: bytes, signature: str) -> int:
        replies = self.application.process_webhook(raw_body, signature)
        delivered = 0
        for reply in replies:
            try:
                self.reply_client.reply_text(reply.reply_token, reply.text)
                delivered += 1
            except LineApiError:
                LOGGER.exception("LINE reply failed for event %s", reply.event_id)
        return delivered


def build_service(config: RuntimeConfig) -> WebhookService:
    database = Database(config.database_path)
    database.initialize_default()
    members = load_members(config.member_config_path)
    task_service = TaskService(database, timezone=config.timezone)
    for member in members:
        task_service.register_member(member.member_id, member.display_name, member.roles)
    application = BotApplication(
        database=database,
        command_processor=CommandProcessor(task_service),
        gate_config=GateConfig.create(
            allowed_group_ids=config.allowed_group_ids,
            allowed_member_ids=(
                [] if config.bootstrap_mode else [member.member_id for member in members]
            ),
        ),
        channel_secret=config.channel_secret,
        timezone=config.timezone,
        bootstrap_mode=config.bootstrap_mode,
    )
    return WebhookService(application, LineReplyClient(config.channel_access_token))


def handler_class(service: WebhookService, max_body_bytes: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LineProjectManager/0.1"

        def do_GET(self) -> None:
            if self.path != "/healthz":
                self._json(404, {"error": "not found"})
                return
            self._json(200, {"status": "ok"})

        def do_POST(self) -> None:
            if self.path != "/webhook":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "invalid content length"})
                return
            if length <= 0 or length > max_body_bytes:
                self._json(413, {"error": "invalid request size"})
                return
            raw_body = self.rfile.read(length)
            signature = self.headers.get("x-line-signature", "")
            try:
                delivered = service.process(raw_body, signature)
            except InvalidSignature:
                self._json(401, {"error": "invalid signature"})
                return
            except ValueError:
                LOGGER.exception("Invalid webhook payload")
                self._json(400, {"error": "invalid payload"})
                return
            self._json(200, {"accepted": True, "replies": delivered})

        def log_message(self, format: str, *args) -> None:
            LOGGER.info("http %s", format % args)

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = RuntimeConfig.from_env()
        service = build_service(config)
    except ConfigError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc
    server = ThreadingHTTPServer(
        (config.host, config.port), handler_class(service, config.max_body_bytes)
    )
    LOGGER.info("listening on http://%s:%s", config.host, config.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("shutdown requested")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

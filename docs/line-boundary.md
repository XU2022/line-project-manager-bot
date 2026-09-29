# LINE integration boundary

## Implemented

- HMAC-SHA256 verification of the raw webhook body
- Constant-time comparison of `x-line-signature`
- Group and optional member allowlists
- Structured bot mentions as the primary trigger
- A configurable single-letter fallback at the start of a message
- Silent handling of ordinary chat
- Reply and Push clients, webhook deduplication, quota checks, and reminders

## Security requirements

1. Verify the unmodified raw request before parsing JSON.
2. Do not replace signature verification with a source-IP allowlist.
3. Configure explicit production group IDs.
4. Keep channel secrets and access tokens in environment variables or restricted secret files.
5. Do not log full message bodies, access tokens, or member identifiers.
6. Use each Reply token only for its corresponding event.

## Official references

- [Verify webhook signature](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
- [Receive messages](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [Group chats](https://developers.line.biz/en/docs/messaging-api/group-chats/)
- [Messaging API reference](https://developers.line.biz/en/reference/messaging-api/)


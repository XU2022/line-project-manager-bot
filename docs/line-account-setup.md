# LINE Official Account setup

## 1. Create a Messaging API channel

Create a LINE Official Account and enable its Messaging API channel. Store the Channel secret and Channel access token only in a restricted server environment file.

## 2. Configure group chat

- Enable webhooks.
- Allow the bot to join group chats.
- Disable unnecessary default auto-replies.
- Add the Official Account to the intended LINE group.

## 3. Discover group and member IDs

Temporarily configure:

```text
LINE_ALLOWED_GROUPS=*
LINE_REMINDER_GROUP_ID=*
LINE_BOOTSTRAP_MODE=true
```

Start only `line-project-bot`, not the reminder timer. Each member should send:

```text
@Bot identity
```

The configured fallback, such as `H: identity`, also works. The bot replies with the group and member IDs. Use this only in a trusted group because those IDs appear in chat.

Store the IDs locally, replace the wildcard, disable bootstrap mode, and restart the service immediately.

## 4. Configure the webhook

Set the public URL to `https://line.example.com/webhook`, then use Verify in LINE Developers Console. An empty `events` request is valid and returns HTTP 200.

## 5. Safety checklist

- Never commit real IDs or credentials.
- Never use bootstrap mode in a public group.
- Disable bootstrap mode immediately after discovery.
- Do not log full webhook bodies.
- Reissue credentials if exposure is suspected.


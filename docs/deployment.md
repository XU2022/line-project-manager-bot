# Deployment guide

This example uses Linux, Python 3.11+, systemd, and Nginx. Validate everything on a test server and in a test group first.

## 1. Prepare LINE and install

Complete [LINE account setup](line-account-setup.md), clone the reviewed repository, and run:

```bash
sudo useradd --system --home /opt/line-project-manager --shell /usr/sbin/nologin linebot
sudo mkdir -p /opt/line-project-manager/state /opt/line-project-manager/config
sudo chown -R linebot:linebot /opt/line-project-manager
sudo -u linebot python3 -m venv /opt/line-project-manager/venv
sudo -u linebot /opt/line-project-manager/venv/bin/pip install .
```

## 2. Local configuration

Copy `config/members.example.json` to `/opt/line-project-manager/config/members.json`, replace fictional values, and restrict it to the service account. Create `/etc/line-project-manager.env`:

```text
LINE_CHANNEL_SECRET=replace_me
LINE_CHANNEL_ACCESS_TOKEN=replace_me
LINE_ALLOWED_GROUPS=C_REPLACE_WITH_GROUP_ID
LINE_REMINDER_GROUP_ID=C_REPLACE_WITH_GROUP_ID
LINE_FALLBACK_TRIGGER_LETTER=H
BOT_LOCALE=en
PROJECT_DB_PATH=/opt/line-project-manager/state/tasks.sqlite3
MEMBER_CONFIG_PATH=/opt/line-project-manager/config/members.json
LINE_HOST=127.0.0.1
LINE_PORT=8646
PROJECT_TIMEZONE=Asia/Tokyo
REMINDER_HOUR=12
MONTHLY_MESSAGE_LIMIT=200
ESTIMATED_PUSH_COST=3
```

Protect the file with `root:linebot` ownership and mode `640`. `ESTIMATED_PUSH_COST` should reflect the estimated billable recipients for one group Push.

## 3. Initialize and install services

```bash
sudo -u linebot sh -c 'set -a; . /etc/line-project-manager.env; set +a; /opt/line-project-manager/venv/bin/line-project-init'
sudo cp systemd/line-project-*.service systemd/line-project-reminder.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now line-project-bot.service
sudo systemctl enable --now line-project-reminder.timer
```

The example timer runs at 12:00 Asia/Tokyo. Keep the timer synchronized with `PROJECT_TIMEZONE` and `REMINDER_HOUR`.

## 4. HTTPS

Adapt `config/nginx.example.conf`. Nginx must preserve the raw request body and forward `x-line-signature`. Configure `https://line.example.com/webhook` in LINE Developers Console and verify HTTP 200.

## 5. Production checklist

- Real credentials, IDs, databases, and logs are absent from Git.
- The webhook is HTTPS-only.
- Secrets and member configuration have restricted permissions.
- Only intended groups and members are allowed.
- Create, list, complete, and reminder flows pass in a test group.
- Push-cost estimates and monthly limits match the deployment.

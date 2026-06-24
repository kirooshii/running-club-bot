# lada-bot

Telegram bot for a weekly running club. Fully automated registration via inline
buttons — no personal data is stored on the server (only Telegram user IDs and
per-week registration status).

## Mechanics

1. **Every Monday 10:00** the bot broadcasts an "open registration" message with
   two buttons: **Да, участвую** / **Нет, не смогу**.
2. **Да, участвую** → the user is added to the registered list if there is a free
   spot, otherwise to the waiting list. A confirmation message is sent together
   with an **Отменить регистрацию** button.
3. **Нет, не смогу** → a friendly "see you next time" message.
4. **Отменить регистрацию** → frees the spot. **All** users on the waiting list
   are then notified that a spot opened; the first one to click **Занять место**
   gets it (first-click wins).
5. **Every Friday 09:00** a reminder is sent **only** to currently registered users.

> All message texts are editable placeholders (see "Editing texts" below).

## Requirements

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set BOT_TOKEN, ADMIN_IDS, CAPACITY, etc.
python -m bot
```

The bot runs in long-polling mode (works on any VPS without HTTPS setup).

## Configuration (`.env`)

| Variable              | Description                                              | Default             |
|-----------------------|---------------------------------------------------------|---------------------|
| `BOT_TOKEN`           | Telegram bot token (required)                           | —                   |
| `DATABASE_PATH`       | SQLite file path                                        | `data/bot.db`       |
| `TIMEZONE`            | IANA timezone for scheduled jobs                        | `Europe/Moscow`     |
| `CAPACITY`            | Max participants per edition                            | `30`                |
| `ADMIN_IDS`           | Comma-separated admin Telegram IDs                      | —                   |
| `MONDAY_OPEN_TIME`    | `HH:MM` when registration opens (Monday)               | `10:00`             |
| `FRIDAY_REMINDER_TIME`| `HH:MM` for the Friday reminder                         | `09:00`             |
| `EVENT_INFO`          | Short event line interpolated into texts                | каждое воскресенье...|

## Admin commands

Only users whose ID is in `ADMIN_IDS` may use these:

| Command                         | Action                                                        |
|---------------------------------|---------------------------------------------------------------|
| `/admin`                        | Show current week stats + help                                |
| `/capacity`                     | Show current capacity                                         |
| `/setcapacity <N>`              | Change capacity; if increased, notify waiting users           |
| `/broadcast <text>`             | Send a message to all subscribed users                        |
| `/texts`                        | List editable text keys                                       |
| `/settext <key> <text...>`      | Override a message text (`/settext welcome Hello there`)      |
| `/resettext <key>`              | Restore a text to its default                                 |
| `/trigger_open`                 | Manually run the Monday broadcast (current week); opens registration             |
| `/trigger_close`                | Close registration for the current week — no new sign-ups or spot claims         |
| `/trigger_reminder`             | Manually run the Friday reminder                              |

## Editing texts

All user-facing texts are placeholders in `bot/texts.py`. Any of them can be
overridden at runtime with `/settext` (stored in the DB, survives restarts) or
permanently by editing `DEFAULT_TEXTS` in `bot/texts.py`. The `{event_info}`
placeholder is filled from the `EVENT_INFO` setting.

Available keys: `welcome`, `subscribed`, `monday_open`, `confirm_registered`,
`confirm_waiting`, `decline_no`, `cancelled`, `cancelled_waiting`, `spot_freed`,
`spot_taken`, `spot_taken_success`, `reminder`, `already_registered`.

## Privacy

The database stores only:
- `users`: Telegram user ID, subscription flag, creation timestamp.
- `registrations`: Telegram user ID, week key, status, timestamps.
- `settings`: capacity + overridden texts.

No names, usernames, or phone numbers are ever stored.

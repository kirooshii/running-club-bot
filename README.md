# Running Club Bot

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0)
![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57)

A fully automated Telegram bot that runs a weekly running club end‑to‑end —
registration, a fair waiting list, automated reminders and a broadcast channel
for the organiser. Everything happens through inline buttons: no back‑and‑forth
chat, minimal taps for the user.


## Highlights

- **Fully automated weekly flow.** Monday 10:00 opens registration, Friday 09:00
  reminds confirmed participants — both run on a cron scheduler.
- **Race‑free booking.** Registrations are guarded by an `asyncio.Lock` over a
  WAL‑mode SQLite DB, so capacity is never exceeded — even when many users tap
  "yes" at the exact same moment.
- **Fair waiting list.** When someone cancels, every waiter is notified and the
  freed spot goes to whoever claims it first (first‑click‑wins).
- **Configurable at runtime.** Change capacity, every user‑facing text and
  broadcast photos — straight from Telegram. No restart, no code edit.
- **Privacy‑first.** The only data stored is Telegram user IDs and a per‑week
  status. No names, usernames or phone numbers.
- **Self‑test suite.** `python -m bot.selftest` exercises the whole booking
  state machine against a throwaway DB and prints a PASS/FAIL report.

## Tech stack

| | |
|---|---|
| Language | Python 3.11+ |
| Bot framework | [aiogram](https://github.com/aiogram/aiogram) 3.x |
| Scheduler | APScheduler (asyncio) |
| Storage | SQLite via aiosqlite (WAL mode) |
| Process manager | PM2 (config included) |

## How it works

The weekly loop:

1. **Monday 10:00** — every subscriber gets a registration card with two
   buttons: **Yes** / **No**.
2. **Yes** → added to the registered list if a spot is free, otherwise to the
   waiting list. They get a confirmation plus an always‑visible
   **Cancel Registration** button.
3. **No** → a friendly "see you next time" message, with a **I've changed my mind**
   button in case they change their mind.
4. **Cancel** → frees the spot. All waiting users are then pinged, and the
   first one to tap **Book a spot** gets it.
5. **Friday 09:00** — a reminder is sent **only** to currently registered users.

Late joiners who run `/start` mid‑week automatically receive the current week's
registration card if it's still open.

## Project structure

```
bot/
├── __main__.py         # entrypoint: wires bot + dispatcher + scheduler
├── config.py           # .env parsing + validation
├── db.py               # SQLite layer: registration state machine + lock
├── scheduler.py        # Monday open / Friday reminder cron jobs
├── texts.py            # all user-facing texts (runtime-overridable)
├── keyboards.py        # inline + persistent reply keyboards
├── utils.py            # safe send / broadcast / waiting-list notify
├── weeks.py            # ISO-week edition keys
├── selftest.py         # end-to-end workflow test
└── handlers/
    ├── common.py       # /start, /stop, /help
    ├── registration.py # yes / no / cancel / take-spot flows
    └── admin.py        # admin commands + photo broadcast
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in BOT_TOKEN, ADMIN_IDS, ...

python -m bot
```

Verify the booking logic any time with the self‑test:

```bash
python -m bot.selftest
```

### Production (PM2)

```bash
pm2 start ecosystem.config.cjs
pm2 logs lada-bot
```

## Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) | — |
| `DATABASE_PATH` | SQLite file path | `data/bot.db` |
| `TIMEZONE` | IANA timezone for scheduled jobs | `Europe/Moscow` |
| `CAPACITY` | Max participants per edition | `30` |
| `ADMIN_IDS` | Comma‑separated admin Telegram IDs | — |
| `MONDAY_OPEN_TIME` | `HH:MM` registration opens (Mon) | `10:00` |
| `FRIDAY_REMINDER_TIME` | `HH:MM` for the reminder (Fri) | `09:00` |

## Admin commands

Restricted to users in `ADMIN_IDS`:

| Command | Action |
|---|---|
| `/admin` | Current week stats + command help |
| `/capacity` | Show current capacity |
| `/setcapacity <N>` | Change capacity live; if raised, notify waiting users |
| `/broadcast <text>` | Message all subscribers |
| *(send a photo)* | Broadcast a photo (with optional caption) via a confirm button |
| `/texts` | List editable text keys |
| `/settext <key> <text>` | Override a message text (e.g. `/settext reminder ...`) |
| `/resettext <key>` | Restore a text to its default |
| `/trigger_open` | Manually run the Monday broadcast |
| `/trigger_close` | Close registration — no new sign‑ups or spot claims |
| `/trigger_reminder` | Manually run the Friday reminder |

User commands: `/start` (subscribe), `/stop` (unsubscribe), `/help`.


## Privacy

The database stores only:

- `users` — Telegram user ID, subscription flag, creation timestamp.
- `registrations` — Telegram user ID, week key, status, timestamps.
- `settings` — capacity + overridden texts.

No names, usernames, or phone numbers are ever stored.

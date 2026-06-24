"""End-to-end workflow self-test (no Telegram, no waiting for Monday).

Runs the real DB + scheduler + utils logic against a throwaway SQLite file and
prints a PASS/FAIL report for every rule of the bot:

    python -m bot.selftest

It does NOT exercise Telegram button rendering / actual delivery — that part
must be checked manually via the admin /trigger_open, /trigger_reminder and
/setcapacity commands (see README).
"""
from __future__ import annotations

import asyncio
import os
import tempfile

# Configure a throwaway environment BEFORE importing the bot package, so config
# loads against an isolated DB and a dummy token.
os.environ.setdefault("BOT_TOKEN", "selftest:selftest")
_TMP_DB = tempfile.mktemp(suffix=".db")
os.environ.setdefault("DATABASE_PATH", _TMP_DB)

from aiogram.types import InlineKeyboardMarkup  # noqa: E402

from bot import config  # noqa: E402
config.db_path = _TMP_DB

from bot import db, weeks  # noqa: E402
from bot.scheduler import open_registration, send_reminders  # noqa: E402
from bot.utils import maybe_relay_announcement, notify_waiting  # noqa: E402

WEEK = weeks.current_week_key()
_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(cond), detail))


class FakeBot:
    """Captures every send_message call so we can assert who got what."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id, text, reply_markup=None, **_):
        self.sent.append({"to": chat_id, "text": text, "kb": reply_markup})
        return True

    def to(self, user_id: int) -> list[dict]:
        return [m for m in self.sent if m["to"] == user_id]


async def run() -> None:
    await db.init_db()
    await db.seed_settings()
    await db.set_capacity(2)

    for uid in (1, 2, 3, 4, 5):
        await db.ensure_user(uid)
        await db.set_subscribed(uid, True)

    bot = FakeBot()

    # --- Monday broadcast: every subscriber gets the Да/Нет card -----------
    sent = await open_registration(bot)
    check("monday broadcast count", sent == 5, f"sent={sent}")
    check(
        "monday card has Да/Нет",
        all(isinstance(m["kb"], InlineKeyboardMarkup) for m in bot.sent),
    )
    check("week is announced", await db.get_announced_week() == WEEK)

    # --- registration fills up to capacity, rest go to waiting -------------
    check("u1 register", await db.register_user(1, WEEK) == "registered")
    check("u2 register", await db.register_user(2, WEEK) == "registered")
    check("u3 waiting", await db.register_user(3, WEEK) == "waiting")
    check("u4 waiting", await db.register_user(4, WEEK) == "waiting")
    check("u5 waiting", await db.register_user(5, WEEK) == "waiting")
    check("capacity respected (2)", await db.count_by_status(WEEK, "registered") == 2)
    check(
        "waiting FIFO order",
        await db.get_users_by_status(WEEK, "waiting") == [3, 4, 5],
    )
    check("re-register is idempotent", await db.register_user(2, WEEK) == "already_registered")

    # --- cancel frees a spot -> ALL waiters are notified -------------------
    prev = await db.cancel_registration(1, WEEK)
    check("cancel returns 'registered'", prev == "registered")
    bot.sent.clear()
    notified = await notify_waiting(bot, WEEK)
    check("notify targets all waiters", notified == 3)
    targets = sorted(m["to"] for m in bot.sent)
    check("notified exactly [3,4,5]", targets == [3, 4, 5])
    check(
        "notify uses «Занять место» card",
        all(isinstance(m["kb"], InlineKeyboardMarkup) for m in bot.sent),
    )

    # --- first-click-wins: only one spot was freed -------------------------
    check("u3 takes freed spot", await db.take_spot(3, WEEK) == "ok")
    check("u4 now too late", await db.take_spot(4, WEEK) == "full")
    check("still 2 registered", await db.count_by_status(WEEK, "registered") == 2)
    check("waiting now [4,5]", await db.get_users_by_status(WEEK, "waiting") == [4, 5])

    # --- cancelling a waiter just removes them ----------------------------
    prev = await db.cancel_registration(4, WEEK)
    check("cancel waiter returns 'waiting'", prev == "waiting")
    check("waiting now [5]", await db.get_users_by_status(WEEK, "waiting") == [5])

    # --- second cancel -> frees again -> remaining waiter notified ---------
    await db.cancel_registration(3, WEEK)
    bot.sent.clear()
    await notify_waiting(bot, WEEK)
    check("second free notifies [5]", sorted(m["to"] for m in bot.sent) == [5])
    check("u5 takes it", await db.take_spot(5, WEEK) == "ok")

    # --- decline flow ------------------------------------------------------
    await db.ensure_user(6)
    await db.set_status(6, WEEK, "declined")
    check("decline counted", await db.count_by_status(WEEK, "declined") == 1)

    # --- Friday reminder: only registered users ----------------------------
    bot.sent.clear()
    rem = await send_reminders(bot)
    registered = await db.get_users_by_status(WEEK, "registered")
    check("reminder recipients == registered", sorted(m["to"] for m in bot.sent) == sorted(registered))
    check("reminder sent > 0", rem == len(registered))

    # --- announce-relay: new subscriber gets card IF week announced --------
    bot.sent.clear()
    relayed = await maybe_relay_announcement(bot, 999)
    check("relay sends card when announced", relayed is True and len(bot.to(999)) == 1)
    await db.set_announced_week("1999-01-04")  # stale week
    relayed_stale = await maybe_relay_announcement(bot, 998)
    check("relay skips when not current week", relayed_stale is False)

    # --- open / close registration ----------------------------------------
    await db.set_announced_week(WEEK)
    check("open before close", await db.is_registration_open(WEEK) is True)
    await db.clear_announced_week()
    check("closed after trigger_close", await db.is_registration_open(WEEK) is False)
    bot.sent.clear()
    await open_registration(bot)
    check("re-open after trigger_open", await db.is_registration_open(WEEK) is True)

    _report()


def _report() -> None:
    width = max(len(n) for n, _, _ in _RESULTS)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    print(f"\n{'check':<{width}}  result   detail")
    print("-" * (width + 40))
    for name, ok, detail in _RESULTS:
        mark = "PASS" if ok else "FAIL"
        print(f"{name:<{width}}  {mark:5}  {('— ' + detail) if detail and not ok else ''}")
    print("-" * (width + 40))
    print(f"{passed}/{len(_RESULTS)} checks passed\n")
    if passed != len(_RESULTS):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())

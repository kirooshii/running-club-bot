"""SQLite persistence layer.

Stores only Telegram user IDs + per-week registration status. No names,
usernames or any other personal data are ever written.

A single ``asyncio.Lock`` serializes registration mutations so that capacity
can never be exceeded even if two users click simultaneously.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime

import aiosqlite

from .config import config

# Status values stored in ``registrations.status``.
REGISTERED = "registered"   # confirmed participant
WAITING = "waiting"         # on the waiting list
DECLINED = "declined"       # clicked "No, не смогу"
CANCELLED = "cancelled"     # was registered/waiting, then cancelled

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    subscribed   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    user_id    INTEGER NOT NULL,
    week_key   TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (user_id, week_key)
);

CREATE INDEX IF NOT EXISTS idx_reg_week_status
    ON registrations (week_key, status);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(config.timezone).isoformat()


# --------------------------------------------------------------------------- #
# connection helper
# --------------------------------------------------------------------------- #
def _connect() -> aiosqlite.Connection:
    # ``timeout`` sets SQLite's busy-timeout (seconds). The returned object is
    # an async context manager that starts its background thread on __aenter__.
    return aiosqlite.connect(config.db_path, timeout=5.0)


# --------------------------------------------------------------------------- #
# init / seeding
# --------------------------------------------------------------------------- #
async def init_db() -> None:
    parent = os.path.dirname(config.db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    async with _connect() as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA journal_mode = WAL")
        await db.commit()


async def seed_settings() -> None:
    if await get_setting("capacity") is None:
        await set_setting("capacity", str(config.capacity))


# --------------------------------------------------------------------------- #
# settings (key/value)
# --------------------------------------------------------------------------- #
async def get_setting(key: str) -> str | None:
    async with _connect() as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    async with _connect() as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_capacity() -> int:
    raw = await get_setting("capacity")
    try:
        return max(1, int(raw)) if raw else config.capacity
    except (TypeError, ValueError):
        return config.capacity


async def set_capacity(value: int) -> None:
    await set_setting("capacity", str(max(1, value)))


# --------------------------------------------------------------------------- #
# announcement tracking (which week's registration is currently open)
# --------------------------------------------------------------------------- #
async def get_announced_week() -> str | None:
    return await get_setting("announced_week")


async def set_announced_week(week_key: str) -> None:
    await set_setting("announced_week", week_key)


async def clear_announced_week() -> None:
    """Close registration: no week is announced, so sign-ups/claims are blocked."""
    async with _connect() as db:
        await db.execute("DELETE FROM settings WHERE key = ?", ("announced_week",))
        await db.commit()


async def is_registration_open(week_key: str) -> bool:
    """True if ``week_key`` is the currently-announced (open) edition."""
    return await get_announced_week() == week_key


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
async def ensure_user(user_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, subscribed, created_at) "
            "VALUES (?, 0, ?)",
            (user_id, _now()),
        )
        await db.commit()


async def set_subscribed(user_id: int, subscribed: bool) -> None:
    async with _connect() as db:
        await db.execute(
            "INSERT INTO users(user_id, subscribed, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET subscribed = excluded.subscribed",
            (user_id, 1 if subscribed else 0, _now()),
        )
        await db.commit()


async def is_subscribed(user_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute(
            "SELECT subscribed FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return bool(row and row[0])


async def get_subscribed_users() -> list[int]:
    async with _connect() as db:
        cur = await db.execute("SELECT user_id FROM users WHERE subscribed = 1")
        return [row[0] for row in await cur.fetchall()]


async def count_users() -> int:
    async with _connect() as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]


async def count_subscribed() -> int:
    async with _connect() as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE subscribed = 1")
        return (await cur.fetchone())[0]


# --------------------------------------------------------------------------- #
# registrations
# --------------------------------------------------------------------------- #
async def _count_registered(week_key: str, db: aiosqlite.Connection) -> int:
    cur = await db.execute(
        "SELECT COUNT(*) FROM registrations "
        "WHERE week_key = ? AND status = ?",
        (week_key, REGISTERED),
    )
    return (await cur.fetchone())[0]


async def _get_status(user_id: int, week_key: str, db: aiosqlite.Connection):
    cur = await db.execute(
        "SELECT status FROM registrations WHERE user_id = ? AND week_key = ?",
        (user_id, week_key),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def count_by_status(week_key: str, status: str) -> int:
    async with _connect() as db:
        return await _count_status(week_key, status, db)


async def _count_status(week_key: str, status: str, db: aiosqlite.Connection) -> int:
    cur = await db.execute(
        "SELECT COUNT(*) FROM registrations WHERE week_key = ? AND status = ?",
        (week_key, status),
    )
    return (await cur.fetchone())[0]


async def get_users_by_status(week_key: str, status: str) -> list[int]:
    async with _connect() as db:
        cur = await db.execute(
            "SELECT user_id FROM registrations WHERE week_key = ? AND status = ? "
            "ORDER BY created_at",
            (week_key, status),
        )
        return [row[0] for row in await cur.fetchall()]


async def get_status(user_id: int, week_key: str):
    """Public accessor for a user's status in a given week (or ``None``)."""
    async with _connect() as db:
        return await _get_status(user_id, week_key, db)


async def set_status(user_id: int, week_key: str, status: str) -> None:
    async with _lock, _connect() as db:
        now = _now()
        await db.execute(
            "INSERT INTO registrations(user_id, week_key, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, week_key) DO UPDATE "
            "SET status = excluded.status, updated_at = excluded.updated_at",
            (user_id, week_key, status, now, now),
        )
        await db.commit()


async def register_user(user_id: int, week_key: str) -> str:
    """Try to register ``user_id`` for ``week_key``.

    Returns one of: ``already_registered``, ``registered``, ``waiting``.
    """
    capacity = await get_capacity()
    async with _lock, _connect() as db:
        current = await _get_status(user_id, week_key, db)
        now = _now()

        if current == REGISTERED:
            return "already_registered"

        registered = await _count_registered(week_key, db)

        if current == WAITING and registered < capacity:
            await db.execute(
                "UPDATE registrations SET status = ?, updated_at = ? "
                "WHERE user_id = ? AND week_key = ?",
                (REGISTERED, now, user_id, week_key),
            )
            await db.commit()
            return "registered"

        if registered >= capacity:
            await db.execute(
                "INSERT INTO registrations(user_id, week_key, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, week_key) DO UPDATE "
                "SET status = excluded.status, updated_at = excluded.updated_at",
                (user_id, week_key, WAITING, now, now),
            )
            await db.commit()
            return "waiting"

        await db.execute(
            "INSERT INTO registrations(user_id, week_key, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, week_key) DO UPDATE "
            "SET status = excluded.status, updated_at = excluded.updated_at",
            (user_id, week_key, REGISTERED, now, now),
        )
        await db.commit()
        return "registered"


async def cancel_registration(user_id: int, week_key: str) -> str:
    """Cancel an active registration or waiting entry.

    Returns the previous status (``registered``/``waiting``) or one of
    ``none`` / ``not_active`` so the caller knows whether to notify waiters.
    """
    async with _lock, _connect() as db:
        current = await _get_status(user_id, week_key, db)
        if current is None:
            return "none"
        if current in (CANCELLED, DECLINED):
            return "not_active"
        now = _now()
        await db.execute(
            "UPDATE registrations SET status = ?, updated_at = ? "
            "WHERE user_id = ? AND week_key = ?",
            (CANCELLED, now, user_id, week_key),
        )
        await db.commit()
        return current  # registered | waiting


async def take_spot(user_id: int, week_key: str) -> str:
    """Called when a waiting user clicks "take the freed spot".

    Returns ``ok`` / ``full`` / ``not_waiting``.
    """
    capacity = await get_capacity()
    async with _lock, _connect() as db:
        current = await _get_status(user_id, week_key, db)
        if current != WAITING:
            return "not_waiting"
        registered = await _count_registered(week_key, db)
        if registered >= capacity:
            return "full"
        now = _now()
        await db.execute(
            "UPDATE registrations SET status = ?, updated_at = ? "
            "WHERE user_id = ? AND week_key = ?",
            (REGISTERED, now, user_id, week_key),
        )
        await db.commit()
        return "ok"


async def week_stats(week_key: str) -> dict[str, int]:
    async with _connect() as db:
        result = {
            "registered": await _count_status(week_key, REGISTERED, db),
            "waiting": await _count_status(week_key, WAITING, db),
            "declined": await _count_status(week_key, DECLINED, db),
            "cancelled": await _count_status(week_key, CANCELLED, db),
        }
        return result

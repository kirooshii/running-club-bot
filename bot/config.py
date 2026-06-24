"""Application configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> set[int]:
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hours, minutes = (int(p) for p in value.split(":"))
    except ValueError as exc:
        raise RuntimeError(f"Invalid time {value!r}: expected HH:MM") from exc
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise RuntimeError(
            f"Invalid time {value!r}: hours must be 0-23, minutes 0-59"
        )
    return hours, minutes


def _parse_capacity(raw: str) -> int:
    try:
        return max(1, int(raw))
    except ValueError as exc:
        raise RuntimeError(f"Invalid CAPACITY {raw!r}: expected an integer") from exc


@dataclass
class Config:
    bot_token: str
    db_path: str
    timezone: ZoneInfo
    capacity: int
    admin_ids: set[int] = field(default_factory=set)
    monday_time: tuple[int, int] = (10, 0)
    friday_time: tuple[int, int] = (9, 0)
    event_info: str = ""


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )
    tz_name = os.getenv("TIMEZONE", "Europe/Moscow")
    try:
        timezone = ZoneInfo(tz_name)
    except Exception as exc:  # invalid timezone
        raise RuntimeError(f"Invalid TIMEZONE {tz_name!r}: {exc}") from exc

    return Config(
        bot_token=token,
        db_path=os.getenv("DATABASE_PATH", "data/bot.db"),
        timezone=timezone,
        capacity=_parse_capacity(os.getenv("CAPACITY", "30")),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
        monday_time=_parse_hhmm(os.getenv("MONDAY_OPEN_TIME", "10:00")),
        friday_time=_parse_hhmm(os.getenv("FRIDAY_REMINDER_TIME", "09:00")),
        event_info=os.getenv("EVENT_INFO", "каждое воскресенье в 18:30"),
    )


config = load_config()

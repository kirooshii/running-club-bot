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
    hours, minutes = value.split(":")
    return int(hours), int(minutes)


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
        capacity=max(1, int(os.getenv("CAPACITY", "30"))),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
        monday_time=_parse_hhmm(os.getenv("MONDAY_OPEN_TIME", "10:00")),
        friday_time=_parse_hhmm(os.getenv("FRIDAY_REMINDER_TIME", "09:00")),
        event_info=os.getenv("EVENT_INFO", "каждое воскресенье в 18:30"),
    )


config = load_config()

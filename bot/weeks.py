"""Week / edition helpers.

An "edition" of the running club is identified by the ISO date of the Monday
that opens its registration (e.g. the edition for the week of Mon 2026-06-29 is
``2026-06-29``).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import config


def monday_of(day: date) -> date:
    """Return the Monday of the week that contains ``day``."""
    return day - timedelta(days=day.weekday())  # Monday == 0


def today() -> date:
    """Today's date in the configured timezone."""
    return datetime.now(config.timezone).date()


def current_week_key() -> str:
    """Edition key for the current week (Monday's ISO date)."""
    return monday_of(today()).isoformat()

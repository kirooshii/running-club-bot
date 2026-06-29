"""Week / edition helpers.

An "edition" of the running club is identified by the ISO date of the Monday
that opens its registration (e.g. the edition for the week of Mon 2026-06-29 is
``2026-06-29``).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import config

# Russian month names in genitive case (for "4 июля"-style output).
_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def monday_of(day: date) -> date:
    """Return the Monday of the week that contains ``day``."""
    return day - timedelta(days=day.weekday())  # Monday == 0


def today() -> date:
    """Today's date in the configured timezone."""
    return datetime.now(config.timezone).date()


def current_week_key() -> str:
    """Edition key for the current week (Monday's ISO date)."""
    return monday_of(today()).isoformat()


def run_date_from_week(week_key: str) -> date:
    """The run date (Saturday) for a given registration week.

    The week key is the ISO date of the Monday that opens registration.
    The actual run happens 5 days later (Saturday).
    """
    return date.fromisoformat(week_key) + timedelta(days=5)


def format_run_date(d: date) -> str:
    """Format a date as ``день месяц`` in Russian (e.g. ``4 июля``)."""
    return f"{d.day} {_MONTHS[d.month - 1]}"

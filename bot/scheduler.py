"""Scheduled jobs: Monday registration open + Friday reminder."""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import config
from .db import (
    REGISTERED,
    get_subscribed_users,
    get_users_by_status,
    set_announced_week,
)
from .keyboards import cancel_kb, monday_kb
from .texts import get_text
from .utils import broadcast, resolve_message
from .weeks import current_week_key

log = logging.getLogger(__name__)


async def open_registration(bot: Bot) -> int:
    """Broadcast the Monday "registration is open" message to subscribers."""
    week = current_week_key()
    await set_announced_week(week)
    text, photo = await resolve_message("monday_open", week)
    kb = monday_kb(week)
    users = await get_subscribed_users()
    sent = await broadcast(bot, users, text, reply_markup=kb, photo=photo)
    log.info("open_registration week=%s sent=%s/%s", week, sent, len(users))
    return sent


async def send_reminders(bot: Bot) -> int:
    """Send the Friday reminder to currently registered users only."""
    week = current_week_key()
    text, photo = await resolve_message("reminder", week)
    kb = cancel_kb(week)
    users = await get_users_by_status(week, REGISTERED)
    sent = await broadcast(bot, users, text, reply_markup=kb, photo=photo)
    log.info("send_reminders week=%s sent=%s/%s", week, sent, len(users))
    return sent


def schedule_jobs(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    mon_h, mon_m = config.monday_time
    fri_h, fri_m = config.friday_time

    scheduler.add_job(
        open_registration,
        CronTrigger(
            day_of_week="mon", hour=mon_h, minute=mon_m, timezone=config.timezone
        ),
        args=[bot],
        id="open_registration",
        replace_existing=True,
    )
    scheduler.add_job(
        send_reminders,
        CronTrigger(
            day_of_week="fri", hour=fri_h, minute=fri_m, timezone=config.timezone
        ),
        args=[bot],
        id="send_reminders",
        replace_existing=True,
    )
    log.info(
        "scheduled jobs: Monday %02d:%02d, Friday %02d:%02d (%s)",
        mon_h, mon_m, fri_h, fri_m, config.timezone,
    )

"""Sending helpers: safe per-user send, broadcast, waiting-list notification."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from .db import WAITING, get_announced_week, get_users_by_status, set_subscribed
from .keyboards import monday_kb, take_spot_kb
from .texts import get_text
from .weeks import current_week_key

log = logging.getLogger(__name__)


async def safe_send(
    bot: Bot, user_id: int, text: str, reply_markup=None
) -> bool:
    """Send a message; on ``Forbidden`` mark the user unsubscribed."""
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except TelegramForbiddenError:
        await set_subscribed(user_id, False)
        return False
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.send_message(user_id, text, reply_markup=reply_markup)
            return True
        except Exception:
            log.warning("safe_send retry failed for user %s", user_id, exc_info=True)
            return False
    except Exception:
        log.warning("safe_send failed for user %s", user_id, exc_info=True)
        return False


async def broadcast(
    bot: Bot,
    user_ids,
    text: str,
    reply_markup=None,
    delay: float = 0.05,
) -> int:
    """Send ``text`` to each user id; returns the number of successful sends."""
    sent = 0
    for uid in user_ids:
        if await safe_send(bot, uid, text, reply_markup):
            sent += 1
        if delay:
            await asyncio.sleep(delay)
    return sent


async def notify_waiting(bot: Bot, week: str) -> int:
    """Notify every waiting user that a spot opened (first-click wins)."""
    waiters = await get_users_by_status(week, WAITING)
    if not waiters:
        return 0
    text = await get_text("spot_freed")
    return await broadcast(bot, waiters, text, reply_markup=take_spot_kb(week))


async def safe_send_photo(
    bot: Bot, user_id: int, photo: str, caption: str | None = None
) -> bool:
    """Send a photo; on ``Forbidden`` mark the user unsubscribed."""
    try:
        await bot.send_photo(user_id, photo, caption=caption)
        return True
    except TelegramForbiddenError:
        await set_subscribed(user_id, False)
        return False
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.send_photo(user_id, photo, caption=caption)
            return True
        except Exception:
            log.warning("safe_send_photo retry failed for user %s", user_id, exc_info=True)
            return False
    except Exception:
        log.warning("safe_send_photo failed for user %s", user_id, exc_info=True)
        return False


async def broadcast_photo(
    bot: Bot, user_ids, photo: str, caption: str | None = None, delay: float = 0.05
) -> int:
    """Send a photo to each user id; returns the number of successful sends."""
    sent = 0
    for uid in user_ids:
        if await safe_send_photo(bot, uid, photo, caption):
            sent += 1
        if delay:
            await asyncio.sleep(delay)
    return sent


async def maybe_relay_announcement(bot: Bot, user_id: int) -> bool:
    """If the current week's run is already announced, send its Да/Нет card.

    Used right after a user subscribes so mid-week joiners don't miss the
    currently open registration. Returns whether the card was sent.
    """
    week = current_week_key()
    if await get_announced_week() != week:
        return False
    text = await get_text("monday_open")
    return await safe_send(bot, user_id, text, reply_markup=monday_kb(week))

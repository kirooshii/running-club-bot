"""Common handlers: /start, /stop, /help."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..config import config
from ..db import ensure_user, is_subscribed, set_subscribed
from ..keyboards import subscribe_kb
from ..texts import get_text
from ..utils import maybe_relay_announcement, resolve_message, safe_send

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id)
    if await is_subscribed(user_id):
        await message.answer("Ты уже подписан.")
        # Re-send the current run's card if registration is already open.
        await maybe_relay_announcement(bot, user_id)
    else:
        text, photo = await resolve_message("welcome")
        if photo:
            await bot.send_photo(user_id, photo, caption=text, reply_markup=subscribe_kb())
        else:
            await message.answer(text, reply_markup=subscribe_kb())


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    await set_subscribed(message.from_user.id, False)
    await message.answer(await get_text("unsubscribed"))


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    is_admin = message.from_user.id in config.admin_ids
    lines = ["Доступные команды:", "/start — подписаться", "/stop — отписаться"]
    if is_admin:
        lines.append("/admin — админ-панель")
    await message.answer("\n".join(lines))

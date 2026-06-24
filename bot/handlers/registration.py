"""Registration flow: subscribe, yes/no, cancel, take freed spot.

The «Отменить регистрацию» button is a **persistent reply keyboard** pinned at
the bottom of the chat, so it is always available for registered/waiting users
(task: «кнопка всегда должна быть доступна»). Inline buttons are used only for
one-off choices (Да/Нет, Занять место, Передумать).
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..db import (
    DECLINED,
    REGISTERED,
    cancel_registration,
    ensure_user,
    get_status,
    is_registration_open,
    register_user,
    set_status,
    set_subscribed,
    take_spot,
)
from ..keyboards import (
    CANCEL_BUTTON_TEXT,
    RegCB,
    SimpleCB,
    cancel_reply_kb,
    change_mind_kb,
)
from ..texts import get_text
from ..utils import maybe_relay_announcement, notify_waiting
from ..weeks import current_week_key

router = Router()


def _week(callback_data: RegCB) -> str:
    return callback_data.week or current_week_key()


async def _clear_inline(cb: CallbackQuery) -> None:
    """Remove the inline buttons from the originating message, if possible."""
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def _do_cancel(bot: Bot, user_id: int, week: str) -> None:
    """Cancel an active registration/waiting entry.

    Always sends the response as a new message carrying ``ReplyKeyboardRemove``
    so the persistent bottom button is cleared once there is nothing to cancel.
    Frees the spot and notifies the waiting list when applicable.
    """
    prev = await cancel_registration(user_id, week)
    if prev == REGISTERED:
        await bot.send_message(
            user_id, await get_text("cancelled"), reply_markup=ReplyKeyboardRemove()
        )
        # Only invite claims while registration is still open.
        if await is_registration_open(week):
            await notify_waiting(bot, week)
    elif prev == "waiting":
        await bot.send_message(
            user_id,
            await get_text("cancelled_waiting"),
            reply_markup=ReplyKeyboardRemove(),
        )
    else:  # none / not_active
        await bot.send_message(
            user_id,
            "Активной записи нет.",
            reply_markup=ReplyKeyboardRemove(),
        )


# --------------------------------------------------------------------------- #
# persistent bottom button: "Отменить регистрацию"
# --------------------------------------------------------------------------- #
@router.message(F.text == CANCEL_BUTTON_TEXT)
async def on_cancel_text(message: Message, bot: Bot) -> None:
    await _do_cancel(bot, message.from_user.id, current_week_key())


# --------------------------------------------------------------------------- #
# subscribe (from /start keyboard)
# --------------------------------------------------------------------------- #
@router.callback_query(SimpleCB.filter(F.action == "subscribe"))
async def on_subscribe(cb: CallbackQuery, bot: Bot) -> None:
    user_id = cb.from_user.id
    await ensure_user(user_id)
    await set_subscribed(user_id, True)
    try:
        await cb.message.edit_text(await get_text("subscribed"), reply_markup=None)
    except Exception:
        await bot.send_message(user_id, await get_text("subscribed"))
    # If a run is already announced for the current week, send its card too.
    await maybe_relay_announcement(bot, user_id)
    await cb.answer("Подписка оформлена")


# --------------------------------------------------------------------------- #
# yes -> register (or join waiting list) + pin the cancel button
# --------------------------------------------------------------------------- #
@router.callback_query(RegCB.filter(F.action == "yes"))
async def on_yes(cb: CallbackQuery, callback_data: RegCB, bot: Bot) -> None:
    user_id = cb.from_user.id
    week = _week(callback_data)
    await ensure_user(user_id)

    if not await is_registration_open(week):
        await cb.answer(await get_text("registration_closed"), show_alert=True)
        return

    result = await register_user(user_id, week)
    await _clear_inline(cb)

    key = {
        "already_registered": "already_registered",
        "registered": "confirm_registered",
        "waiting": "confirm_waiting",
    }[result]
    # New message so we can attach the persistent reply keyboard.
    await bot.send_message(
        user_id, await get_text(key), reply_markup=cancel_reply_kb()
    )
    await cb.answer()


# --------------------------------------------------------------------------- #
# no -> decline (but still allow changing mind)
# --------------------------------------------------------------------------- #
@router.callback_query(RegCB.filter(F.action == "no"))
async def on_no(cb: CallbackQuery, callback_data: RegCB, bot: Bot) -> None:
    user_id = cb.from_user.id
    week = _week(callback_data)
    await ensure_user(user_id)
    if await get_status(user_id, week) == REGISTERED:
        await cb.answer(await get_text("already_registered"), show_alert=True)
        return
    await set_status(user_id, week, DECLINED)

    await _clear_inline(cb)
    await bot.send_message(
        user_id, await get_text("decline_no"), reply_markup=change_mind_kb(week)
    )
    await cb.answer()


# --------------------------------------------------------------------------- #
# cancel via inline button (e.g. on the Friday reminder / take-spot message)
# --------------------------------------------------------------------------- #
@router.callback_query(RegCB.filter(F.action == "cancel"))
async def on_cancel(cb: CallbackQuery, callback_data: RegCB, bot: Bot) -> None:
    await _clear_inline(cb)
    await _do_cancel(bot, cb.from_user.id, _week(callback_data))
    await cb.answer()


# --------------------------------------------------------------------------- #
# take -> first-click-wins the freed spot
# --------------------------------------------------------------------------- #
@router.callback_query(RegCB.filter(F.action == "take"))
async def on_take(cb: CallbackQuery, callback_data: RegCB, bot: Bot) -> None:
    user_id = cb.from_user.id
    week = _week(callback_data)

    if not await is_registration_open(week):
        await cb.answer(await get_text("registration_closed"), show_alert=True)
        return

    result = await take_spot(user_id, week)
    if result == "ok":
        await _clear_inline(cb)
        await bot.send_message(
            user_id, await get_text("spot_taken_success"), reply_markup=cancel_reply_kb()
        )
        await cb.answer("Место твоё!")
    elif result == "full":
        await cb.answer(await get_text("spot_taken"), show_alert=True)
    else:  # not_waiting
        await cb.answer("Ты больше не в листе ожидания", show_alert=True)

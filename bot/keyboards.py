"""Bot keyboards: inline (per-message) and reply (persistent bottom)."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

#: Text of the persistent bottom button. Matched by a message handler.
CANCEL_BUTTON_TEXT = "Отменить регистрацию"


class RegCB(CallbackData, prefix="rc"):
    action: str   # yes | no | cancel | take
    week: str


class SimpleCB(CallbackData, prefix="s"):
    action: str   # subscribe


def _btn(text: str, action: str, week: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, callback_data=RegCB(action=action, week=week).pack()
    )


def monday_kb(week: str) -> InlineKeyboardMarkup:
    """Initial Monday message: [Да, участвую] [Нет, не смогу]."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Да, участвую", "yes", week),
        _btn("Нет, не смогу", "no", week),
    ]])


def cancel_kb(week: str) -> InlineKeyboardMarkup:
    """Single [Отменить регистрацию] button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Отменить регистрацию", "cancel", week),
    ]])


def take_spot_kb(week: str) -> InlineKeyboardMarkup:
    """Offered to waiting users when a spot frees up."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Занять место", "take", week)],
        [_btn("Отменить", "cancel", week)],
    ])


def change_mind_kb(week: str) -> InlineKeyboardMarkup:
    """Shown on the "no" message so a user can still register."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Передумать — участвую", "yes", week),
    ]])


def subscribe_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Подписаться", callback_data=SimpleCB(action="subscribe").pack()
        ),
    ]])


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm/cancel an admin photo broadcast."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Разослать всем", callback_data="bc:yes")],
        [InlineKeyboardButton(text="Отмена", callback_data="bc:no")],
    ])


def cancel_reply_kb() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard with the cancel button.

    Stays pinned at the bottom of the chat so a registered user can cancel at
    any time without scrolling — satisfies «кнопка всегда должна быть доступна».
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )

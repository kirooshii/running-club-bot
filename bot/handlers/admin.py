"""Admin commands. Accessible only to users in ADMIN_IDS."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import CallbackQuery, Message

from ..config import config
from ..db import (
    clear_announced_week,
    delete_text_photo,
    get_capacity,
    get_subscribed_users,
    get_text_photo,
    get_users_by_status,
    is_registration_open,
    set_capacity,
    set_text_photo,
    count_subscribed,
    week_stats,
)
from ..keyboards import broadcast_confirm_kb
from ..scheduler import open_registration, send_reminders
from ..texts import DEFAULT_TEXTS, get_text, reset_text, set_text
from ..utils import broadcast, broadcast_photo, notify_waiting
from ..weeks import current_week_key

router = Router()

# Pending photo broadcast per admin: {admin_id: {"file_id", "caption"}}.
_pending_photo: dict[int, dict] = {}
# Pending setphoto: {admin_id: text_key}.
_pending_setphoto: dict[int, str] = {}


class IsAdmin(Filter):
    async def __call__(self, obj) -> bool:
        return obj.from_user.id in config.admin_ids


HELP_TEXT = (
    "📊 Админ-панель\n\n"
    "Команды:\n"
    "/capacity — текущая вместимость\n"
    "/setcapacity N — изменить вместимость\n"
    "/broadcast текст — рассылка по подписчикам\n"
    "(или отправь фото с подписью — разошлём по кнопке)\n"
    "/texts — список редактируемых текстов\n"
    "/settext ключ текст — переопределить текст\n"
    "/resettext ключ — сбросить текст\n"
    "/setphoto ключ — прикрепить фото к тексту (затем отправь фото)\n"
    "/resetphoto ключ — удалить прикреплённое фото\n"
    "/trigger_open — открыть запись (рассылка понедельника)\n"
    "/trigger_close — закрыть запись (без новых заявок)\n"
    "/trigger_reminder — запустить напоминания\n"
)


@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message) -> None:
    week = current_week_key()
    stats = await week_stats(week)
    cap = await get_capacity()
    subs = await count_subscribed()
    status = "открыта" if await is_registration_open(week) else "закрыта"
    info = (
        f"📊 Текущая неделя: {week}\n"
        f"📝 Запись: {status}\n"
        f"👥 Подписчиков: {subs}\n"
        f"🔢 Вместимость: {cap}\n\n"
        f"✅ Записано: {stats['registered']}\n"
        f"⏳ Лист ожидания: {stats['waiting']}\n"
        f"❌ Отказались: {stats['declined']}\n"
        f"🚫 Отменили: {stats['cancelled']}\n"
    )
    await message.answer(info + "\n" + HELP_TEXT)


@router.message(Command("capacity"), IsAdmin())
async def cmd_capacity(message: Message) -> None:
    await message.answer(f"Текущая вместимость: {await get_capacity()}")


@router.message(Command("setcapacity"), IsAdmin())
async def cmd_setcapacity(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Использование: /setcapacity N (положительное число)")
        return
    new_cap, old_cap = int(arg), await get_capacity()
    await set_capacity(new_cap)
    await message.answer(f"Вместимость изменена: {old_cap} → {new_cap}.")

    if new_cap > old_cap:
        week = current_week_key()
        waiters = await get_users_by_status(week, "waiting")
        if waiters:
            await notify_waiting(message.bot, week)
            await message.answer(f"Уведомление отправлено {len(waiters)} ждущим.")


@router.message(Command("broadcast"), IsAdmin())
async def cmd_broadcast(message: Message, command: CommandObject) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer("Использование: /broadcast <текст>")
        return
    users = await get_subscribed_users()
    sent = await broadcast(message.bot, users, text)
    await message.answer(f"Отправлено {sent}/{len(users)} подписчикам.")


@router.message(Command("texts"), IsAdmin())
async def cmd_texts(message: Message) -> None:
    lines = []
    for key in sorted(DEFAULT_TEXTS):
        photo = await get_text_photo(key)
        marker = " 🖼" if photo else ""
        lines.append(f"{key}{marker}")
    await message.answer(
        f"Редактируемые тексты:\n" + "\n".join(lines) + "\n\n"
        "Пример: /settext welcome Привет!\n"
        "/setphoto ключ — прикрепить фото"
    )


@router.message(Command("settext"), IsAdmin())
async def cmd_settext(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Нужны ключ и текст. Пример: /settext welcome Новый текст"
        )
        return
    key, value = parts
    if key not in DEFAULT_TEXTS:
        await message.answer(f"Неизвестный ключ «{key}». Список: /texts")
        return
    await set_text(key, value)
    await message.answer(
        f"Текст «{key}» обновлён:\n\n{await get_text(key)}"
    )


@router.message(Command("resettext"), IsAdmin())
async def cmd_resettext(message: Message, command: CommandObject) -> None:
    key = (command.args or "").strip()
    if not await reset_text(key):
        await message.answer(f"Неизвестный ключ «{key}». Список: /texts")
        return
    await message.answer(f"Текст «{key}» сброшен к значению по умолчанию.")


@router.message(Command("setphoto"), IsAdmin())
async def cmd_setphoto(message: Message, command: CommandObject) -> None:
    key = (command.args or "").strip()
    if key not in DEFAULT_TEXTS:
        await message.answer(f"Неизвестный ключ «{key}». Список: /texts")
        return
    _pending_setphoto[message.from_user.id] = key
    await message.answer(f"Отправь фото для текста «{key}» (с подписью или без).")


@router.message(Command("resetphoto"), IsAdmin())
async def cmd_resetphoto(message: Message, command: CommandObject) -> None:
    key = (command.args or "").strip()
    if key not in DEFAULT_TEXTS:
        await message.answer(f"Неизвестный ключ «{key}». Список: /texts")
        return
    await delete_text_photo(key)
    await message.answer(f"Фото для «{key}» удалено.")


@router.message(Command("trigger_open"), IsAdmin())
async def cmd_trigger_open(message: Message) -> None:
    await message.answer("Запускаю рассылку открытия записи...")
    sent = await open_registration(message.bot)
    await message.answer(f"Готово. Отправлено: {sent}.")


@router.message(Command("trigger_close"), IsAdmin())
async def cmd_trigger_close(message: Message) -> None:
    week = current_week_key()
    await clear_announced_week()
    stats = await week_stats(week)
    await message.answer(
        f"🔒 Запись на неделю {week} закрыта.\n"
        f"Новые заявки и «Занять место» больше не принимаются.\n"
        f"Зарегистрировано: {stats['registered']} · в ожидании: {stats['waiting']}."
    )


@router.message(Command("trigger_reminder"), IsAdmin())
async def cmd_trigger_reminder(message: Message) -> None:
    await message.answer("Запускаю напоминания...")
    sent = await send_reminders(message.bot)
    await message.answer(f"Готово. Напоминаний отправлено: {sent}.")


# photo handler: check for /setphoto caption first, then pending setphoto, then broadcast
@router.message(F.photo, IsAdmin())
async def on_admin_photo(message: Message) -> None:
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    admin_id = message.from_user.id

    # Support inline "/setphoto key" in the photo caption.
    if caption.startswith("/setphoto"):
        parts = caption.split(maxsplit=1)
        key = parts[1].strip() if len(parts) > 1 else ""
        if key in DEFAULT_TEXTS:
            await set_text_photo(key, file_id)
            await message.answer(f"Фото прикреплено к «{key}».")
        else:
            await message.answer(f"Неизвестный ключ «{key}». Список: /texts")
        return

    # Two-step flow: /setphoto <key> then send a photo.
    key = _pending_setphoto.pop(admin_id, None)
    if key:
        await set_text_photo(key, file_id)
        await message.answer(f"Фото прикреплено к «{key}».")
        return

    # Default: broadcast this photo.
    _pending_photo[admin_id] = {"file_id": file_id, "caption": caption}
    preview = (caption + "\n\n" if caption else "") + "📩 Разослать это фото всем подписчикам?"
    await message.answer(preview, reply_markup=broadcast_confirm_kb())


@router.callback_query(F.data == "bc:yes", IsAdmin())
async def on_broadcast_photo_confirm(cb: CallbackQuery, bot: Bot) -> None:
    data = _pending_photo.pop(cb.from_user.id, None)
    if not data:
        await cb.answer("Нет ожидающего фото.", show_alert=True)
        return
    users = await get_subscribed_users()
    sent = await broadcast_photo(
        bot, users, data["file_id"], data["caption"] or None
    )
    try:
        await cb.message.edit_text(f"📸 Разослано {sent}/{len(users)} подписчикам.")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "bc:no", IsAdmin())
async def on_broadcast_photo_cancel(cb: CallbackQuery) -> None:
    _pending_photo.pop(cb.from_user.id, None)
    try:
        await cb.message.edit_text("Рассылка фото отменена.")
    except Exception:
        pass
    await cb.answer("Отменено")

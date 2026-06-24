"""User-facing message texts.

All texts are Russian placeholders. ``{event_info}`` is filled from the
``EVENT_INFO`` setting. Any key can be overridden at runtime via the admin
``/settext`` command (stored in the DB) or permanently by editing
``DEFAULT_TEXTS`` below.
"""
from __future__ import annotations

from .config import config
from .db import get_setting, set_setting

DEFAULT_TEXTS: dict[str, str] = {
    "welcome": (
        "Привет! Это бот бегового клуба.\n\n"
        "Каждый понедельник здесь открывается запись на ближайшую пробежку "
        "({event_info}). Нажми кнопку ниже, чтобы подписаться на уведомления."
    ),
    "subscribed": (
        "Поздравляем с регистрацией!\n\n"
        "Всю информацию о следующем забеге пришлём ближе к дате тренировки.\n"
        "Побежали вместе!"
    ),
    "unsubscribed": "Ты отписан от рассылки. Подписаться снова — /start.",
    "monday_open": (
        "Открыта запись на ближайший беговой клуб!\n\n"
        "Когда: {event_info}.\n\n"
        "Записываешься?"
    ),
    "confirm_registered": (
        "Запись принята! Ждём тебя на клубе.\n\n"
        "Если планы изменятся — отмени запись кнопкой ниже, чтобы место "
        "досталось кому-то ещё."
    ),
    "confirm_waiting": (
        "Мест уже нет — ты в листе ожидания.\n\n"
        "Если кто-то отменит запись, пришлю уведомление и ты сможешь занять "
        "свободное место."
    ),
    "decline_no": (
        "Жаль, что не получится. Впереди ещё много беговых клубов — "
        "{event_info}. До встречи!"
    ),
    "cancelled": "Запись отменена, место освобождено.",
    "cancelled_waiting": "Ты удалён из листа ожидания.",
    "spot_freed": (
        "Освободилось место на беговый клуб! Можешь занять его кнопкой ниже "
        "(достанется тому, кто нажмёт первым)."
    ),
    "spot_taken": "Место уже заняли — ты остаёшься в листе ожидания.",
    "spot_taken_success": "Отлично, место твоё! Запись подтверждена.",
    "reminder": (
        "Напоминание: завтра беговой клуб, ждём тебя!\n\n"
        "Если планы изменились — отмени запись кнопкой ниже."
    ),
    "already_registered": "Ты уже записан на этот клуб.",
    "registration_closed": "Запись на этот клуб уже закрыта.",
}


def _format(value: str) -> str:
    try:
        return value.format(event_info=config.event_info)
    except (KeyError, IndexError):
        return value


async def get_text(key: str) -> str:
    raw = await get_setting(f"text:{key}")
    if raw is None:
        raw = DEFAULT_TEXTS.get(key, f"[{key}]")
    return _format(raw)


async def set_text(key: str, value: str) -> None:
    await set_setting(f"text:{key}", value)


async def reset_text(key: str) -> bool:
    """Remove an override, reverting to the built-in default."""
    from .db import _connect  # local import to avoid cycle

    if key not in DEFAULT_TEXTS:
        return False
    async with _connect() as db:
        await db.execute("DELETE FROM settings WHERE key = ?", (f"text:{key}",))
        await db.commit()
    return True

"""User-facing message texts.

``{event_info}`` is auto-computed as the Saturday run date (e.g. ``4 июля``)
for the given registration week. Any text key can be overridden at runtime via
the admin ``/settext`` command (stored in the DB) or permanently by editing
``DEFAULT_TEXTS`` below.
"""
from __future__ import annotations

from .db import get_setting, set_setting
from .weeks import format_run_date, run_date_from_week

DEFAULT_TEXTS: dict[str, str] = {
    "welcome": (
        "Привет! Мы — беговой клуб WellProducts x Finch. То самое «третье место», где можно выдохнуть после работы, найти друзей и зарядиться энергией.\n"
        "Чтобы не пропустить наши забеги и классные конкурсы — подписывайся на канал."
    ),
    "subscribed": (
        "Поздравляем с регистрацией!\n\n"
    ),
    "unsubscribed": "Ты отписан от рассылки. Подписаться снова — /start.",
    "monday_open": (
        "Открываем запись на забег <b>{event_info}</b>!\n\n"
        "В эту субботу снова встречаемся в Finch, чтобы размяться, отключить голову от рабочих чатов и по-настоящему настроиться на выходные.\n\n"
        "<b>Детали встречи</b>:\n\n"
        "<b>Дата</b>: {event_info}\n"
        "<b>Локация</b>: кафе Finch (Газетный переулок, 5)\n"
        "<b>Сбор</b>: 18:00\n"
        "<b>Разминка</b>: 18:30\n\n"

        "<b>Кто ведет?</b>\n"
        "Валерий Вершинин — фитнес-эксперт с 12-летним стажем, тренер FPA и основатель аутдор-движения. В прошлом — наставник топовых клубов World Class и X-Fit. С ним безопасно и драйвово!\n\n"

        "<b>Что ждет на финише?</b>\n"
        "Бодрящий фильтр-кофе, витаминизированная вода и лимонады WellDrink и сытные батончики WellBar. Восстанавливаем силы с удовольствием!\n\n"
        "Жми на кнопку ниже, чтобы записаться. Количество мест ограничено!"
    ),

    "confirm_registered": (
        "Отлично! Ты с нами!\n"
        "Мы сохранили твое место и обязательно напомним о всех деталях перед стартом.\n"
        "А пока — готовь кроссовки и хорошее настроение. Побежали вместе! 🏃‍♂️"
    ),
    "confirm_waiting": (
        "Регистрация на этот забег закрыта. Ты автоматически попал в лист ожидания.\n"
        "Как только появится свободное место — мы сразу же пришлем тебе  уведомление.\n\n"
        "А пока можешь подкрепиться белком и хорошенько отдохнуть. В следующий раз обязательно успеем!"
    ),
    "decline_no": (
        "Жаль, что не получится. Следующий забег — {event_info}. До встречи!"
    ),
    "cancelled": (
        "Регистрация отменена. Спасибо, что предупредил!\n"
        "Твое место освободилось для другого бегуна. Мы будем скучать, но обязательно ждем тебя на следующей тренировке в нашем клубе. "
    ),
    "cancelled_waiting": "Ты удалён из листа ожидания.",
    "spot_freed": (
        "🚨 Ура! Освободилось место!\n\n"
        "Пока кто-то решил остаться дома, мы подумали о тебе. Хочешь пробежаться с нами?\n\n"
        "<b>Детали</b> встречи:\n\n"
        "<b>Дата</b>: {event_info}\n"
        "<b>Локация</b>: кафе Finch (Газетный переулок, 5)\n"
        "<b>Сбор</b>: 18:00\n"
        "<b>Разминка</b>: 18:30\n"
        "Жми на кнопку ниже, чтобы записаться"
    ),
    "spot_taken": "Место уже заняли — ты остаёшься в листе ожидания.",
    "spot_taken_success": "Отлично, место твоё! Запись подтверждена.",
    
    "reminder": (
        "Напоминаем: наш забег уже ЗАВТРА!\n\n"
        "Разминаемся и готовимся к классному вечеру в компании WellProducts x Finch.\n\n"

        "🕕 Сбор в 18:00 (разминка в 18:30)\n"
        "📍 Finch на Газетном, 5\n\n"
        "Важно: если планы изменились и ты не сможешь прийти, пожалуйста, отмени регистрацию. Пожалуйста, не забудь отменить регистрацию, если твои планы изменились 💚\n\n"
        "До встречи!"
    ),
    "already_registered": "Ты уже записан на этот клуб.",
    "registration_closed": "Запись на этот клуб уже закрыта.",
}


def _format(value: str, week: str | None = None) -> str:
    if not week:
        return value
    try:
        run = run_date_from_week(week)
    except (ValueError, TypeError):
        return value
    try:
        return value.format(event_info=format_run_date(run))
    except (KeyError, IndexError, ValueError):
        return value


async def get_text(key: str, week: str | None = None) -> str:
    raw = await get_setting(f"text:{key}")
    if raw is None:
        raw = DEFAULT_TEXTS.get(key, f"[{key}]")
    return _format(raw, week)


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

"""Entrypoint: python -m bot"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import config
from .db import init_db, seed_settings
from .handlers import admin, common, registration
from .scheduler import schedule_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("lada-bot")


async def main() -> None:
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    scheduler = AsyncIOScheduler(timezone=config.timezone)

    dp.include_router(common.router)
    dp.include_router(registration.router)
    dp.include_router(admin.router)

    @dp.startup()
    async def on_startup(bot: Bot) -> None:
        await init_db()
        await seed_settings()
        schedule_jobs(scheduler, bot)
        scheduler.start()
        log.info("Bot started. Admins=%s", config.admin_ids or "<none>")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

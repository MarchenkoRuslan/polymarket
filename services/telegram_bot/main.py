"""Telegram bot — minimal launcher for the Web App dashboard.

Provides /start command and a persistent menu button that opens
the Polymarket dashboard as a Telegram Web App (Mini App).

Usage:
    python -m services.telegram_bot.main

Required env vars:
    TELEGRAM_BOT_TOKEN  — BotFather token
    WEBAPP_URL          — HTTPS URL of the deployed Web App (e.g. https://example.com/webapp)
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import TELEGRAM_BOT_TOKEN, WEBAPP_URL

logger = logging.getLogger(__name__)


async def run_bot() -> None:
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.filters import CommandStart
        from aiogram.types import (
            InlineKeyboardButton,
            InlineKeyboardMarkup,
            MenuButtonWebApp,
            Message,
            WebAppInfo,
        )
    except ImportError:
        logger.error(
            "aiogram is not installed. Install it with: pip install aiogram>=3.4"
        )
        return

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set — skipping bot startup")
        return
    if not WEBAPP_URL:
        logger.warning("WEBAPP_URL is not set — bot will start but menu button won't work")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        kb = None
        if WEBAPP_URL:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Открыть дашборд",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )],
            ])
        await message.answer(
            "Добро пожаловать в Polymarket Trading Bot!\n\n"
            "Откройте дашборд, чтобы смотреть рынки, ML-сигналы и результаты.",
            reply_markup=kb,
        )

    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Дашборд",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                ),
            )
            logger.info("Menu button set → %s", WEBAPP_URL)
        except Exception as exc:
            logger.warning("Failed to set menu button: %s", exc)

    logger.info("Starting Telegram bot polling…")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()

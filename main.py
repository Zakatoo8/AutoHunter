import asyncio
import logging
import uvicorn
from contextlib import suppress

from config import settings
from database.db_manager import init_db
from engine.hunter_engine import HunterEngine
from bot.telegram_bot import get_bot, dp
from web.app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AutoHunterMain")


async def run_bot():
    bot = get_bot()
    if bot:
        logger.info("Starting Telegram Bot Polling...")
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Telegram Bot error: {e}")
    else:
        logger.warning("No TG_BOT_TOKEN set. Telegram bot polling disabled.")


async def run_web():
    config = uvicorn.Config(app=app, host=settings.WEB_HOST, port=settings.WEB_PORT, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    logger.info("Initializing AutoHunter...")
    await init_db()

    engine = HunterEngine()

    # Run Hunter Engine, Telegram Bot, and Web API concurrently
    tasks = [
        asyncio.create_task(engine.start(), name="HunterEngine"),
        asyncio.create_task(run_web(), name="WebServer")
    ]

    if settings.TG_BOT_TOKEN:
        tasks.append(asyncio.create_task(run_bot(), name="TelegramBot"))

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down AutoHunter gracefully...")
        engine.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAutoHunter stopped.")

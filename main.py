import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import config
from database import Database
from handlers import (
    common_router,
    location_router,
    events_router,
    services_router,
    reminders_router,
    news_router,
    admin_router,
)
from services.scheduler import reminder_scheduler_task

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def setup_dispatcher(db: Database) -> Dispatcher:
    """Создает и конфигурирует экземпляр Dispatcher, подключая роутеры и базу данных."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Внедрение зависимости базы данных во все хэндлеры
    dp["db"] = db

    # Регистрация роутеров
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(events_router)
    dp.include_router(location_router)
    dp.include_router(services_router)
    dp.include_router(reminders_router)
    dp.include_router(news_router)

    return dp


async def on_startup_webhook(bot: Bot, db: Database) -> None:
    """Хук старта для режима Webhook."""
    logger.info("Инициализация базы данных...")
    await db.init_tables()

    webhook_url = config.webhook_url
    logger.info("Установка Telegram Webhook: %s", webhook_url)
    await bot.set_webhook(
        url=webhook_url,
        secret_token=config.webhook_secret,
        drop_pending_updates=True,
        allowed_updates=["message", "edited_message", "callback_query"]
    )

    # Запуск фонового планировщика напоминаний
    asyncio.create_task(reminder_scheduler_task(bot=bot, db=db, interval_seconds=3600))
    logger.info("Бот успешно запущен в режиме Webhook на порту %d!", config.app_port)


async def on_shutdown_webhook(bot: Bot) -> None:
    """Хук остановки для режима Webhook."""
    logger.info("Остановка Webhook и закрытие сессии бота...")
    try:
        await bot.delete_webhook()
    except Exception as e:
        logger.warning("Ошибка при удалении вебхука: %e", e)
    await bot.session.close()


def run_webhook(bot: Bot, dp: Dispatcher, db: Database) -> None:
    """Запуск бота в режиме Webhook (для Railway / Production)."""
    app = web.Application()

    # Регистрация обработчика входящих запросов от Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.webhook_secret,
    )
    webhook_requests_handler.register(app, path=config.webhook_path)

    async def on_app_startup(app: web.Application) -> None:
        await on_startup_webhook(bot, db)

    async def on_app_shutdown(app: web.Application) -> None:
        await on_shutdown_webhook(bot)

    app.on_startup.append(on_app_startup)
    app.on_shutdown.append(on_app_shutdown)

    # Настройка интеграции aiogram с aiohttp
    setup_application(app, dp, bot=bot)

    # Запуск веб-сервера aiohttp
    web.run_app(
        app,
        host=config.app_host,
        port=config.app_port,
        print=logger.info
    )


async def run_polling(bot: Bot, dp: Dispatcher, db: Database) -> None:
    """Запуск бота в режиме Long Polling (для локальной разработки)."""
    logger.info("Инициализация базы данных SQLite (%s)...", config.db_path)
    await db.init_tables()

    scheduler_task = asyncio.create_task(
        reminder_scheduler_task(bot=bot, db=db, interval_seconds=3600)
    )

    try:
        logger.info("Бот запущен в режиме Long Polling!")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot,
            allowed_updates=["message", "edited_message", "callback_query"]
        )
    finally:
        logger.info("Завершение работы бота...")
        scheduler_task.cancel()
        await bot.session.close()


def main() -> None:
    """Точка входа."""
    if not config.bot_token:
        logger.critical("ОШИБКА: BOT_TOKEN не задан! Проверьте переменные окружения.")
        sys.exit(1)

    db = Database(db_path=config.db_path)
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = setup_dispatcher(db=db)

    logger.info("Выбранный режим работы: %s", config.mode.upper())

    if config.mode == "webhook":
        if not config.webhook_base_url:
            logger.critical(
                "ОШИБКА: Для режима Webhook требуется указать WEBHOOK_BASE_URL "
                "или RAILWAY_PUBLIC_DOMAIN в переменных окружения!"
            )
            sys.exit(1)
        run_webhook(bot, dp, db)
    else:
        asyncio.run(run_polling(bot, dp, db))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")

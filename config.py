import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


@dataclass
class Config:
    """Конфигурация бота и глобальные константы."""
    bot_token: str
    admin_ids: list[int]
    db_path: str
    danger_radius_meters: float
    broadcast_radius_meters: float

    # Настройки режима работы (Polling vs Webhook)
    mode: str  # "polling" или "webhook"
    app_host: str
    app_port: int
    webhook_path: str
    webhook_secret: str
    webhook_base_url: str

    @property
    def webhook_url(self) -> str:
        """Полный URL вебхука для Telegram."""
        base = self.webhook_base_url.rstrip("/")
        path = self.webhook_path if self.webhook_path.startswith("/") else f"/{self.webhook_path}"
        return f"{base}{path}" if base else ""


def load_config() -> Config:
    """
    Загружает конфигурацию из переменных окружения с автоопределением среды Railway.
    """
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        print("[ВНИМАНИЕ] BOT_TOKEN не установлен в .env! Укажите токен перед запуском.")

    admin_ids_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = [
        int(adm.strip())
        for adm in admin_ids_raw.split(",")
        if adm.strip().isdigit()
    ]

    # База данных: если в Railway примонтирован Persistent Volume /data, сохраняем туда
    default_db = "/data/bot_database.sqlite3" if os.path.exists("/data") else "bot_database.sqlite3"
    db_path = os.getenv("DB_PATH", default_db)

    danger_radius = float(os.getenv("DANGER_RADIUS_METERS", "500.0"))
    broadcast_radius = float(os.getenv("BROADCAST_RADIUS_METERS", "5000.0"))

    # Определение порта: Railway передает переменную PORT
    app_port = int(os.getenv("PORT", os.getenv("APP_PORT", "8080")))
    app_host = os.getenv("APP_HOST", "0.0.0.0")

    # Определение базового URL вебхука:
    # В Railway при включении домена доступна переменная RAILWAY_PUBLIC_DOMAIN
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip()

    if not webhook_base_url and railway_domain:
        webhook_base_url = f"https://{railway_domain}"

    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
    webhook_secret = os.getenv("WEBHOOK_SECRET", "super_secret_car_bot_token")

    # Режим работы: если задан WEBHOOK_BASE_URL или RAILWAY_PUBLIC_DOMAIN, по умолчанию webhook
    default_mode = "webhook" if webhook_base_url else "polling"
    mode = os.getenv("MODE", default_mode).lower().strip()

    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        db_path=db_path,
        danger_radius_meters=danger_radius,
        broadcast_radius_meters=broadcast_radius,
        mode=mode,
        app_host=app_host,
        app_port=app_port,
        webhook_path=webhook_path,
        webhook_secret=webhook_secret,
        webhook_base_url=webhook_base_url,
    )


# Глобальный экземпляр настроек
config = load_config()

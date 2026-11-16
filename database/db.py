import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """
    Класс для асинхронной работы с базой данных SQLite через aiosqlite.
    Инкапсулирует создание таблиц, сохранение координат, событий и напоминаний.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_tables(self) -> None:
        """
        Создает необходимые таблицы в базе данных при первом запуске бота,
        а также заполняет тестовыми точками полезных сервисов (шиномонтажи, эвакуаторы).
        """
        import os
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError:
                # Если путь недоступен (например /data без прав), переключаемся на локальный
                self.db_path = "bot_database.sqlite3"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # 1. Таблица пользователей и их последних координат
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    latitude REAL,
                    longitude REAL,
                    last_location_update TIMESTAMP,
                    is_live INTEGER DEFAULT 0
                )
            """)

            # 2. Таблица дорожных событий (Народная карта / UGC)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS road_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    category TEXT NOT NULL,
                    description TEXT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # 3. Таблица напоминаний (ОСАГО, ТО, техобслуживание)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reminder_type TEXT NOT NULL,
                    expire_date TEXT NOT NULL,
                    note TEXT,
                    notified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. Таблица новостей и сводок ГАИ
            await db.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 5. Таблица каталога автосервисов (Шиномонтаж, Эвакуатор)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    address TEXT NOT NULL
                )
            """)

            # Заполняем базовыми тестовыми сервисами, если таблица пуста
            cursor = await db.execute("SELECT COUNT(*) as cnt FROM services")
            row = await cursor.fetchone()
            if row and row["cnt"] == 0:
                initial_services = [
                    ("Круглосуточный шиномонтаж 24/7", "tire_service", "+7 (999) 111-22-33", 55.751244, 37.618423, "ул. Тверская, 12"),
                    ("Шиномонтаж «АвтоМастер»", "tire_service", "+7 (999) 222-33-44", 55.760241, 37.605342, "ул. Большая Бронная, 7"),
                    ("Эвакуатор «Быстрая Помощь»", "tow_truck", "+7 (999) 333-44-55", 55.748532, 37.632145, "наб. Котельническая, 1/15"),
                    ("Служба эвакуации 24/7 (до 3.5т)", "tow_truck", "+7 (999) 444-55-66", 55.735111, 37.592314, "Комсомольский пр-т, 28"),
                ]
                await db.executemany(
                    """
                    INSERT INTO services (name, service_type, phone, latitude, longitude, address)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    initial_services
                )

            # Заполняем тестовой новостью, если пусто
            cursor_news = await db.execute("SELECT COUNT(*) as cnt FROM news")
            row_news = await cursor_news.fetchone()
            if row_news and row_news["cnt"] == 0:
                await db.execute(
                    """
                    INSERT INTO news (author_id, title, content)
                    VALUES (?, ?, ?)
                    """,
                    (
                        0,
                        "Операция «Трезвый водитель» в эти выходные",
                        "Госавтоинспекция информирует: с пятницы по воскресенье на ключевых магистралях города пройдут массовые сплошные проверки водителей на состояние опьянения. Будьте внимательны и соблюдайте ПДД!"
                    )
                )

            await db.commit()

    # ==================== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ И ЛОКАЦИЕЙ ====================

    async def upsert_user_location(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        latitude: float,
        longitude: float,
        is_live: bool = False
    ) -> None:
        """
        Сохраняет или обновляет координаты пользователя в БД.
        Фиксирует текущее время обновления и статус live-трансляции.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, latitude, longitude, last_location_update, is_live)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    last_location_update = excluded.last_location_update,
                    is_live = excluded.is_live
            """, (
                user_id,
                username,
                first_name,
                latitude,
                longitude,
                datetime.utcnow().isoformat(),
                1 if is_live else 0
            ))
            await db.commit()

    async def get_user_location(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает последние сохраненные координаты пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT latitude, longitude, last_location_update FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def get_all_active_users_with_location(self) -> List[Dict[str, Any]]:
        """Возвращает список всех пользователей с сохраненной геолокацией."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, latitude, longitude, last_location_update FROM users WHERE latitude IS NOT NULL"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ==================== НАРОДНАЯ КАРТА (ДОРОЖНЫЕ СОБЫТИЯ) ====================

    async def add_road_event(
        self,
        user_id: int,
        category: str,
        description: str,
        latitude: float,
        longitude: float
    ) -> int:
        """
        Добавляет новое дорожное происшествие или предупреждение от пользователя.
        Возвращает ID созданного события.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO road_events (user_id, category, description, latitude, longitude)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, category, description, latitude, longitude))
            await db.commit()
            return cursor.lastrowid

    async def get_active_road_events(self) -> List[Dict[str, Any]]:
        """
        Возвращает список всех активных дорожных событий.
        (События не старше 24 часов).
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, user_id, category, description, latitude, longitude, created_at
                FROM road_events
                WHERE is_active = 1
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ==================== НОВОСТИ ГАИ ====================

    async def add_news(self, author_id: int, title: str, content: str) -> int:
        """Публикует новость или сводку дорожной инспекции."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO news (author_id, title, content)
                VALUES (?, ?, ?)
            """, (author_id, title, content))
            await db.commit()
            return cursor.lastrowid

    async def get_recent_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Возвращает последние новости автоинспекции."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, title, content, created_at
                FROM news
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ==================== НАПОМИНАНИЯ (ОСАГО / ТО) ====================

    async def add_reminder(
        self,
        user_id: int,
        reminder_type: str,
        expire_date: str,
        note: Optional[str] = None
    ) -> int:
        """
        Создает напоминание об окончании срока действия документа (ОСАГО/ТО).
        expire_date передается в формате YYYY-MM-DD.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO reminders (user_id, reminder_type, expire_date, note)
                VALUES (?, ?, ?, ?)
            """, (user_id, reminder_type, expire_date, note or ""))
            await db.commit()
            return cursor.lastrowid

    async def get_user_reminders(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список всех напоминаний пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, reminder_type, expire_date, note, notified
                FROM reminders
                WHERE user_id = ?
                ORDER BY expire_date ASC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        """Удаляет напоминание пользователя по ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM reminders
                WHERE id = ? AND user_id = ?
            """, (reminder_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_due_reminders(self, today_str: str, warning_date_str: str) -> List[Dict[str, Any]]:
        """
        Возвращает напоминания, по которым нужно отправить уведомление:
        - Либо за 7 дней до истечения (notified = 0 и expire_date <= warning_date_str)
        - Либо в день истечения (notified = 1 и expire_date <= today_str)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, user_id, reminder_type, expire_date, note, notified
                FROM reminders
                WHERE (notified = 0 AND expire_date <= ?)
                   OR (notified = 1 AND expire_date <= ?)
            """, (warning_date_str, today_str))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_reminder_status(self, reminder_id: int, status: int) -> None:
        """Обновляет флаг отправки уведомления для напоминания."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE reminders SET notified = ? WHERE id = ?",
                (status, reminder_id)
            )
            await db.commit()

    # ==================== КАТАЛОГ СЕРВИСОВ («ПОМОЩЬ РЯДОМ») ====================

    async def get_all_services(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает список сервисов (всех или конкретного типа: tire_service, tow_truck)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if service_type:
                cursor = await db.execute(
                    "SELECT id, name, service_type, phone, latitude, longitude, address FROM services WHERE service_type = ?",
                    (service_type,)
                )
            else:
                cursor = await db.execute(
                    "SELECT id, name, service_type, phone, latitude, longitude, address FROM services"
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

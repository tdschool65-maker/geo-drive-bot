import time
from typing import Dict, Tuple
from aiogram import Router, F, Bot
from aiogram.types import Message

from config import config
from database import Database
from utils import haversine_distance, format_distance

router = Router(name="location_router")

# Словарь для предотвращения спама уведомлениями (Debounce / Cooldown)
# Структура: {user_id: {event_id: timestamp_последнего_оповещения}}
# Не повторяем предупреждение по одной и той же точке чаще чем раз в 15 минут (900 сек).
ALERT_COOLDOWN_SECONDS = 900
user_alert_history: Dict[int, Dict[int, float]] = {}

# Иконки и читаемые названия категорий событий
CATEGORY_TITLES = {
    "accident": "💥 ДТП / Авария",
    "road_work": "🚧 Дорожные работы",
    "police": "👮 Экипаж ДПС",
    "ice_danger": "❄️ Опасный участок / Гололед"
}


async def check_proximity_and_alert(
    bot: Bot,
    db: Database,
    user_id: int,
    user_lat: float,
    user_lon: float
) -> int:
    """
    Проверяет расстояние от текущих координат водителя до всех активных точек опасности.
    Если расстояние меньше DANGER_RADIUS_METERS (по умолчанию 500 м),
    отправляет водителю экстренное предупреждение.

    Возвращает количество отправленных предупреждений.
    """
    current_time = time.time()
    active_events = await db.get_active_road_events()
    alerts_sent = 0

    if user_id not in user_alert_history:
        user_alert_history[user_id] = {}

    for event in active_events:
        event_id = event["id"]
        event_lat = event["latitude"]
        event_lon = event["longitude"]

        # Вычисляем расстояние по формуле Хаверсина
        distance = haversine_distance(user_lat, user_lon, event_lat, event_lon)

        if distance <= config.danger_radius_meters:
            # Проверяем кулдаун (чтобы не спамить каждые 5 секунд при трансляции Live-локации)
            last_alert_time = user_alert_history[user_id].get(event_id, 0)
            if current_time - last_alert_time > ALERT_COOLDOWN_SECONDS:
                user_alert_history[user_id][event_id] = current_time
                alerts_sent += 1

                cat_title = CATEGORY_TITLES.get(event["category"], "⚠️ Внимание на дороге")
                desc = event["description"] or "Без дополнительных деталей"

                warning_text = (
                    f"⚠️ <b>ВНИМАНИЕ! ОПАСНОСТЬ ВПЕРЕДИ!</b>\n\n"
                    f"📌 <b>Тип события:</b> {cat_title}\n"
                    f"📏 <b>Расстояние:</b> ~<b>{format_distance(distance)}</b>\n"
                    f"📝 <b>Детали:</b> {desc}\n\n"
                    f"<i>Снизьте скорость и соблюдайте безопасную дистанцию!</i>"
                )

                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=warning_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"[ОШИБКА] Не удалось отправить предупреждение пользователю {user_id}: {e}")

    return alerts_sent


@router.message(F.location)
async def handle_single_or_initial_live_location(
    message: Message,
    bot: Bot,
    db: Database
) -> None:
    """
    Обрабатывает получение геопозиции от пользователя:
    как разовой статической геометки, так и первого сообщения при старте Live Location.
    """
    loc = message.location
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    is_live = bool(loc.live_period)

    # Сохраняем актуальные координаты в базу данных SQLite
    await db.upsert_user_location(
        user_id=user_id,
        username=username,
        first_name=first_name,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_live=is_live
    )

    # Проверяем близость к известным опасным точкам
    alerts_sent = await check_proximity_and_alert(
        bot=bot,
        db=db,
        user_id=user_id,
        user_lat=loc.latitude,
        user_lon=loc.longitude
    )

    if is_live:
        await message.answer(
            "🛰 <b>Трансляция Live-локации успешно активирована!</b>\n\n"
            "Бот непрерывно следит за маршрутом в фоновом режиме. "
            "Если на вашем пути возникнет экипаж ДПС, авария или ремонт ближе 500 метров — "
            "вы мгновенно получите голосовое/текстовое предупреждение.",
            parse_mode="HTML"
        )
    else:
        status_msg = (
            "📍 <b>Ваша геопозиция сохранена!</b>\n\n"
            f"Координаты: <code>{loc.latitude:.5f}, {loc.longitude:.5f}</code>\n"
        )
        if alerts_sent > 0:
            status_msg += f"⚠️ В радиусе 500 м обнаружены опасные участки (см. предупреждение выше)."
        else:
            status_msg += "✅ В радиусе 500 м активных опасностей и засад ДПС не обнаружено. Счастливого пути!"

        await message.answer(status_msg, parse_mode="HTML")


@router.edited_message(F.location)
async def handle_live_location_update(
    edited_message: Message,
    bot: Bot,
    db: Database
) -> None:
    """
    Обрабатывает автоматические обновления Live Location (приходят как edited_message).
    Вызывается клиентом Telegram каждые несколько секунд при движении автомобиля.
    """
    loc = edited_message.location
    if not loc:
        return

    user_id = edited_message.from_user.id
    username = edited_message.from_user.username
    first_name = edited_message.from_user.first_name

    # Обновляем координаты на лету
    await db.upsert_user_location(
        user_id=user_id,
        username=username,
        first_name=first_name,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_live=True
    )

    # Проверяем приближение к опасным точкам
    await check_proximity_and_alert(
        bot=bot,
        db=db,
        user_id=user_id,
        user_lat=loc.latitude,
        user_lon=loc.longitude
    )

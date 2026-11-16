from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import config
from database import Database
from keyboards import (
    get_main_menu_kb,
    get_event_categories_kb,
    get_location_request_kb,
    get_skip_or_cancel_kb,
)
from utils import haversine_distance, format_distance

router = Router(name="events_router")


class ReportEventFSM(StatesGroup):
    """Машина состояний (FSM) для процесса отправки дорожного события пользователем."""
    choosing_category = State()
    waiting_for_location = State()
    waiting_for_description = State()


CATEGORY_MAP = {
    "accident": "💥 ДТП / Авария",
    "road_work": "🚧 Ремонт дороги",
    "police": "👮 Экипаж ДПС",
    "ice_danger": "❄️ Гололед / Опасность"
}


@router.message(F.text == "⚠️ Сообщить о событии")
async def start_report_event(message: Message, state: FSMContext) -> None:
    """
    Точка входа в режим «Народная карта»:
    пользователь нажимает кнопку и выбирает категорию происшествия.
    """
    await state.clear()
    await state.set_state(ReportEventFSM.choosing_category)

    await message.answer(
        "📢 <b>Народная карта: фиксация дорожного события</b>\n\n"
        "Выберите категорию происшествия, чтобы предупредить других водителей:",
        parse_mode="HTML",
        reply_markup=get_event_categories_kb()
    )


@router.callback_query(ReportEventFSM.choosing_category, F.data.startswith("event_cat:"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает выбор категории и запрашивает координаты места происшествия.
    """
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await state.set_state(ReportEventFSM.waiting_for_location)

    category_title = CATEGORY_MAP.get(category, category)
    await callback.answer()

    await callback.message.answer(
        f"Выбрано: <b>{category_title}</b>.\n\n"
        "📍 Теперь отправьте геопозицию события:\n"
        "• Нажмите кнопку ниже <b>«📍 Отправить текущую геопозицию»</b>;\n"
        "• Либо прикрепите любую точку на карте через скрепку 📎 ➔ «Геопозиция».",
        parse_mode="HTML",
        reply_markup=get_location_request_kb()
    )


@router.message(ReportEventFSM.waiting_for_location, F.location)
async def process_event_location(message: Message, state: FSMContext) -> None:
    """
    Принимает координаты события и переходит к запросу текстового описания.
    """
    loc = message.location
    await state.update_data(latitude=loc.latitude, longitude=loc.longitude)
    await state.set_state(ReportEventFSM.waiting_for_description)

    await message.answer(
        "📍 Точка зафиксирована!\n\n"
        "✍️ Напишите краткое описание (например: <i>«Левый ряд перекрыт, сильная пробка»</i>) "
        "или нажмите кнопку <b>«Пропустить»</b>, если подробностей нет:",
        parse_mode="HTML",
        reply_markup=get_skip_or_cancel_kb()
    )


@router.message(ReportEventFSM.waiting_for_location)
async def invalid_location_handler(message: Message) -> None:
    """Обработка некорректного ввода, если пользователь отправил текст вместо геопозиции."""
    await message.answer(
        "⚠️ Пожалуйста, отправьте именно <b>геопозицию</b> через кнопку ниже "
        "или через меню вложений (скрепка 📎).",
        parse_mode="HTML",
        reply_markup=get_location_request_kb()
    )


async def finalize_event_creation(
    bot: Bot,
    db: Database,
    user_id: int,
    state_data: dict,
    description: str
) -> int:
    """
    Вспомогательная функция сохранения события в БД и рассылки водителям поблизости.
    Возвращает количество оповещенных водителей.
    """
    category = state_data["category"]
    lat = state_data["latitude"]
    lon = state_data["longitude"]

    # Сохраняем событие в базе данных
    event_id = await db.add_road_event(
        user_id=user_id,
        category=category,
        description=description,
        latitude=lat,
        longitude=lon
    )

    # Ищем пользователей, чьи последние координаты находятся в радиусе вещания (5 км)
    all_users = await db.get_all_active_users_with_location()
    notified_count = 0
    cat_title = CATEGORY_MAP.get(category, "Предупреждение")

    for u in all_users:
        target_uid = u["user_id"]
        # Не отправляем самому автору события
        if target_uid == user_id:
            continue

        target_lat = u["latitude"]
        target_lon = u["longitude"]
        dist = haversine_distance(lat, lon, target_lat, target_lon)

        if dist <= config.broadcast_radius_meters:
            broadcast_msg = (
                "📢 <b>Народная карта: Предупреждение поблизости!</b>\n\n"
                f"📌 <b>Событие:</b> {cat_title}\n"
                f"📏 <b>Расстояние от вас:</b> ~<b>{format_distance(dist)}</b>\n"
                f"📝 <b>Детали:</b> {description or 'Информация отсутствует'}\n\n"
                f"<i>Будьте внимательны при движении в этом направлении!</i>"
            )
            try:
                await bot.send_message(
                    chat_id=target_uid,
                    text=broadcast_msg,
                    parse_mode="HTML"
                )
                notified_count += 1
            except Exception:
                pass

    return notified_count


@router.message(ReportEventFSM.waiting_for_description, F.text)
async def process_event_description(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database
) -> None:
    """Принимает текстовое описание и завершает создание события."""
    data = await state.get_data()
    description = message.text.strip()
    await state.clear()

    notified = await finalize_event_creation(
        bot=bot,
        db=db,
        user_id=message.from_user.id,
        state_data=data,
        description=description
    )

    is_admin = message.from_user.id in config.admin_ids
    await message.answer(
        f"✅ <b>Спасибо за бдительность!</b>\n\n"
        f"Событие успешно нанесено на Народную карту.\n"
        f"Оповещено водителей поблизости: <b>{notified}</b>.",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(is_admin=is_admin)
    )


@router.callback_query(ReportEventFSM.waiting_for_description, F.data == "event_skip_desc")
async def process_skip_description(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database
) -> None:
    """Завершает создание события без подробного описания."""
    data = await state.get_data()
    await state.clear()

    notified = await finalize_event_creation(
        bot=bot,
        db=db,
        user_id=callback.from_user.id,
        state_data=data,
        description=""
    )

    is_admin = callback.from_user.id in config.admin_ids
    await callback.answer()
    await callback.message.answer(
        f"✅ <b>Событие успешно зарегистрировано!</b>\n\n"
        f"Оповещено водителей поблизости: <b>{notified}</b>.",
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(is_admin=is_admin)
    )

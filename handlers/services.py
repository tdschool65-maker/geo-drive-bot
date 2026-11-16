from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import Database
from keyboards import get_help_services_kb, get_location_request_kb
from utils import haversine_distance, format_distance

router = Router(name="services_router")


class NearbyHelpFSM(StatesGroup):
    waiting_for_location = State()


@router.message(F.text == "🚨 Помощь рядом")
async def cmd_nearby_help(message: Message, db: Database, state: FSMContext) -> None:
    """
    Точка входа в раздел «Помощь рядом».
    Проверяет наличие сохраненных координат водителя.
    Если координат нет — запрашивает их.
    """
    user_id = message.from_user.id
    user_loc = await db.get_user_location(user_id)

    if not user_loc or user_loc["latitude"] is None:
        await state.set_state(NearbyHelpFSM.waiting_for_location)
        await message.answer(
            "📍 Для поиска ближайшего шиномонтажа или эвакуатора боту необходимо знать ваше местоположение.\n\n"
            "Пожалуйста, нажмите кнопку ниже, чтобы отправить геопозицию:",
            reply_markup=get_location_request_kb()
        )
        return

    await message.answer(
        "🛠 <b>Служба экстренной помощи на дороге</b>\n\n"
        "Выберите, какая услуга вам необходима:",
        parse_mode="HTML",
        reply_markup=get_help_services_kb()
    )


@router.message(NearbyHelpFSM.waiting_for_location, F.location)
async def process_help_location(message: Message, state: FSMContext, db: Database) -> None:
    """Принимает локацию, сохраняет ее в БД и предлагает выбрать тип помощи."""
    loc = message.location
    await db.upsert_user_location(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_live=bool(loc.live_period)
    )
    await state.clear()

    await message.answer(
        "✅ Координаты определены!\n\n"
        "Выберите, какую помощь требуется найти:",
        reply_markup=get_help_services_kb()
    )


@router.callback_query(F.data.startswith("help_service:"))
async def display_nearby_services(callback: CallbackQuery, db: Database) -> None:
    """
    Вычисляет расстояние до зарегистрированных сервисов по формуле Хаверсина,
    сортирует их по возрастанию расстояния и возвращает водителю топ ближайших точек.
    """
    service_type = callback.data.split(":")[1]
    user_id = callback.from_user.id

    user_loc = await db.get_user_location(user_id)
    if not user_loc or user_loc["latitude"] is None:
        await callback.answer("Сначала отправьте геопозицию!", show_alert=True)
        return

    user_lat = user_loc["latitude"]
    user_lon = user_loc["longitude"]

    # Запрашиваем сервисы из базы данных
    services = await db.get_all_services(
        service_type=None if service_type == "all" else service_type
    )

    if not services:
        await callback.answer()
        await callback.message.answer("К сожалению, в базе пока нет зарегистрированных сервисов.")
        return

    # Рассчитываем расстояние до каждого сервиса
    services_with_distance = []
    for s in services:
        dist = haversine_distance(user_lat, user_lon, s["latitude"], s["longitude"])
        services_with_distance.append((dist, s))

    # Сортируем: сначала самые близкие
    services_with_distance.sort(key=lambda item: item[0])

    # Берем топ-5 ближайших
    top_services = services_with_distance[:5]

    response_lines = ["🚨 <b>Ближайшие точки помощи:</b>\n"]
    for idx, (dist, s) in enumerate(top_services, start=1):
        type_icon = "🛞" if s["service_type"] == "tire_service" else "🚜"
        map_url = f"https://yandex.ru/maps/?pt={s['longitude']},{s['latitude']}&z=16&l=map"

        response_lines.append(
            f"<b>{idx}. {type_icon} {s['name']}</b>\n"
            f"📏 Расстояние: <b>~{format_distance(dist)}</b>\n"
            f"📍 Адрес: {s['address']}\n"
            f"📞 Телефон: <code>{s['phone']}</code>\n"
            f"🗺 <a href='{map_url}'>Показать на Яндекс.Картах</a>\n"
        )

    response_lines.append("<i>Для звонка нажмите на номер телефона или скопируйте его.</i>")

    await callback.answer()
    await callback.message.answer(
        "\n".join(response_lines),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

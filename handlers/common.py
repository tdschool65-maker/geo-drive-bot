from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from config import config
from keyboards import get_main_menu_kb

router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    Приветствует пользователя, регистрирует его и выводит главное меню авто-ассистента.
    """
    await state.clear()
    is_admin = message.from_user.id in config.admin_ids

    welcome_text = (
        f"👋 Здравствуйте, <b>{message.from_user.first_name}</b>!\n\n"
        "🚗 Я — ваш персональный <b>авто-ассистент («Все-в-одном»)</b>.\n\n"
        "<b>Мои основные возможности:</b>\n"
        "• 📡 <b>Live-локация:</b> предупреждаю о засадах ДПС, авариях и ремонтах за 500 метров в реальном времени.\n"
        "• ⚠️ <b>Народная карта:</b> сообщайте о дорожных событиях и предупреждайте водителей рядом.\n"
        "• 🚨 <b>Помощь рядом:</b> быстрый поиск ближайшего шиномонтажа или эвакуатора.\n"
        "• 📰 <b>Новости ГАИ:</b> сводки об ограничениях движения, рейдах и изменениях ПДД.\n"
        "• ⏰ <b>Напоминания:</b> контроль срока окончания ОСАГО, КАСКО и техосмотра.\n\n"
        "<i>Для начала работы выберите нужный пункт в меню ниже:</i>"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(is_admin=is_admin)
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help с описанием функционала бота."""
    help_text = (
        "📖 <b>Справочник по функциям авто-ассистента:</b>\n\n"
        "1. <b>Трансляция геопозиции (Live Location):</b>\n"
        "Нажмите скрепку 📎 ➔ «Геопозиция» ➔ «Транслировать мою геопозицию» (на 15 мин, 1 час или 8 часов). "
        "Бот будет отслеживать ваше движение и заранее предупредит о препятствиях впереди (до 500 м).\n\n"
        "2. <b>Народная карта:</b>\n"
        "Заметили экипаж ДПС, яму или аварию? Нажмите «⚠️ Сообщить о событии», выберите тип и отправьте точку.\n\n"
        "3. <b>Помощь рядом:</b>\n"
        "Пробили колесо или заглохли? Бот мгновенно найдет ближайший сервис с прямым номером телефона.\n\n"
        "4. <b>Напоминания:</b>\n"
        "Внесите дату окончания полиса ОСАГО или ТО — бот заранее напомнит о необходимости продления."
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text == "ℹ️ Как включить Live-локацию")
async def info_live_location(message: Message) -> None:
    """Инструкция для пользователя по включению непрерывной Live-локации."""
    instruction = (
        "📡 <b>Как включить непрерывную трансляцию геопозиции (Live Location):</b>\n\n"
        "1. В поле ввода сообщения нажмите на значок <b>скрепки 📎</b> (или ➕ на iPhone).\n"
        "2. Выберите пункт <b>«Геопозиция» (Location)</b>.\n"
        "3. Выберите <b>«Транслировать мою геопозицию...» (Share Live Location)</b>.\n"
        "4. Укажите желаемое время (например, <i>на 1 час</i> или <i>на 8 часов</i> в дорогу).\n\n"
        "💡 <i>Пока вы едете, Telegram автоматически передает боту обновления координат, "
        "а бот предупредит вас звуковым уведомлением при приближении к камерам, ДПС или авариям за 500 метров!</i>"
    )
    await message.answer(instruction, parse_mode="HTML")


@router.message(F.text == "❌ Отмена")
@router.callback_query(F.data == "cancel_action")
async def cancel_handler(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Универсальный сброс состояния FSM при нажатии кнопки 'Отмена'."""
    await state.clear()
    is_admin = event.from_user.id in config.admin_ids

    if isinstance(event, CallbackQuery):
        await event.answer("Действие отменено.")
        await event.message.answer(
            "Операция отменена. Вы вернулись в главное меню.",
            reply_markup=get_main_menu_kb(is_admin=is_admin)
        )
    else:
        await event.answer(
            "Операция отменена. Вы вернулись в главное меню.",
            reply_markup=get_main_menu_kb(is_admin=is_admin)
        )

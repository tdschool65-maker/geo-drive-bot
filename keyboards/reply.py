from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Главное меню бота с основными функциями авто-ассистента.
    """
    keyboard = [
        [
            KeyboardButton(text="📍 Отправить геопозицию", request_location=True),
            KeyboardButton(text="ℹ️ Как включить Live-локацию")
        ],
        [
            KeyboardButton(text="⚠️ Сообщить о событии"),
            KeyboardButton(text="🚨 Помощь рядом")
        ],
        [
            KeyboardButton(text="📰 Новости ГАИ"),
            KeyboardButton(text="⏰ Напоминания (ОСАГО/ТО)")
        ]
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админ-панель")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню..."
    )


def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены текущего действия."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_location_request_kb() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой запроса геолокации и отменой."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить текущую геопозицию", request_location=True)],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any


def get_event_categories_kb() -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура выбора типа дорожного события для Народной карты.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="💥 ДТП / Авария", callback_data="event_cat:accident"),
            InlineKeyboardButton(text="🚧 Ремонт дороги", callback_data="event_cat:road_work"),
        ],
        [
            InlineKeyboardButton(text="👮 Экипаж ДПС", callback_data="event_cat:police"),
            InlineKeyboardButton(text="❄️ Гололед / Опасность", callback_data="event_cat:ice_danger"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_skip_or_cancel_kb() -> InlineKeyboardMarkup:
    """Клавиатура с возможностью пропустить ввод описания или отменить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить описание", callback_data="event_skip_desc")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
        ]
    )


def get_help_services_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора типа экстренной помощи рядом (шиномонтаж или эвакуатор).
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🛞 Ближайший шиномонтаж", callback_data="help_service:tire_service"),
        ],
        [
            InlineKeyboardButton(text="🚜 Вызов эвакуатора", callback_data="help_service:tow_truck"),
        ],
        [
            InlineKeyboardButton(text="🔍 Показать все сервисы рядом", callback_data="help_service:all"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_reminders_menu_kb() -> InlineKeyboardMarkup:
    """
    Меню управления напоминаниями автовладельца.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="➕ Добавить напоминание", callback_data="rem_action:add"),
        ],
        [
            InlineKeyboardButton(text="📋 Список моих напоминаний", callback_data="rem_action:list"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_reminder_types_kb() -> InlineKeyboardMarkup:
    """
    Выбор типа напоминания (ОСАГО, ТО, Замена масла).
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📄 Страховка ОСАГО / КАСКО", callback_data="rem_type:osago"),
        ],
        [
            InlineKeyboardButton(text="🔧 Техосмотр (ТО)", callback_data="rem_type:to"),
        ],
        [
            InlineKeyboardButton(text="🛢 Замена масла и фильтров", callback_data="rem_type:oil"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_delete_reminder_kb(reminder_id: int) -> InlineKeyboardMarkup:
    """Кнопка удаления конкретного напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить это напоминание", callback_data=f"rem_del:{reminder_id}")]
        ]
    )


def get_admin_menu_kb() -> InlineKeyboardMarkup:
    """
    Панель управления администратора.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📢 Добавить новость/сводку ГАИ", callback_data="admin:add_news"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика активности", callback_data="admin:stats"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

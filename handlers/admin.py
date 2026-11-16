from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import aiosqlite

from config import config
from database import Database
from keyboards import get_admin_menu_kb, get_main_menu_kb, get_cancel_kb

router = Router(name="admin_router")


class AdminAddNewsFSM(StatesGroup):
    """FSM добавления новости администратором."""
    waiting_for_title = State()
    waiting_for_content = State()
    confirm_broadcast = State()


def is_admin_filter(user_id: int) -> bool:
    """Проверка прав администратора по ID."""
    return user_id in config.admin_ids


@router.message(Command("admin"))
@router.message(F.text == "⚙️ Админ-панель")
async def cmd_admin_panel(message: Message) -> None:
    """Точка входа в панель администратора."""
    if not is_admin_filter(message.from_user.id):
        await message.answer("⛔ У вас нет прав доступа к панели администратора.")
        return

    await message.answer(
        "⚙️ <b>Панель управления администратора</b>\n\n"
        "Здесь вы можете опубликовать сводку ГАИ или просмотреть статистику сервиса:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_kb()
    )


@router.callback_query(F.data == "admin:stats")
async def show_bot_stats(callback: CallbackQuery, db: Database) -> None:
    """Отображает сводную статистику по базе данных бота."""
    if not is_admin_filter(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Подсчет пользователей
        c = await conn.execute("SELECT COUNT(*) as cnt FROM users")
        total_users = (await c.fetchone())["cnt"]

        # Пользователи с активной локацией
        c = await conn.execute("SELECT COUNT(*) as cnt FROM users WHERE latitude IS NOT NULL")
        located_users = (await c.fetchone())["cnt"]

        # Активные дорожные события
        c = await conn.execute("SELECT COUNT(*) as cnt FROM road_events WHERE is_active = 1")
        active_events = (await c.fetchone())["cnt"]

        # Напоминания
        c = await conn.execute("SELECT COUNT(*) as cnt FROM reminders")
        total_reminders = (await c.fetchone())["cnt"]

        # Количество опубликованных новостей
        c = await conn.execute("SELECT COUNT(*) as cnt FROM news")
        total_news = (await c.fetchone())["cnt"]

    stats_text = (
        "📊 <b>Статистика системы:</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📍 Пользователей с геолокацией: <b>{located_users}</b>\n"
        f"⚠️ Активных дорожных событий: <b>{active_events}</b>\n"
        f"⏰ Запланированных напоминаний: <b>{total_reminders}</b>\n"
        f"📰 Опубликовано новостей: <b>{total_news}</b>\n"
    )

    await callback.answer()
    await callback.message.answer(stats_text, parse_mode="HTML")


@router.message(Command("add_news"))
@router.callback_query(F.data == "admin:add_news")
async def start_add_news(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Инициализация создания новой публикации/сводки ГАИ."""
    user_id = event.from_user.id
    if not is_admin_filter(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer("Доступ запрещен", show_alert=True)
        else:
            await event.answer("⛔ Доступ запрещен.")
        return

    await state.set_state(AdminAddNewsFSM.waiting_for_title)

    prompt = (
        "📢 <b>Публикация новости ГАИ / Сводки</b>\n\n"
        "Шаг 1 из 2: Введите <b>заголовок новости</b>\n"
        "<i>Например: Рейд «Пешеходный переход» с 20 по 25 ноября</i>"
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(prompt, parse_mode="HTML", reply_markup=get_cancel_kb())
    else:
        await event.answer(prompt, parse_mode="HTML", reply_markup=get_cancel_kb())


@router.message(AdminAddNewsFSM.waiting_for_title, F.text)
async def process_news_title(message: Message, state: FSMContext) -> None:
    """Сохраняет заголовок новости и запрашивает текст сообщения."""
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AdminAddNewsFSM.waiting_for_content)

    await message.answer(
        f"Заголовок: <b>{title}</b>\n\n"
        "Шаг 2 из 2: Теперь введите <b>полный текст новости</b> или сводки:",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )


@router.message(AdminAddNewsFSM.waiting_for_content, F.text)
async def process_news_content(message: Message, state: FSMContext) -> None:
    """Принимает текст новости и предлагает выбрать: разослать всем или только сохранить в ленту."""
    content = message.text.strip()
    await state.update_data(content=content)
    await state.set_state(AdminAddNewsFSM.confirm_broadcast)

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 Сохранить и РАЗОСЛАТЬ ВСЕМ", callback_data="news_pub:broadcast"),
            ],
            [
                InlineKeyboardButton(text="💾 Только сохранить в ленту", callback_data="news_pub:feed_only"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ]
        ]
    )

    data = await state.get_data()
    preview = (
        "🔎 <b>Предпросмотр публикации:</b>\n\n"
        f"📢 <b>{data['title']}</b>\n\n"
        f"{content}\n\n"
        "<i>Выберите способ публикации:</i>"
    )

    await message.answer(preview, parse_mode="HTML", reply_markup=confirm_kb)


@router.callback_query(AdminAddNewsFSM.confirm_broadcast, F.data.startswith("news_pub:"))
async def finalize_news_publication(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database
) -> None:
    """Сохраняет новость в базу и при необходимости осуществляет рассылку."""
    action = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    title = data["title"]
    content = data["content"]

    # Сохраняем в БД
    await db.add_news(
        author_id=callback.from_user.id,
        title=title,
        content=content
    )

    broadcast_count = 0
    if action == "broadcast":
        users = await db.get_all_active_users_with_location()
        # Также можно взять всех уникальных пользователей из таблицы users
        broadcast_text = (
            f"📢 <b>ЭКСТРЕННАЯ СВОДКА ГАИ / НОВОСТИ</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"{content}"
        )
        for u in users:
            try:
                await bot.send_message(
                    chat_id=u["user_id"],
                    text=broadcast_text,
                    parse_mode="HTML"
                )
                broadcast_count += 1
            except Exception:
                pass

    await callback.answer()
    result_text = "✅ <b>Новость успешно опубликована в ленте!</b>"
    if action == "broadcast":
        result_text += f"\n📢 Доставлено пользователям: <b>{broadcast_count}</b>"

    await callback.message.answer(
        result_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_kb(is_admin=True)
    )

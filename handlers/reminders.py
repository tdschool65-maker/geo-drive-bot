from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import Database
from keyboards import (
    get_reminders_menu_kb,
    get_reminder_types_kb,
    get_delete_reminder_kb,
    get_skip_or_cancel_kb,
)

router = Router(name="reminders_router")


class AddReminderFSM(StatesGroup):
    """Машина состояний добавления нового напоминания для автомобиля."""
    choosing_type = State()
    waiting_for_date = State()
    waiting_for_note = State()


REMINDER_TYPE_NAMES = {
    "osago": "📄 Страховка ОСАГО / КАСКО",
    "to": "🔧 Техосмотр (ТО)",
    "oil": "🛢 Замена масла / ТО"
}


@router.message(F.text == "⏰ Напоминания (ОСАГО/ТО)")
async def menu_reminders(message: Message, state: FSMContext) -> None:
    """Точка входа в раздел напоминаний автовладельца."""
    await state.clear()
    await message.answer(
        "⏰ <b>Авто-напоминания (ОСАГО, ТО, Расходники)</b>\n\n"
        "Бот заблаговременно (за 7 дней и в день срока) пришлет вам push-уведомление, "
        "чтобы вы не забыли оформить страховку или пройти техобслуживание.",
        parse_mode="HTML",
        reply_markup=get_reminders_menu_kb()
    )


@router.callback_query(F.data == "rem_action:list")
async def show_user_reminders(callback: CallbackQuery, db: Database) -> None:
    """Отображает список всех запланированных напоминаний пользователя."""
    user_id = callback.from_user.id
    reminders = await db.get_user_reminders(user_id)

    if not reminders:
        await callback.answer()
        await callback.message.answer(
            "📋 У вас пока нет активных напоминаний.\n"
            "Нажмите <b>«➕ Добавить напоминание»</b>, чтобы внести полис или дату ТО.",
            parse_mode="HTML",
            reply_markup=get_reminders_menu_kb()
        )
        return

    await callback.answer()
    today = date.today()

    for r in reminders:
        r_type = REMINDER_TYPE_NAMES.get(r["reminder_type"], r["reminder_type"])
        exp_date_obj = datetime.strptime(r["expire_date"], "%Y-%m-%d").date()
        days_left = (exp_date_obj - today).days

        if days_left > 0:
            status = f"⏳ Осталось дней: <b>{days_left}</b>"
        elif days_left == 0:
            status = "🚨 <b>Срок истекает сегодня!</b>"
        else:
            status = f"❌ <b>Просрочено на {-days_left} дн.</b>"

        formatted_date = exp_date_obj.strftime("%d.%m.%Y")
        note_str = f"\n📝 Заметка: <i>{r['note']}</i>" if r["note"] else ""

        text = (
            f"📌 <b>{r_type}</b>\n"
            f"📅 Дата окончания: <b>{formatted_date}</b>\n"
            f"{status}{note_str}"
        )

        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_delete_reminder_kb(r["id"])
        )


@router.callback_query(F.data.startswith("rem_del:"))
async def delete_reminder_handler(callback: CallbackQuery, db: Database) -> None:
    """Удаляет выбранное напоминание из базы данных."""
    reminder_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    success = await db.delete_reminder(reminder_id, user_id)
    await callback.answer("Напоминание удалено!" if success else "Ошибка удаления")

    if success:
        try:
            await callback.message.delete()
        except Exception:
            pass


@router.callback_query(F.data == "rem_action:add")
async def start_add_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает FSM создания нового напоминания и предлагает выбрать тип."""
    await state.set_state(AddReminderFSM.choosing_type)
    await callback.answer()
    await callback.message.answer(
        "Выберите тип документа или события:",
        reply_markup=get_reminder_types_kb()
    )


@router.callback_query(AddReminderFSM.choosing_type, F.data.startswith("rem_type:"))
async def process_reminder_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет выбранный тип и запрашивает дату окончания срока."""
    rem_type = callback.data.split(":")[1]
    await state.update_data(reminder_type=rem_type)
    await state.set_state(AddReminderFSM.waiting_for_date)

    type_name = REMINDER_TYPE_NAMES.get(rem_type, rem_type)
    await callback.answer()
    await callback.message.answer(
        f"Выбрано: <b>{type_name}</b>.\n\n"
        "📅 Введите дату окончания срока в формате <b>ДД.ММ.ГГГГ</b>\n"
        "<i>Например: 15.05.2027</i>",
        parse_mode="HTML"
    )


@router.message(AddReminderFSM.waiting_for_date, F.text)
async def process_reminder_date(message: Message, state: FSMContext) -> None:
    """Парсит и валидирует дату, введенную пользователем."""
    raw_date = message.text.strip()
    try:
        parsed_date = datetime.strptime(raw_date, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат даты! Пожалуйста, укажите дату строго в формате <b>ДД.ММ.ГГГГ</b>\n"
            "Пример: <code>20.12.2026</code>",
            parse_mode="HTML"
        )
        return

    # Сохраняем в формате базы данных YYYY-MM-DD
    await state.update_data(expire_date=parsed_date.isoformat())
    await state.set_state(AddReminderFSM.waiting_for_note)

    await message.answer(
        "✍️ Введите краткий комментарий (например: <i>«Страховая РЕСО, полис XXX 123456»</i>) "
        "или нажмите <b>«Пропустить описание»</b>:",
        parse_mode="HTML",
        reply_markup=get_skip_or_cancel_kb()
    )


@router.message(AddReminderFSM.waiting_for_note, F.text)
async def process_reminder_note(message: Message, state: FSMContext, db: Database) -> None:
    """Завершает добавление напоминания с пользовательским примечанием."""
    note = message.text.strip()
    data = await state.get_data()
    await state.clear()

    await db.add_reminder(
        user_id=message.from_user.id,
        reminder_type=data["reminder_type"],
        expire_date=data["expire_date"],
        note=note
    )

    date_formatted = datetime.strptime(data["expire_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    await message.answer(
        f"✅ <b>Напоминание успешно создано!</b>\n\n"
        f"📌 Тип: {REMINDER_TYPE_NAMES.get(data['reminder_type'])}\n"
        f"📅 Срок: <b>{date_formatted}</b>\n"
        f"📝 Примечание: {note}\n\n"
        "Мы заранее оповестим вас о приближении этой даты!",
        parse_mode="HTML"
    )


@router.callback_query(AddReminderFSM.waiting_for_note, F.data == "event_skip_desc")
async def process_reminder_skip_note(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Завершает добавление напоминания без примечания."""
    data = await state.get_data()
    await state.clear()

    await db.add_reminder(
        user_id=callback.from_user.id,
        reminder_type=data["reminder_type"],
        expire_date=data["expire_date"],
        note=""
    )

    date_formatted = datetime.strptime(data["expire_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    await callback.answer()
    await callback.message.answer(
        f"✅ <b>Напоминание успешно создано!</b>\n\n"
        f"📌 Тип: {REMINDER_TYPE_NAMES.get(data['reminder_type'])}\n"
        f"📅 Срок: <b>{date_formatted}</b>\n\n"
        "Мы заранее оповестим вас о приближении этой даты!",
        parse_mode="HTML"
    )

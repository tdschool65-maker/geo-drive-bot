from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime

from config import config
from database import Database

router = Router(name="news_router")


@router.message(F.text == "📰 Новости ГАИ")
async def show_traffic_news(message: Message, db: Database) -> None:
    """
    Отображает список последних важных новостей и оперативных сводок
    (рейды, перекрытия движения, изменения в штрафах и ПДД).
    """
    recent_news = await db.get_recent_news(limit=5)

    if not recent_news:
        await message.answer(
            "📰 <b>Сводки и новости ГАИ</b>\n\n"
            "На данный момент свежих предупреждений и сводок не опубликовано.\n"
            "Следите за обновлениями!",
            parse_mode="HTML"
        )
        return

    text_parts = ["📰 <b>Оперативные сводки и новости автоинспекции:</b>\n"]
    for item in recent_news:
        # Форматируем дату публикации
        try:
            dt = datetime.fromisoformat(item["created_at"])
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            date_str = item["created_at"]

        text_parts.append(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>{item['title']}</b>\n"
            f"🕒 <i>{date_str}</i>\n\n"
            f"{item['content']}\n"
        )

    is_admin = message.from_user.id in config.admin_ids
    if is_admin:
        text_parts.append("━━━━━━━━━━━━━━━━━━━━\n💡 <i>Вы администратор. Для добавления новости используйте команду /add_news или панель управления.</i>")

    await message.answer("\n".join(text_parts), parse_mode="HTML")

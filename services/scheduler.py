import asyncio
from datetime import date, timedelta, datetime
from aiogram import Bot

from database import Database

REMINDER_TITLES = {
    "osago": "📄 Страховой полис ОСАГО / КАСКО",
    "to": "🔧 Диагностическая карта / Техосмотр (ТО)",
    "oil": "🛢 Замена моторного масла и расходников"
}


async def reminder_scheduler_task(bot: Bot, db: Database, interval_seconds: int = 3600) -> None:
    """
    Фоновая асинхронная корутина, периодически проверяющая наступление сроков
    действия документов (ОСАГО, ТО) и отправляющая push-уведомления водителям:
    1. За 7 дней до истечения срока (статус notified = 1).
    2. В день истечения срока (статус notified = 2).
    """
    print("[SCHEDULER] Служба проверки напоминаний запущена.")

    while True:
        try:
            today = date.today()
            today_str = today.isoformat()
            warning_date_str = (today + timedelta(days=7)).isoformat()

            due_reminders = await db.get_due_reminders(
                today_str=today_str,
                warning_date_str=warning_date_str
            )

            for rem in due_reminders:
                rem_id = rem["id"]
                user_id = rem["user_id"]
                rem_type = rem["reminder_type"]
                type_title = REMINDER_TITLES.get(rem_type, rem_type)
                exp_date = datetime.strptime(rem["expire_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
                note_text = f"\n📝 Примечание: <i>{rem['note']}</i>" if rem["note"] else ""

                if rem["notified"] == 0:
                    # Уведомление за 7 дней
                    text = (
                        f"🔔 <b>ВНИМАНИЕ! Скоро истекает срок документа!</b>\n\n"
                        f"📌 <b>{type_title}</b>\n"
                        f"📅 Дата окончания: <b>{exp_date}</b> (осталось 7 дней или меньше)\n"
                        f"{note_text}\n\n"
                        f"<i>Рекомендуем заблаговременно оформить продление полиса или записаться на ТО.</i>"
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
                        await db.update_reminder_status(rem_id, 1)
                    except Exception as e:
                        print(f"[SCHEDULER] Ошибка отправки 7-дневного напоминания {user_id}: {e}")

                elif rem["notified"] == 1 and rem["expire_date"] <= today_str:
                    # Уведомление в день истечения
                    text = (
                        f"🚨 <b>СРОЧНОЕ НАПОМИНАНИЕ: Срок истекает СЕГОДНЯ!</b>\n\n"
                        f"📌 <b>{type_title}</b>\n"
                        f"📅 Дата окончания: <b>{exp_date}</b>\n"
                        f"{note_text}\n\n"
                        f"<i>Внимание: управление ТС без действующего полиса ОСАГО или ТО влечет штраф или запрет эксплуатации!</i>"
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
                        await db.update_reminder_status(rem_id, 2)
                    except Exception as e:
                        print(f"[SCHEDULER] Ошибка отправки финального напоминания {user_id}: {e}")

        except asyncio.CancelledError:
            print("[SCHEDULER] Служба напоминаний остановлена.")
            break
        except Exception as e:
            print(f"[SCHEDULER] Непредвиденная ошибка в цикле планировщика: {e}")

        # Пауза перед следующей проверкой (по умолчанию 1 час)
        await asyncio.sleep(interval_seconds)

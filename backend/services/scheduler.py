import asyncio
import os
from datetime import datetime, timedelta
from sqlalchemy import select
from database import async_session
from models.reminder import Reminder
from player import player
from services.tts import generate_audio_sync
import logging

logger = logging.getLogger(__name__)

async def check_and_play_reminders():
    """Check for due reminders and play them."""
    due_list = []
    try:
        async with async_session() as session:
            now = datetime.now()
            result = await session.execute(
                select(Reminder).where(
                    Reminder.status == "pending",
                    Reminder.reminder_time <= now
                ).order_by(Reminder.reminder_time)
            )
            for r in result.scalars().all():
                due_list.append({
                    "id": r.id, "title": r.title,
                    "description": r.description or "",
                    "audio_file": r.audio_file or "",
                    "is_repeating": r.is_repeating,
                    "repeat_type": r.repeat_type or "",
                    "reminder_time": r.reminder_time,
                })
    except Exception as e:
        logger.error(f"Scheduler query error: {e}")
        return

    loop = asyncio.get_event_loop()

    for item in due_list:
        try:
            logger.info(f"Playing reminder: {item['title']}")
            print(f"[Scheduler] Playing: {item['title']} at {item['reminder_time']}")

            # Re-query from DB to get the LATEST title (avoid stale data)
            audio_file = item["audio_file"]
            if not audio_file or not os.path.exists(audio_file):
                async with async_session() as session:
                    result = await session.execute(
                        select(Reminder).where(Reminder.id == item["id"])
                    )
                    r = result.scalar_one_or_none()
                    if r:
                        item["title"] = r.title
                        item["description"] = r.description or ""

                audio_file = await loop.run_in_executor(
                    None, generate_audio_sync,
                    item["id"], item["title"], item["description"]
                )

            if audio_file and os.path.exists(audio_file):
                await loop.run_in_executor(None, player.play, audio_file, True)

            # Update DB with new session
            async with async_session() as session:
                result = await session.execute(
                    select(Reminder).where(Reminder.id == item["id"])
                )
                r = result.scalar_one_or_none()
                if not r:
                    continue
                if audio_file:
                    r.audio_file = audio_file
                if r.is_repeating and r.repeat_type:
                    r.reminder_time = _calc_next(r.reminder_time, r.repeat_type)
                    r.status = "pending"
                else:
                    r.status = "played"
                await session.commit()
                print(f"[Scheduler] Updated reminder {item['id']} -> {r.status}")

        except Exception as e:
            logger.error(f"Scheduler process error for reminder {item['id']}: {e}")

def _calc_next(current_time, repeat_type):
    days_map = {"daily": 1, "weekly": 7, "monthly": 30}
    return current_time + timedelta(days=days_map.get(repeat_type, 1))

_scheduler_task = None

async def start_scheduler():
    global _scheduler_task
    async def loop():
        while True:
            await check_and_play_reminders()
            await asyncio.sleep(5)
    _scheduler_task = asyncio.create_task(loop())
    logger.info("Scheduler started")
    print("[Scheduler] Started - checking every 5 seconds")

async def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Scheduler stopped")
        print("[Scheduler] Stopped")

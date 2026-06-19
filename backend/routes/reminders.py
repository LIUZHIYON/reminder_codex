from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os
import asyncio
from database import get_session, async_session
from models.reminder import Reminder
from services.tts import generate_audio_sync
from player import player

router = APIRouter(prefix="/api/reminders", tags=["reminders"])

class ReminderCreate(BaseModel):
    title: str
    description: str = ""
    reminder_time: str
    is_repeating: bool = False
    repeat_type: str = ""

class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reminder_time: Optional[str] = None
    is_repeating: Optional[bool] = None
    repeat_type: Optional[str] = None

def reminder_to_dict(r):
    return {
        "id": r.id,
        "title": r.title,
        "description": r.description or "",
        "reminder_time": r.reminder_time.isoformat(),
        "is_repeating": r.is_repeating,
        "repeat_type": r.repeat_type or "",
        "audio_file": r.audio_file or "",
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }

async def _gen_audio_and_update(reminder_id, title, description):
    """Generate audio and update DB in a separate session."""
    loop = asyncio.get_event_loop()
    audio_path = await loop.run_in_executor(
        None, generate_audio_sync, reminder_id, title, description
    )
    if not audio_path:
        return
    try:
        async with async_session() as session:
            result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
            r = result.scalar_one_or_none()
            if r:
                r.audio_file = audio_path
                await session.commit()
                print(f"[API] Audio saved for reminder {reminder_id}")
    except Exception as e:
        print(f"[API] Audio update error: {e}")

@router.get("")
async def list_reminders(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Reminder).order_by(Reminder.reminder_time))
    return [reminder_to_dict(r) for r in result.scalars().all()]

@router.post("")
async def create_reminder(data: ReminderCreate, session: AsyncSession = Depends(get_session)):
    reminder = Reminder(
        title=data.title, description=data.description,
        reminder_time=datetime.fromisoformat(data.reminder_time),
        is_repeating=data.is_repeating, repeat_type=data.repeat_type,
        status="pending"
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)

    # Generate audio synchronously (not background) to avoid race conditions
    rid = reminder.id
    title = reminder.title
    desc = reminder.description
    await _gen_audio_and_update(rid, title, desc)

    # Refresh to get audio_file from DB
    await session.refresh(reminder)
    return reminder_to_dict(reminder)

@router.put("/{reminder_id}")
async def update_reminder(reminder_id: int, data: ReminderUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if data.title is not None: reminder.title = data.title
    if data.description is not None: reminder.description = data.description
    if data.reminder_time is not None: reminder.reminder_time = datetime.fromisoformat(data.reminder_time)
    if data.is_repeating is not None: reminder.is_repeating = data.is_repeating
    if data.repeat_type is not None: reminder.repeat_type = data.repeat_type
    reminder.status = "pending"
    await session.commit()

    rid = reminder.id
    await _gen_audio_and_update(rid, reminder.title, reminder.description)
    await session.refresh(reminder)
    return reminder_to_dict(reminder)

@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await session.delete(reminder)
    await session.commit()
    if reminder.audio_file and os.path.exists(reminder.audio_file):
        try: os.remove(reminder.audio_file)
        except: pass
    return {"message": "Reminder deleted"}

@router.post("/{reminder_id}/test-play")
async def test_play_reminder(reminder_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    audio_file = reminder.audio_file or ""
    if not audio_file or not os.path.exists(audio_file):
        loop = asyncio.get_event_loop()
        audio_file = await loop.run_in_executor(
            None, generate_audio_sync, reminder_id, reminder.title, reminder.description
        )
        if not audio_file:
            raise HTTPException(status_code=500, detail="TTS generation failed")
        await _gen_audio_and_update(reminder_id, reminder.title, reminder.description)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, player.play, audio_file, False)
    return {"message": "Playing reminder audio"}

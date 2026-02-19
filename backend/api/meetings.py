"""
Meeting management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
from pydantic import BaseModel

from backend.database import get_db
from backend.models.meeting import Meeting, MeetingType
from backend.models.user import User
from backend.api.auth import get_current_user
from backend.agents.meeting_prep.agent import MeetingPrepAgent
import json

router = APIRouter()


class MeetingCreate(BaseModel):
    title: str
    meeting_type: MeetingType
    scheduled_at: datetime
    duration_minutes: int = 60
    site_id: int | None = None


class MeetingResponse(BaseModel):
    id: int
    title: str
    meeting_type: MeetingType
    scheduled_at: datetime
    duration_minutes: int
    site_id: int | None
    ai_brief: dict | None
    ai_agenda: str | None

    class Config:
        from_attributes = True


@router.post("/", response_model=MeetingResponse)
async def create_meeting(
    meeting_data: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new meeting"""
    meeting = Meeting(**meeting_data.model_dump())
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    return await format_meeting_response(meeting)


@router.get("/", response_model=List[MeetingResponse])
async def list_meetings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    upcoming_only: bool = True
):
    """List all meetings"""
    query = select(Meeting)
    if upcoming_only:
        query = query.where(Meeting.scheduled_at >= datetime.now())
    query = query.order_by(Meeting.scheduled_at)

    result = await db.execute(query)
    meetings = result.scalars().all()

    return [await format_meeting_response(m) for m in meetings]


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific meeting"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return await format_meeting_response(meeting)


@router.post("/{meeting_id}/prepare", response_model=MeetingResponse)
async def prepare_meeting_brief(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI-powered meeting brief"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Generate brief using AI agent
    agent = MeetingPrepAgent()
    brief = await agent.prepare_meeting_brief(db, meeting)

    await db.commit()
    await db.refresh(meeting)

    return await format_meeting_response(meeting)


async def format_meeting_response(meeting: Meeting) -> MeetingResponse:
    """Format meeting for response"""
    ai_brief = None
    if meeting.ai_brief:
        try:
            ai_brief = json.loads(meeting.ai_brief)
        except json.JSONDecodeError:
            pass

    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        meeting_type=meeting.meeting_type,
        scheduled_at=meeting.scheduled_at,
        duration_minutes=meeting.duration_minutes,
        site_id=meeting.site_id,
        ai_brief=ai_brief,
        ai_agenda=meeting.ai_agenda
    )

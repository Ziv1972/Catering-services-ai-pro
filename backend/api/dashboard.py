"""
Dashboard data endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from backend.database import get_db
from backend.models.meeting import Meeting
from backend.models.site import Site
from backend.models.user import User
from backend.api.auth import get_current_user
from pydantic import BaseModel

router = APIRouter()


class DashboardData(BaseModel):
    upcoming_meetings: int
    total_sites: int
    meetings_with_briefs: int
    meetings_without_briefs: int


@router.get("/", response_model=DashboardData)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard summary data"""
    # Upcoming meetings count
    upcoming_result = await db.execute(
        select(func.count(Meeting.id)).where(
            Meeting.scheduled_at >= datetime.now()
        )
    )
    upcoming_meetings = upcoming_result.scalar() or 0

    # Total sites
    sites_result = await db.execute(
        select(func.count(Site.id)).where(Site.is_active == True)
    )
    total_sites = sites_result.scalar() or 0

    # Meetings with briefs
    briefs_result = await db.execute(
        select(func.count(Meeting.id)).where(
            Meeting.ai_brief.isnot(None),
            Meeting.scheduled_at >= datetime.now()
        )
    )
    meetings_with_briefs = briefs_result.scalar() or 0

    return DashboardData(
        upcoming_meetings=upcoming_meetings,
        total_sites=total_sites,
        meetings_with_briefs=meetings_with_briefs,
        meetings_without_briefs=upcoming_meetings - meetings_with_briefs,
    )

"""
Data gathering for meeting prep
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from backend.models.meeting import Meeting
from typing import Dict, Any, Optional


class MeetingDataGatherer:
    """
    Gathers relevant context data for meeting preparation
    """

    async def gather_context(
        self,
        db: AsyncSession,
        meeting: Meeting
    ) -> Dict[str, Any]:
        """
        Gather all relevant context for a meeting
        """
        context = {
            "meeting_info": await self._get_meeting_info(meeting),
            "previous_meeting": await self._get_previous_meeting(db, meeting),
            "site_metrics": await self._get_site_metrics(db, meeting.site_id) if meeting.site_id else None,
            # TODO: Add more data sources as we build them
            # "recent_complaints": await self._get_recent_complaints(db, meeting.site_id),
            # "budget_status": await self._get_budget_status(db, meeting.site_id),
            # "equipment_status": await self._get_equipment_status(db, meeting.site_id),
        }

        return context

    async def _get_meeting_info(self, meeting: Meeting) -> Dict[str, Any]:
        """Basic meeting information"""
        return {
            "title": meeting.title,
            "type": meeting.meeting_type.value,
            "scheduled_at": meeting.scheduled_at.isoformat(),
            "duration_minutes": meeting.duration_minutes,
            "site": meeting.site.name if meeting.site else "All Sites"
        }

    async def _get_previous_meeting(
        self,
        db: AsyncSession,
        current_meeting: Meeting
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent previous meeting of the same type"""
        query = select(Meeting).where(
            and_(
                Meeting.meeting_type == current_meeting.meeting_type,
                Meeting.scheduled_at < current_meeting.scheduled_at,
                Meeting.site_id == current_meeting.site_id if current_meeting.site_id else True
            )
        ).order_by(Meeting.scheduled_at.desc()).limit(1)

        result = await db.execute(query)
        previous = result.scalar_one_or_none()

        if not previous:
            return None

        return {
            "date": previous.scheduled_at.isoformat(),
            "summary": previous.ai_summary,
            "action_items": [
                {
                    "item": note.note_text,
                    "completed": note.is_completed,
                    "assigned_to": note.assigned_to
                }
                for note in previous.notes if note.is_action_item
            ]
        }

    async def _get_site_metrics(
        self,
        db: AsyncSession,
        site_id: int
    ) -> Dict[str, Any]:
        """Get high-level metrics for a site"""
        # TODO: Implement once we have more data models
        return {
            "meal_counts": "Data coming soon",
            "budget_status": "Data coming soon",
            "service_quality": "Data coming soon"
        }

"""
Webhook endpoints for Power Automate integration
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import logging

from backend.database import get_db
from backend.models.complaint import Complaint, ComplaintSource, ComplaintStatus
from backend.models.meeting import Meeting, MeetingType
from backend.models.site import Site
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent

router = APIRouter()
logger = logging.getLogger(__name__)


class ComplaintWebhook(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    bodyPreview: Optional[str] = None
    received: Optional[str] = None
    receivedDateTime: Optional[str] = None
    message_id: Optional[str] = None
    # "from" can be a string or object
    from_address: Optional[str] = None


class MeetingWebhook(BaseModel):
    subject: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    location: Optional[str] = None
    event_id: Optional[str] = None


CATERING_KEYWORDS = [
    'catering', 'food', 'menu', 'dining', 'kitchen',
    'vendor', 'supplier', 'nes ziona', 'kiryat gat',
    'site manager', 'weekly sync', 'foodhouse', 'l.eshel'
]


async def _infer_site_id(text: str, db: AsyncSession) -> Optional[int]:
    """Infer site from text content"""
    text_lower = text.lower()

    if 'nes ziona' in text_lower or ' nz ' in text_lower or text_lower.startswith('nz '):
        result = await db.execute(select(Site).where(Site.code == 'NZ'))
        site = result.scalar_one_or_none()
        return site.id if site else None

    if 'kiryat gat' in text_lower or ' kg ' in text_lower or text_lower.startswith('kg '):
        result = await db.execute(select(Site).where(Site.code == 'KG'))
        site = result.scalar_one_or_none()
        return site.id if site else None

    return None


def _is_catering_meeting(title: str) -> bool:
    """Check if meeting is catering-related"""
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in CATERING_KEYWORDS)


def _infer_meeting_type(title: str) -> MeetingType:
    """Infer meeting type from title"""
    title_lower = title.lower()

    if 'site manager' in title_lower or 'weekly sync' in title_lower:
        return MeetingType.SITE_MANAGER
    elif 'technical' in title_lower or 'equipment' in title_lower:
        return MeetingType.TECHNICAL
    elif 'vendor' in title_lower or 'supplier' in title_lower:
        return MeetingType.VENDOR
    elif 'hp management' in title_lower or 'budget' in title_lower:
        return MeetingType.HP_MANAGEMENT
    else:
        return MeetingType.OTHER


def _parse_datetime(value: Optional[str]) -> datetime:
    """Parse ISO datetime string, handling Z suffix"""
    if not value:
        return datetime.utcnow()
    cleaned = value.replace('Z', '+00:00')
    return datetime.fromisoformat(cleaned)


@router.post("/complaints")
async def receive_complaint_from_email(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for Power Automate email trigger.
    Receives complaints from monitored emails.

    Expected JSON body from Power Automate:
    {
        "from": "employee@hp.com",
        "subject": "Food complaint",
        "body": "The food was cold today...",
        "received": "2026-02-20T14:30:00Z",
        "message_id": "outlook-message-id"
    }
    """
    try:
        logger.info(f"Received complaint webhook: {request.get('subject', 'No subject')}")

        # Extract body text (prefer plain text preview)
        body_text = request.get('bodyPreview') or request.get('body', '')

        # Parse sender email
        from_email = request.get('from', '')
        if isinstance(from_email, dict):
            from_email = from_email.get('emailAddress', {}).get('address', '')

        # Determine site from email content
        site_id = await _infer_site_id(body_text, db)

        # Parse received time
        received_str = request.get('receivedDateTime') or request.get('received')
        received_at = _parse_datetime(received_str)

        # Create complaint
        complaint = Complaint(
            complaint_text=body_text,
            employee_email=from_email if from_email else None,
            source=ComplaintSource.EMAIL,
            source_id=request.get('message_id'),
            received_at=received_at,
            status=ComplaintStatus.NEW,
            site_id=site_id,
        )

        db.add(complaint)
        await db.flush()

        # AI analysis
        try:
            agent = ComplaintIntelligenceAgent()
            await agent.analyze_complaint(db, complaint)
        except Exception as ai_err:
            logger.warning(f"AI analysis failed (complaint still saved): {ai_err}")

        logger.info(
            f"Complaint created: ID={complaint.id}, "
            f"Category={complaint.category}, Severity={complaint.severity}"
        )

        return {
            "status": "success",
            "complaint_id": complaint.id,
            "category": complaint.category.value if complaint.category else None,
            "severity": complaint.severity.value if complaint.severity else None,
            "ai_summary": complaint.ai_summary,
        }

    except Exception as e:
        logger.error(f"Error processing complaint webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meetings")
async def receive_meeting_from_calendar(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for Power Automate calendar trigger.
    Receives catering-related meetings.

    Expected JSON body from Power Automate:
    {
        "subject": "Weekly Sync - Nes Ziona",
        "start": "2026-02-24T10:00:00Z",
        "end": "2026-02-24T11:00:00Z",
        "location": "Nes Ziona",
        "event_id": "outlook-event-id"
    }
    """
    try:
        title = request.get('subject', 'Untitled Meeting')
        logger.info(f"Received meeting webhook: {title}")

        # Check if catering-related
        if not _is_catering_meeting(title):
            logger.info(f"Skipping non-catering meeting: {title}")
            return {
                "status": "skipped",
                "reason": "Not catering-related",
            }

        # Parse times
        start_time = _parse_datetime(request.get('start'))
        end_time = _parse_datetime(request.get('end'))
        duration_minutes = max(int((end_time - start_time).total_seconds() / 60), 15)

        # Infer meeting type and site
        meeting_type = _infer_meeting_type(title)
        location_text = request.get('location', '') or ''
        site_id = await _infer_site_id(f"{title} {location_text}", db)

        # Check if meeting already exists (by event_id)
        event_id = request.get('event_id')
        if event_id:
            result = await db.execute(
                select(Meeting).where(Meeting.outlook_event_id == event_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.title = title
                existing.scheduled_at = start_time
                existing.duration_minutes = duration_minutes
                existing.site_id = site_id

                logger.info(f"Updated existing meeting: ID={existing.id}")
                return {
                    "status": "updated",
                    "meeting_id": existing.id,
                }

        # Create new meeting
        meeting = Meeting(
            title=title,
            meeting_type=meeting_type,
            scheduled_at=start_time,
            duration_minutes=duration_minutes,
            site_id=site_id,
            outlook_event_id=event_id,
        )

        db.add(meeting)
        await db.flush()

        logger.info(f"Meeting created: ID={meeting.id}, Type={meeting.meeting_type}")

        return {
            "status": "created",
            "meeting_id": meeting.id,
            "type": meeting.meeting_type.value,
        }

    except Exception as e:
        logger.error(f"Error processing meeting webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_webhook():
    """Test endpoint to verify webhooks are working"""
    return {
        "status": "ok",
        "message": "Webhooks are operational",
        "endpoints": {
            "complaints": "POST /api/webhooks/complaints",
            "meetings": "POST /api/webhooks/meetings",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

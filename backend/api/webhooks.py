"""
Webhook endpoints for Power Automate integration
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, date
from pydantic import BaseModel
from typing import Optional, List
import logging
import re
import io
import csv

from backend.database import get_db
from backend.models.complaint import Complaint, ComplaintSource, ComplaintStatus
from backend.models.meeting import Meeting, MeetingType
from backend.models.site import Site
from backend.models.daily_meal_count import DailyMealCount
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent

router = APIRouter()
logger = logging.getLogger(__name__)


# ──── Meal type parsing helpers ────
MEAL_TYPE_MAP = {
    "בשרי": ("Meat", "בשרי"),
    "חלבי": ("Dairy", "חלבי"),
    "עיקרית בלבד": ("Main Only", "עיקרית בלבד"),
}

SITE_MAP = {
    "נס ציונה": "NZ",
    "קרית גת": "KG",
}


def _parse_restaurant_line(name: str) -> dict:
    """
    Parse a line like 'HP פוד האוס בשרי עיקרית בלבד - נס ציונה'
    Returns: { meal_type, meal_type_en, site_code, restaurant_name }
    """
    result = {"meal_type": "unknown", "meal_type_en": "Unknown", "site_code": None, "restaurant_name": name}

    # Extract site from "- <site>" suffix
    for heb_site, code in SITE_MAP.items():
        if heb_site in name:
            result["site_code"] = code
            break

    # Determine meal type (check longest matches first)
    if "עיקרית בלבד" in name:
        result["meal_type"] = "עיקרית בלבד"
        result["meal_type_en"] = "Main Only"
    elif "חלבי" in name:
        result["meal_type"] = "חלבי"
        result["meal_type_en"] = "Dairy"
    elif "בשרי" in name:
        result["meal_type"] = "בשרי"
        result["meal_type_en"] = "Meat"

    return result


async def _upsert_daily_meals(
    db: AsyncSession,
    meal_date: date,
    rows: list[dict],
    source: str = "csv_upload",
) -> dict:
    """Upsert daily meal counts from parsed rows."""
    created = 0
    updated = 0

    for row in rows:
        parsed = _parse_restaurant_line(row["name"])
        qty = row["quantity"]

        # Resolve site_id
        site_id = None
        if parsed["site_code"]:
            site_result = await db.execute(
                select(Site).where(Site.code == parsed["site_code"])
            )
            site = site_result.scalar_one_or_none()
            if site:
                site_id = site.id

        if not site_id:
            continue

        # Check for existing record (upsert)
        existing_result = await db.execute(
            select(DailyMealCount).where(
                and_(
                    DailyMealCount.date == meal_date,
                    DailyMealCount.site_id == site_id,
                    DailyMealCount.meal_type == parsed["meal_type"],
                )
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.quantity = qty
            existing.restaurant_name = row["name"]
            existing.source = source
            updated += 1
        else:
            record = DailyMealCount(
                date=meal_date,
                site_id=site_id,
                meal_type=parsed["meal_type"],
                meal_type_en=parsed["meal_type_en"],
                restaurant_name=row["name"],
                quantity=qty,
                source=source,
            )
            db.add(record)
            created += 1

    await db.commit()
    return {"created": created, "updated": updated}


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


@router.post("/daily-meals")
async def receive_daily_meals(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for Power Automate email trigger.
    Receives daily meal counts from the FoodHouse report email.

    Expected JSON body from Power Automate:
    {
        "date": "2026-02-27",
        "items": [
            { "name": "HP פוד האוס בשרי - נס ציונה", "quantity": 635 },
            { "name": "HP קופי האוס חלבי - קרית גת", "quantity": 14 }
        ]
    }

    Or raw CSV content:
    {
        "date": "2026-02-27",
        "csv_content": "שם מסעדה,מספר עסקאות\\nHP פוד האוס בשרי - נס ציונה,635.00\\n..."
    }
    """
    try:
        logger.info("Received daily-meals webhook")

        # Parse date
        date_str = request.get("date")
        meal_date = date.fromisoformat(date_str) if date_str else date.today()

        rows: list[dict] = []

        # Option 1: Pre-parsed items array
        if "items" in request:
            for item in request["items"]:
                rows.append({
                    "name": item.get("name", ""),
                    "quantity": float(item.get("quantity", 0)),
                })

        # Option 2: Raw CSV content from email body
        elif "csv_content" in request:
            csv_text = request["csv_content"]
            reader = csv.reader(io.StringIO(csv_text))
            header = next(reader, None)  # skip header
            for csv_row in reader:
                if len(csv_row) >= 2 and csv_row[0].strip():
                    try:
                        rows.append({
                            "name": csv_row[0].strip(),
                            "quantity": float(csv_row[1].strip()),
                        })
                    except ValueError:
                        continue

        if not rows:
            return {"status": "warning", "message": "No meal data found in request"}

        result = await _upsert_daily_meals(db, meal_date, rows, source="email")

        logger.info(f"Daily meals imported: date={meal_date}, created={result['created']}, updated={result['updated']}")

        return {
            "status": "success",
            "date": meal_date.isoformat(),
            "items_processed": len(rows),
            **result,
        }

    except Exception as e:
        logger.error(f"Error processing daily-meals webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily-meals/upload")
async def upload_daily_meals_csv(
    file: UploadFile = File(...),
    meal_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a CSV file with daily meal counts.
    CSV format: שם מסעדה,מספר עסקאות (restaurant name, transaction count)
    Encoding: cp1255 (Windows Hebrew)
    """
    try:
        content = await file.read()

        # Try multiple encodings
        text = None
        for enc in ["cp1255", "utf-8-sig", "utf-8", "iso-8859-8"]:
            try:
                text = content.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if not text:
            raise HTTPException(status_code=400, detail="Could not decode CSV file")

        # Parse date from filename if not provided (e.g. HpIndig_Hadri_Ochel2526.csv)
        parsed_date = date.today()
        if meal_date:
            parsed_date = date.fromisoformat(meal_date)

        # Parse CSV
        rows: list[dict] = []
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        for csv_row in reader:
            if len(csv_row) >= 2 and csv_row[0].strip():
                try:
                    rows.append({
                        "name": csv_row[0].strip(),
                        "quantity": float(csv_row[1].strip()),
                    })
                except ValueError:
                    continue

        if not rows:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")

        result = await _upsert_daily_meals(db, parsed_date, rows, source="csv_upload")

        return {
            "status": "success",
            "date": parsed_date.isoformat(),
            "filename": file.filename,
            "items_processed": len(rows),
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading daily meals CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-meals")
async def get_daily_meals(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get daily meal counts for a date range."""
    query = select(DailyMealCount).order_by(DailyMealCount.date.desc())

    if from_date:
        query = query.where(DailyMealCount.date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(DailyMealCount.date <= date.fromisoformat(to_date))
    if site_id:
        query = query.where(DailyMealCount.site_id == site_id)

    result = await db.execute(query.options())
    records = result.scalars().all()

    # Group by date
    by_date: dict = {}
    for r in records:
        d = r.date.isoformat()
        if d not in by_date:
            by_date[d] = {"date": d, "items": [], "total": 0}
        by_date[d]["items"].append({
            "site_id": r.site_id,
            "meal_type": r.meal_type,
            "meal_type_en": r.meal_type_en,
            "restaurant_name": r.restaurant_name,
            "quantity": r.quantity,
        })
        by_date[d]["total"] += r.quantity

    return {
        "days": sorted(by_date.values(), key=lambda x: x["date"], reverse=True),
        "total_records": len(records),
    }


@router.post("/daily-meals/poll-now")
async def trigger_meal_email_poll():
    """
    Manually trigger the IMAP email poller to check for new meal reports.
    Useful for testing or forcing an immediate check.
    """
    from backend.services.meal_email_poller import poll_meal_emails
    try:
        result = await poll_meal_emails()
        return result
    except Exception as e:
        logger.error(f"Manual meal poll failed: {e}")
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
            "daily_meals": "POST /api/webhooks/daily-meals",
            "daily_meals_upload": "POST /api/webhooks/daily-meals/upload",
            "daily_meals_get": "GET /api/webhooks/daily-meals",
            "daily_meals_poll": "POST /api/webhooks/daily-meals/poll-now",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

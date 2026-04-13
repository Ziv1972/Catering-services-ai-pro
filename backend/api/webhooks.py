"""
Webhook endpoints for Power Automate integration
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, date, timedelta
from pydantic import BaseModel
from typing import Optional, List
import logging
import re
import io
import csv
import hmac

import base64 as base64_module
import os
import uuid as uuid_module

from backend.database import get_db
from backend.models.violation import (
    Violation, ViolationSource, ViolationStatus,
    ViolationCategory, ViolationSeverity, RestaurantType,
    CATEGORY_FROM_HE, SEVERITY_FROM_HE, RESTAURANT_MAP,
)
from backend.models.meeting import Meeting, MeetingType
from backend.models.site import Site
from backend.models.daily_meal_count import DailyMealCount
from backend.models.attachment import Attachment
from backend.agents.violation_intelligence.agent import ViolationIntelligenceAgent
from backend.config import get_settings
from backend.api.auth import get_current_user
from backend.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


def _verify_webhook_secret(x_webhook_secret: Optional[str] = Header(default=None)):
    """Verify shared-secret header for webhook endpoints."""
    if not settings.WEBHOOK_SECRET:
        # No secret configured — allow (dev mode)
        return
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


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

    logger.info(f"Upserting {len(rows)} rows for date={meal_date}, source={source}")
    for row in rows:
        parsed = _parse_restaurant_line(row["name"])
        qty = row["quantity"]
        logger.info(f"  Row: '{row['name'][:50]}' qty={qty} → site={parsed['site_code']} type={parsed['meal_type_en']}")

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
            logger.warning(f"Skipping row — no site found: name='{row['name']}' parsed_site_code='{parsed['site_code']}'")
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


class ViolationWebhook(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    bodyPreview: Optional[str] = None
    received: Optional[str] = None
    receivedDateTime: Optional[str] = None
    message_id: Optional[str] = None
    # "from" can be a string or object
    from_address: Optional[str] = None
    # Source: "email", "whatsapp", or "form"
    source: Optional[str] = None
    sender_name: Optional[str] = None
    sender_phone: Optional[str] = None
    image_base64: Optional[str] = None
    image_content_type: Optional[str] = None
    # Form-specific fields (MS Forms via Power Automate)
    restaurant: Optional[str] = None  # e.g. "קרית גת - מסעדת בשר"
    category: Optional[str] = None    # Hebrew category label
    severity: Optional[str] = None    # Hebrew severity label


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


@router.post("/violations")
async def receive_violation(
    request: dict,
    db: AsyncSession = Depends(get_db),
    _secret: None = Depends(_verify_webhook_secret),
):
    """
    Webhook endpoint for Power Automate — email, WhatsApp, or MS Forms trigger.
    Receives inspection violations from various sources.

    Email format:
    {
        "from": "inspector@hp.com",
        "subject": "Inspection finding",
        "body": "Kitchen cleanliness issue...",
        "received": "2026-02-20T14:30:00Z",
        "message_id": "outlook-message-id"
    }

    WhatsApp format:
    {
        "source": "whatsapp",
        "sender_name": "John Doe",
        "sender_phone": "+972501234567",
        "body": "Cleanliness issue in dining room",
        "image_base64": "<base64_encoded_image>",
        "image_content_type": "image/jpeg",
        "received": "2026-03-09T12:00:00Z"
    }

    MS Forms format (via Power Automate) — supports up to 5 findings per visit:
    {
        "source": "form",
        "sender_name": "Inspector Name",
        "restaurant": "קרית גת - מסעדת בשר",
        "category_1": "ניקיון מטבח וציוד",
        "severity_1": "גבוה",
        "body_1": "Description of first finding",
        "category_2": "לבוש עובדים",
        "severity_2": "בינוני",
        "body_2": "Description of second finding",
        "received": "2026-03-12T10:00:00Z"
    }
    Note: Each finding (category_N + severity_N + body_N) creates a separate
    violation. Findings 2-5 are optional — empty fields are skipped.
    """
    try:
        # Detect source type
        source_type = request.get('source', 'email').lower()
        is_whatsapp = source_type == 'whatsapp'
        is_form = source_type == 'form'

        logger.info(
            f"Received violation webhook: source={source_type}, "
            f"subject={request.get('subject', 'N/A')}"
        )

        # Extract body text (prefer plain text preview)
        body_text = request.get('bodyPreview') or request.get('body', '')

        # Parse sender info based on source
        from_email = ''
        employee_name = None
        employee_phone = None
        restaurant_type = None
        site_id = None

        if is_form:
            employee_name = request.get('sender_name')
            # Parse restaurant field → site_id + restaurant_type
            restaurant_label = request.get('restaurant', '')
            restaurant_info = RESTAURANT_MAP.get(restaurant_label)
            if restaurant_info:
                site_name_en, restaurant_type = restaurant_info
                # Look up site by name
                code_map = {"Kiryat Gat": "KG", "Nes Ziona": "NZ"}
                site_code = code_map.get(site_name_en)
                if site_code:
                    site_result = await db.execute(
                        select(Site).where(Site.code == site_code)
                    )
                    site = site_result.scalar_one_or_none()
                    site_id = site.id if site else None
            else:
                site_id = await _infer_site_id(body_text, db)

        elif is_whatsapp:
            employee_name = request.get('sender_name')
            employee_phone = request.get('sender_phone')
            site_id = await _infer_site_id(body_text, db)
        else:
            from_email = request.get('from', '')
            if isinstance(from_email, dict):
                from_email = from_email.get('emailAddress', {}).get('address', '')
            site_id = await _infer_site_id(body_text, db)

        # Parse received time
        received_str = request.get('receivedDateTime') or request.get('received')
        received_at = _parse_datetime(received_str)

        # Map source type to enum
        source_map = {
            'email': ViolationSource.EMAIL,
            'whatsapp': ViolationSource.WHATSAPP,
            'form': ViolationSource.FORM,
        }
        violation_source = source_map.get(source_type, ViolationSource.EMAIL)

        # Handle image attachment helper
        image_base64_data = request.get('image_base64')
        image_content_type = request.get('image_content_type', 'image/jpeg')

        async def _save_image(violation_id: int) -> None:
            if not image_base64_data:
                return
            try:
                ext_map = {
                    "image/jpeg": ".jpg", "image/png": ".png",
                    "image/webp": ".webp", "image/gif": ".gif",
                }
                ext = ext_map.get(image_content_type, ".jpg")
                unique_name = f"{uuid_module.uuid4().hex}{ext}"
                entity_dir = os.path.join("uploads", "attachments", "violation", str(violation_id))
                os.makedirs(entity_dir, exist_ok=True)
                file_path = os.path.join(entity_dir, unique_name)

                image_bytes = base64_module.b64decode(image_base64_data)
                with open(file_path, "wb") as f:
                    f.write(image_bytes)

                attachment = Attachment(
                    entity_type="violation",
                    entity_id=violation_id,
                    filename=unique_name,
                    original_filename=f"inspection_image{ext}",
                    file_path=file_path,
                    file_size=len(image_bytes),
                    content_type=image_content_type,
                )
                db.add(attachment)
                logger.info(f"Saved image for violation {violation_id}: {file_path}")
            except Exception as img_err:
                logger.warning(f"Failed to save image: {img_err}")

        # Build list of findings to create.
        # Form submissions: parse numbered fields (category_1..category_5, etc.)
        # Other sources: single violation from body_text.
        findings: list[dict] = []

        if is_form:
            for i in range(1, 6):  # findings 1-5
                he_cat = request.get(f'category_{i}', '').strip()
                he_sev = request.get(f'severity_{i}', '').strip()
                finding_body = request.get(f'body_{i}', '').strip()

                if not he_cat and not finding_body:
                    continue  # empty finding slot — skip

                cat_enum = CATEGORY_FROM_HE.get(he_cat)
                sev_enum = SEVERITY_FROM_HE.get(he_sev)

                findings.append({
                    "body": finding_body or body_text,
                    "category": cat_enum,
                    "severity": sev_enum,
                })

            # Fallback: if no numbered fields found, try flat fields (backward compat)
            if not findings:
                he_cat = request.get('category', '').strip()
                he_sev = request.get('severity', '').strip()
                cat_enum = CATEGORY_FROM_HE.get(he_cat)
                sev_enum = SEVERITY_FROM_HE.get(he_sev)
                findings.append({
                    "body": body_text,
                    "category": cat_enum,
                    "severity": sev_enum,
                })
        else:
            findings.append({
                "body": body_text,
                "category": None,
                "severity": None,
            })

        created_violations = []

        for finding in findings:
            violation = Violation(
                violation_text=finding["body"],
                employee_email=from_email if from_email else None,
                employee_name=employee_name,
                employee_phone=employee_phone,
                source=violation_source,
                source_id=request.get('message_id'),
                received_at=received_at,
                status=ViolationStatus.NEW,
                site_id=site_id,
                restaurant_type=restaurant_type,
                category=finding["category"],
                severity=finding["severity"],
            )

            db.add(violation)
            await db.flush()

            # Save image attachment (only for first violation to avoid duplication)
            if not created_violations:
                await _save_image(violation.id)

            # AI analysis (skip if form already provided category+severity)
            run_ai = not (is_form and finding["category"] and finding["severity"])
            if run_ai:
                try:
                    agent = ViolationIntelligenceAgent()
                    await agent.analyze_violation(
                        db,
                        violation,
                        image_base64=image_base64_data,
                        image_content_type=image_content_type if image_base64_data else None,
                    )
                except Exception as ai_err:
                    logger.warning(f"AI analysis failed (violation still saved): {ai_err}")

            created_violations.append(violation)

            logger.info(
                f"Violation created: ID={violation.id}, source={violation_source.value}, "
                f"Category={violation.category}, Severity={violation.severity}"
            )

        await db.commit()

        # Return response
        if len(created_violations) == 1:
            v = created_violations[0]
            return {
                "status": "success",
                "violation_id": v.id,
                "source": violation_source.value,
                "category": v.category.value if v.category else None,
                "severity": v.severity.value if v.severity else None,
                "ai_summary": v.ai_summary,
                "has_image": bool(image_base64_data),
            }

        return {
            "status": "success",
            "violations_created": len(created_violations),
            "violation_ids": [v.id for v in created_violations],
            "source": violation_source.value,
            "categories": [v.category.value for v in created_violations if v.category],
            "severity": created_violations[0].severity.value if created_violations[0].severity else None,
            "has_image": bool(image_base64_data),
        }

    except Exception as e:
        logger.error(f"Error processing violation webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process violation webhook")


@router.post("/meetings")
async def receive_meeting_from_calendar(
    request: dict,
    db: AsyncSession = Depends(get_db),
    _secret: None = Depends(_verify_webhook_secret),
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
        raise HTTPException(status_code=500, detail="Failed to process meeting webhook")


@router.post("/daily-meals")
async def receive_daily_meals(
    request: dict,
    db: AsyncSession = Depends(get_db),
    _secret: None = Depends(_verify_webhook_secret),
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
        raise HTTPException(status_code=500, detail="Failed to process daily meals webhook")


@router.post("/daily-meals/upload")
async def upload_daily_meals_csv(
    file: UploadFile = File(...),
    meal_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(status_code=500, detail="Failed to upload daily meals CSV")


@router.get("/daily-meals")
async def get_daily_meals(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
async def trigger_meal_email_poll(
    reprocess: bool = Query(default=False, description="Re-scan ALL emails (including already-read)"),
    since_date: Optional[str] = Query(default=None, description="Start date for reprocessing (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger the IMAP email poller to check for new meal reports.

    - Default: checks only UNSEEN (unread) emails
    - reprocess=true: re-scans ALL emails (including read) since since_date
    - since_date: defaults to 30 days ago when reprocessing
    """
    from backend.services.meal_email_poller import poll_meal_emails
    try:
        parsed_since = None
        if since_date:
            parsed_since = date.fromisoformat(since_date)
        result = await poll_meal_emails(
            reprocess=reprocess,
            since_date=parsed_since,
        )
        return result
    except Exception as e:
        logger.error(f"Manual meal poll failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to poll meal emails: {e}")


@router.get("/daily-meals/inbox-scan")
async def scan_meal_inbox(
    since_date: str = Query(default=None, description="YYYY-MM-DD, default 30 days ago"),
    current_user: User = Depends(get_current_user),
):
    """
    Diagnostic: list ALL emails in the monitored inbox since a date.
    Runs multiple IMAP searches to diagnose why emails aren't being found.
    Does NOT process or modify anything.
    """
    import imaplib
    import email as email_lib
    from backend.config import get_settings
    from backend.services.meal_email_poller import _decode_header_value

    settings = get_settings()
    if not settings.IMAP_HOST:
        return {"error": "IMAP not configured"}

    effective_since = date.fromisoformat(since_date) if since_date else (date.today() - timedelta(days=30))
    imap_date_str = effective_since.strftime("%d-%b-%Y")
    subject_filter = settings.MEAL_EMAIL_SUBJECT or "HP_FC_REPORT"

    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST)
        mail.login(settings.IMAP_EMAIL, settings.IMAP_PASSWORD)
        mail.select("INBOX")

        # Run all the search variations to diagnose
        searches = {}

        # 1. ALL emails since date
        s1, d1 = mail.uid("search", None, f"(SINCE {imap_date_str})")
        searches["all_since"] = len(d1[0].split()) if d1[0] else 0
        all_uids = d1[0].split() if d1[0] else []

        # 2. SUBJECT filter only
        s2, d2 = mail.uid("search", None, f'(SUBJECT "{subject_filter}")')
        searches["subject_only"] = len(d2[0].split()) if d2[0] else 0

        # 3. UNSEEN only
        s3, d3 = mail.uid("search", None, "(UNSEEN)")
        searches["unseen_only"] = len(d3[0].split()) if d3[0] else 0

        # 4. UNSEEN + SUBJECT (what the poller uses)
        s4, d4 = mail.uid("search", None, f'(UNSEEN SUBJECT "{subject_filter}")')
        searches["unseen_subject"] = len(d4[0].split()) if d4[0] else 0

        # 5. SINCE + SUBJECT (what reprocess uses)
        s5, d5 = mail.uid("search", None, f'(SINCE {imap_date_str} SUBJECT "{subject_filter}")')
        searches["since_subject"] = len(d5[0].split()) if d5[0] else 0
        report_uids = set(u.decode() for u in (d5[0].split() if d5[0] else []))

        # 6. X-GM-RAW Gmail-specific search (more reliable)
        try:
            s6, d6 = mail.uid("search", None, f'X-GM-RAW "subject:{subject_filter} after:{effective_since.strftime("%Y/%m/%d")}"')
            searches["gmail_raw"] = len(d6[0].split()) if d6[0] else 0
        except Exception:
            searches["gmail_raw"] = "error"

        # Fetch details for ALL emails since date
        emails_info = []
        for uid in all_uids:
            uid_str = uid.decode()
            st, msg_data = mail.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE FROM)] FLAGS)")
            if st != "OK" or not msg_data:
                continue

            flags_str = ""
            msg = None
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email_lib.message_from_bytes(part[1])
                elif isinstance(part, bytes):
                    flags_match = re.search(rb"FLAGS \(([^)]*)\)", part)
                    if flags_match:
                        flags_str = flags_match.group(1).decode()

            if not msg:
                continue

            subject = _decode_header_value(msg.get("Subject", ""))
            date_str = msg.get("Date", "")[:35]

            emails_info.append({
                "uid": uid_str,
                "date": date_str,
                "subject": subject[:100],
                "flags": flags_str,
                "matches_filter": uid_str in report_uids,
            })

        mail.logout()

        return {
            "inbox": settings.IMAP_EMAIL,
            "since": effective_since.isoformat(),
            "subject_filter": subject_filter,
            "search_results": searches,
            "emails": emails_info,
        }
    except Exception as e:
        logger.error(f"Inbox scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Inbox scan failed: {e}")


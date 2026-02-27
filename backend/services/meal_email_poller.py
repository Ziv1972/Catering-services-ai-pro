"""
Automated IMAP email poller for daily FoodHouse meal reports.

Connects to an IMAP mailbox (Gmail, Outlook, etc.), searches for
unread meal-report emails, extracts CSV attachments or inline tables,
and upserts them into the daily_meal_counts table.

Config (in .env):
    IMAP_HOST=imap.gmail.com
    IMAP_EMAIL=your@gmail.com
    IMAP_PASSWORD=abcd efgh ijkl mnop   # Gmail app password
    MEAL_EMAIL_SENDER=noreply@foodhouse  # partial match on From
    MEAL_EMAIL_SUBJECT=Hadri_Ochel       # partial match on Subject
    MEAL_POLL_INTERVAL_MIN=60
"""
import asyncio
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import date, datetime
from typing import Optional
import csv
import io
import logging
import re

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.api.webhooks import _upsert_daily_meals

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────
#  IMAP helpers (sync — run in executor for async usage)
# ──────────────────────────────────────────────────────

def _decode_header_value(raw: str) -> str:
    """Decode a possibly-encoded MIME header."""
    parts = decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_csv_from_attachment(msg: email_lib.message.Message) -> Optional[str]:
    """Walk MIME parts looking for a .csv attachment."""
    for part in msg.walk():
        content_disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)

        if "attachment" in content_disp and filename and filename.lower().endswith(".csv"):
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            # Try multiple Hebrew encodings
            for enc in ["cp1255", "windows-1255", "utf-8-sig", "utf-8", "iso-8859-8"]:
                try:
                    return payload.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
    return None


def _extract_csv_from_body(msg: email_lib.message.Message) -> Optional[str]:
    """Fallback: look for CSV-like data in the email body (plain text)."""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/plain":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            for enc in ["cp1255", "windows-1255", "utf-8-sig", "utf-8", "iso-8859-8"]:
                try:
                    text = payload.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                continue
            # Check if it looks like CSV with Hebrew restaurant names
            if "מסעדה" in text or "עסקאות" in text:
                return text
    return None


def _parse_csv_text(text: str) -> list[dict]:
    """Parse CSV text into rows [{name, quantity}]."""
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    for csv_row in reader:
        if len(csv_row) >= 2 and csv_row[0].strip():
            try:
                qty = float(csv_row[1].strip().replace(",", ""))
                rows.append({"name": csv_row[0].strip(), "quantity": qty})
            except ValueError:
                continue
    return rows


def _extract_date_from_email(msg: email_lib.message.Message) -> date:
    """Try to extract the meal date from the email Date header."""
    date_str = msg.get("Date", "")
    if date_str:
        try:
            parsed = email_lib.utils.parsedate_to_datetime(date_str)
            return parsed.date()
        except Exception:
            pass
    return date.today()


def _fetch_meal_emails(
    imap_host: str,
    imap_email: str,
    imap_password: str,
    sender_filter: str = "",
    subject_filter: str = "",
) -> list[dict]:
    """
    Connect to IMAP, find unread meal report emails, extract CSV data.
    Returns list of {date, rows, message_uid} dicts.
    Marks processed emails as read.
    """
    results: list[dict] = []

    try:
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(imap_email, imap_password)
        mail.select("INBOX")

        # Build IMAP search criteria
        criteria_parts = ["UNSEEN"]
        if sender_filter:
            criteria_parts.append(f'FROM "{sender_filter}"')
        if subject_filter:
            criteria_parts.append(f'SUBJECT "{subject_filter}"')

        search_criteria = "(" + " ".join(criteria_parts) + ")"
        status, data = mail.uid("search", None, search_criteria)

        if status != "OK" or not data[0]:
            mail.logout()
            return results

        uids = data[0].split()
        logger.info(f"Found {len(uids)} unread meal email(s)")

        for uid in uids:
            try:
                status, msg_data = mail.uid("fetch", uid, "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    continue

                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)

                subject = _decode_header_value(msg.get("Subject", ""))
                logger.info(f"Processing meal email: {subject}")

                # Try attachment first, then body
                csv_text = _extract_csv_from_attachment(msg)
                if not csv_text:
                    csv_text = _extract_csv_from_body(msg)

                if not csv_text:
                    logger.warning(f"No CSV data found in email: {subject}")
                    continue

                rows = _parse_csv_text(csv_text)
                if not rows:
                    logger.warning(f"No valid rows parsed from email: {subject}")
                    continue

                meal_date = _extract_date_from_email(msg)

                results.append({
                    "date": meal_date,
                    "rows": rows,
                    "uid": uid,
                    "subject": subject,
                })

                # Mark as read
                mail.uid("store", uid, "+FLAGS", "\\Seen")

            except Exception as e:
                logger.error(f"Error processing email uid={uid}: {e}")
                continue

        mail.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP connection error: {e}")
    except Exception as e:
        logger.error(f"Email poller error: {e}")

    return results


# ──────────────────────────────────────────────────────
#  Async poll function (called by scheduler)
# ──────────────────────────────────────────────────────

async def poll_meal_emails() -> dict:
    """
    Check for new meal report emails and process them.
    Returns summary of what was processed.
    """
    settings = get_settings()

    if not settings.IMAP_HOST or not settings.IMAP_EMAIL or not settings.IMAP_PASSWORD:
        return {"status": "skipped", "reason": "IMAP not configured"}

    # Run IMAP fetch in thread (it's blocking IO)
    loop = asyncio.get_event_loop()
    emails = await loop.run_in_executor(
        None,
        _fetch_meal_emails,
        settings.IMAP_HOST,
        settings.IMAP_EMAIL,
        settings.IMAP_PASSWORD,
        settings.MEAL_EMAIL_SENDER,
        settings.MEAL_EMAIL_SUBJECT,
    )

    if not emails:
        return {"status": "ok", "emails_found": 0}

    total_created = 0
    total_updated = 0
    processed = []

    for em in emails:
        try:
            async with AsyncSessionLocal() as db:
                result = await _upsert_daily_meals(
                    db, em["date"], em["rows"], source="email_imap",
                )
                total_created += result["created"]
                total_updated += result["updated"]
                processed.append({
                    "subject": em["subject"],
                    "date": em["date"].isoformat(),
                    "rows": len(em["rows"]),
                    **result,
                })
        except Exception as e:
            logger.error(f"Error upserting meal data from email: {e}")
            processed.append({
                "subject": em.get("subject", "?"),
                "error": str(e),
            })

    logger.info(
        f"Meal email poll complete: {len(emails)} emails, "
        f"{total_created} created, {total_updated} updated"
    )

    return {
        "status": "ok",
        "emails_found": len(emails),
        "total_created": total_created,
        "total_updated": total_updated,
        "processed": processed,
    }


# ──────────────────────────────────────────────────────
#  Background scheduler
# ──────────────────────────────────────────────────────

async def start_meal_email_scheduler():
    """Background loop that polls for meal emails at a configured interval."""
    settings = get_settings()

    if not settings.IMAP_HOST:
        logger.info("IMAP not configured — meal email poller disabled")
        return

    interval = max(settings.MEAL_POLL_INTERVAL_MIN, 5) * 60  # min 5 minutes
    logger.info(
        f"Meal email poller started: checking {settings.IMAP_EMAIL} "
        f"every {settings.MEAL_POLL_INTERVAL_MIN} min"
    )

    # Initial delay to let the app finish startup
    await asyncio.sleep(30)

    while True:
        try:
            result = await poll_meal_emails()
            if result.get("emails_found", 0) > 0:
                logger.info(f"Meal poll result: {result}")
        except Exception as e:
            logger.error(f"Meal email scheduler error: {e}")

        await asyncio.sleep(interval)

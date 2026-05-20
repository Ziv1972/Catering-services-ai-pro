"""
Communication Hub Agent
Drafts communications, generates reports, handles stakeholder messaging
"""
from backend.agents.base_agent import BaseAgent
from backend.models.violation import Violation
from backend.models.meeting import Meeting
from backend.models.proforma import Proforma
from backend.models.operations import Anomaly
from backend.models.saved_report import SavedReport, MonthlyReportSent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

# Supplier ID for FoodHouse — used to decide when a month is "ready" to send.
# Memory: FoodHouse is supplier id=1; if it ever changes, this constant is the
# single place to update.
FOODHOUSE_SUPPLIER_ID = 1


class CommunicationHubAgent(BaseAgent):
    """Drafts communications and generates reports for stakeholders"""

    def __init__(self):
        super().__init__(name="CommunicationHubAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action", "weekly_report")
        db = context["db"]

        if action == "weekly_report":
            return await self.generate_weekly_report(db)
        elif action == "draft_vendor_email":
            vendor = context.get("vendor_name", "")
            topic = context.get("topic", "")
            return await self.draft_vendor_email(vendor, topic, context)
        elif action == "draft_management_update":
            return await self.draft_management_update(db)

        return {"error": f"Unknown action: {action}"}

    async def generate_weekly_report(self, db: AsyncSession) -> Dict[str, Any]:
        """Generate a weekly status report for management"""
        week_ago = datetime.utcnow() - timedelta(days=7)

        violations_result = await db.execute(
            select(func.count(Violation.id)).where(
                Violation.received_at >= week_ago
            )
        )
        violation_count = violations_result.scalar() or 0

        meetings_result = await db.execute(
            select(func.count(Meeting.id)).where(
                Meeting.scheduled_at >= week_ago
            )
        )
        meeting_count = meetings_result.scalar() or 0

        anomalies_result = await db.execute(
            select(func.count(Anomaly.id)).where(
                Anomaly.detected_at >= week_ago.date()
            )
        )
        anomaly_count = anomalies_result.scalar() or 0

        proformas_result = await db.execute(
            select(func.sum(Proforma.total_amount)).where(
                Proforma.invoice_date >= week_ago.date()
            )
        )
        weekly_spend = proformas_result.scalar() or 0

        prompt = f"""
        Generate a concise weekly catering operations report for HP Israel management:

        THIS WEEK'S DATA:
        - Violations received: {violation_count}
        - Meetings held: {meeting_count}
        - Anomalies detected: {anomaly_count}
        - Total spending: {weekly_spend:,.2f} ILS

        Return JSON:
        {{
            "subject": "email subject line",
            "summary": "2-3 sentence executive summary",
            "highlights": ["positive developments"],
            "concerns": ["items needing attention"],
            "action_items": ["specific next steps"],
            "metrics_snapshot": {{
                "violations": {violation_count},
                "meetings": {meeting_count},
                "anomalies": {anomaly_count},
                "spend_ils": {weekly_spend:.2f}
            }}
        }}
        """

        report = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"weekly_report": report}

    async def draft_vendor_email(
        self,
        vendor_name: str,
        topic: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Draft an email to a vendor"""
        details = context.get("details", "")

        prompt = f"""
        Draft a professional email to catering vendor "{vendor_name}" about: {topic}

        ADDITIONAL CONTEXT:
        {details}

        Return JSON:
        {{
            "subject": "email subject",
            "body": "full email body text",
            "tone": "professional|firm|friendly",
            "follow_up_needed": true|false,
            "follow_up_date": "suggested follow-up date if needed"
        }}

        Write in professional English. Be specific and actionable.
        Keep it concise (3-5 paragraphs max).
        """

        email = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"draft_email": email}

    async def draft_management_update(self, db: AsyncSession) -> Dict[str, Any]:
        """Draft a management update with current status"""
        month_ago = datetime.utcnow() - timedelta(days=30)

        violations_result = await db.execute(
            select(func.count(Violation.id)).where(
                Violation.received_at >= month_ago
            )
        )
        monthly_violations = violations_result.scalar() or 0

        resolved_result = await db.execute(
            select(func.count(Violation.id)).where(
                Violation.received_at >= month_ago,
                Violation.resolved_at.isnot(None),
            )
        )
        resolved_count = resolved_result.scalar() or 0

        prompt = f"""
        Draft a monthly management update for HP Israel catering operations:

        MONTHLY STATS:
        - Total violations: {monthly_violations}
        - Resolved: {resolved_count}
        - Resolution rate: {(resolved_count / monthly_violations * 100) if monthly_violations else 100:.0f}%

        Return JSON:
        {{
            "subject": "Monthly Catering Operations Update",
            "body": "Full update text (3-4 paragraphs)",
            "key_metrics": {{
                "violations": {monthly_violations},
                "resolved": {resolved_count},
                "resolution_rate_pct": {(resolved_count / monthly_violations * 100) if monthly_violations else 100:.0f}
            }}
        }}
        """

        update = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"management_update": update}

    # ─── Auto-email scheduled reports ─────────────────────────────────────

    async def maybe_send_monthly_reports(
        self,
        db: AsyncSession,
        proforma_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Trigger entry-point called after a successful proforma upload.

        Walks every SavedReport with `auto_email_enabled=True` and sends the
        ones whose configured trigger is now satisfied. Only one trigger
        type is implemented: `monthly_after_foodhouse` — fires when both
        Nes Ziona + Kiryat Gat FoodHouse proformas exist for a given month.

        Dedupe is enforced via the MonthlyReportSent table — each
        (saved_report_id, year, month) is sent at most once. Failures
        are recorded too so retries are explicit, not silent.

        Returns a summary {sent: int, skipped: int, errors: [..]}.
        Never raises — callers (the upload endpoint) should treat any
        result as advisory.
        """
        summary: Dict[str, Any] = {"sent": 0, "skipped": 0, "errors": []}

        # Which (year, month) pairs have both sites uploaded for FoodHouse?
        ready_months = await self._foodhouse_complete_months(db)
        if not ready_months:
            return summary

        # All saved reports that opted into auto-email.
        res = await db.execute(
            select(SavedReport).where(SavedReport.auto_email_enabled == True)  # noqa: E712
        )
        reports = res.scalars().all()
        if not reports:
            return summary

        # Already-sent (saved_report_id, year, month) pairs — skip these.
        sent_res = await db.execute(select(MonthlyReportSent))
        already_sent = {
            (s.saved_report_id, s.year, s.month)
            for s in sent_res.scalars().all()
            if s.status == "sent"
        }

        for saved in reports:
            if (saved.auto_email_trigger or "monthly_after_foodhouse") != "monthly_after_foodhouse":
                continue
            for year, month in ready_months:
                key = (saved.id, year, month)
                if key in already_sent:
                    summary["skipped"] += 1
                    continue
                try:
                    await self._send_one_monthly_report(db, saved, year, month)
                    summary["sent"] += 1
                except Exception as e:
                    logger.exception("Auto-email failed for saved_report=%s %d-%02d", saved.id, year, month)
                    summary["errors"].append({
                        "saved_report_id": saved.id,
                        "year": year, "month": month, "error": str(e),
                    })
                    # Record the failure so we don't retry on every upload
                    db.add(MonthlyReportSent(
                        saved_report_id=saved.id, year=year, month=month,
                        recipient_count=0, status="failed", error=str(e)[:500],
                    ))
                    await db.commit()

        return summary

    async def _foodhouse_complete_months(self, db: AsyncSession) -> List[tuple]:
        """Return (year, month) pairs where FoodHouse has uploaded proformas
        for BOTH sites (site_id 1 = NZ, site_id 2 = KG)."""
        from backend.utils.db_compat import extract_year, extract_month
        q = (
            select(
                extract_year(Proforma.invoice_date).label("y"),
                extract_month(Proforma.invoice_date).label("m"),
                func.count(func.distinct(Proforma.site_id)).label("sites"),
            )
            .where(Proforma.supplier_id == FOODHOUSE_SUPPLIER_ID)
            .where(Proforma.invoice_date.isnot(None))
            .group_by(extract_year(Proforma.invoice_date), extract_month(Proforma.invoice_date))
        )
        rows = (await db.execute(q)).all()
        complete = []
        for y, m, sites in rows:
            try:
                if int(sites) >= 2:
                    complete.append((int(y), int(m)))
            except (TypeError, ValueError):
                continue
        return complete

    async def _send_one_monthly_report(
        self,
        db: AsyncSession,
        saved: SavedReport,
        year: int,
        month: int,
    ) -> None:
        """Run a SavedReport for (year, month), build the .xlsx, email it,
        and record the send. Raises on any failure (caller catches)."""
        from backend.schemas.report import ReportConfig
        from backend.services.report_engine import ReportEngine
        from backend.utils.report_export import build_xlsx
        from backend.services.email_sender import send_xlsx_email
        from backend.api.reports import _default_title

        # Materialize config, then narrow filters to this specific month
        cfg = ReportConfig(**json.loads(saved.config_json))
        cfg = cfg.model_copy(update={
            "filters": cfg.filters.model_copy(update={
                "year": year, "from_month": month, "to_month": month,
            })
        })

        engine = ReportEngine(db)
        report = await engine.run(cfg)
        title = saved.name or _default_title(cfg)
        xlsx_bytes = build_xlsx(report, cfg, title)

        recipients_raw = (saved.auto_email_recipients or "").strip()
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
        if not recipients:
            raise ValueError("no recipients configured")

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        period = f"{month_names[month - 1]} {year}"
        subject = f"[Catering AI] {saved.name} — {period}"
        body = (
            f"Automated monthly report from Catering AI Pro.\n\n"
            f"Report: {saved.name}\n"
            f"Period: {period}\n"
            f"Generated: {datetime.utcnow().date().isoformat()}\n\n"
            f"The full table is attached as an Excel file (.xlsx)."
        )
        filename = f"{saved.name}_{year}-{month:02d}.xlsx"

        count = send_xlsx_email(
            recipients=recipients,
            subject=subject,
            body=body,
            xlsx_bytes=xlsx_bytes,
            xlsx_filename=filename,
        )

        db.add(MonthlyReportSent(
            saved_report_id=saved.id, year=year, month=month,
            recipient_count=count, status="sent",
        ))
        await db.commit()
        logger.info(
            "Auto-emailed saved_report=%s for %d-%02d to %d recipient(s)",
            saved.id, year, month, count,
        )

    def _get_system_prompt(self) -> str:
        return (
            "You are a communications assistant for Ziv Reshef-Simchoni, "
            "Food Service Manager at HP Israel.\n\n"
            "Your role is to draft professional communications, "
            "generate reports, and help manage stakeholder messaging.\n\n"
            "Context:\n"
            "- Communications go to: HP management, vendors, site managers, employees\n"
            "- Tone should be professional and data-driven\n"
            "- Reports should highlight both achievements and areas for improvement\n"
            "- Vendor emails should be firm but collaborative\n"
            "- All communications should be actionable"
        )

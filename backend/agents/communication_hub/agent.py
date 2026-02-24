"""
Communication Hub Agent
Drafts communications, generates reports, handles stakeholder messaging
"""
from backend.agents.base_agent import BaseAgent
from backend.models.complaint import Complaint
from backend.models.meeting import Meeting
from backend.models.proforma import Proforma
from backend.models.operations import Anomaly
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Dict, Any
import json


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

        complaints_result = await db.execute(
            select(func.count(Complaint.id)).where(
                Complaint.received_at >= week_ago
            )
        )
        complaint_count = complaints_result.scalar() or 0

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
        - Complaints received: {complaint_count}
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
                "complaints": {complaint_count},
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

        complaints_result = await db.execute(
            select(func.count(Complaint.id)).where(
                Complaint.received_at >= month_ago
            )
        )
        monthly_complaints = complaints_result.scalar() or 0

        resolved_result = await db.execute(
            select(func.count(Complaint.id)).where(
                Complaint.received_at >= month_ago,
                Complaint.resolved_at.isnot(None),
            )
        )
        resolved_count = resolved_result.scalar() or 0

        prompt = f"""
        Draft a monthly management update for HP Israel catering operations:

        MONTHLY STATS:
        - Total complaints: {monthly_complaints}
        - Resolved: {resolved_count}
        - Resolution rate: {(resolved_count / monthly_complaints * 100) if monthly_complaints else 100:.0f}%

        Return JSON:
        {{
            "subject": "Monthly Catering Operations Update",
            "body": "Full update text (3-4 paragraphs)",
            "key_metrics": {{
                "complaints": {monthly_complaints},
                "resolved": {resolved_count},
                "resolution_rate_pct": {(resolved_count / monthly_complaints * 100) if monthly_complaints else 100:.0f}
            }}
        }}
        """

        update = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"management_update": update}

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

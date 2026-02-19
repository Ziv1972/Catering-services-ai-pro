"""
Complaint Intelligence Agent
Analyzes complaints, detects patterns, suggests actions
"""
from backend.agents.base_agent import BaseAgent
from backend.models.complaint import (
    Complaint, ComplaintPattern, ComplaintSeverity,
    ComplaintCategory, ComplaintStatus
)
from backend.models.site import Site
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import uuid


class ComplaintIntelligenceAgent(BaseAgent):
    """Analyzes complaints, detects patterns, and suggests responses"""

    def __init__(self):
        super().__init__(name="ComplaintIntelligenceAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process complaint context"""
        action = context.get("action", "analyze")
        db = context["db"]

        if action == "analyze":
            complaint = context["complaint"]
            analysis = await self.analyze_complaint(db, complaint)
            return {"analysis": analysis}
        elif action == "detect_patterns":
            days = context.get("lookback_days", 7)
            patterns = await self.detect_patterns(db, lookback_days=days)
            return {"patterns": patterns}
        elif action == "draft_response":
            complaint = context["complaint"]
            draft = await self.draft_acknowledgment(db, complaint)
            return {"draft": draft}
        elif action == "weekly_summary":
            summary = await self.generate_weekly_summary(db)
            return {"summary": summary}

        return {"error": f"Unknown action: {action}"}

    async def analyze_complaint(
        self,
        db: AsyncSession,
        complaint: Complaint
    ) -> Dict[str, Any]:
        """Analyze a single complaint using AI"""

        site_name = "Unknown"
        if complaint.site_id:
            result = await db.execute(select(Site).where(Site.id == complaint.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name

        prompt = f"""
        Analyze this employee complaint from HP Israel catering services:

        COMPLAINT TEXT:
        {complaint.complaint_text}

        CONTEXT:
        - Source: {complaint.source}
        - Site: {site_name}
        - Date: {complaint.received_at.strftime('%Y-%m-%d %H:%M')}

        Provide detailed analysis as JSON:
        {{
            "category": "food_quality|temperature|service|variety|dietary|cleanliness|equipment|other",
            "severity": "low|medium|high|critical",
            "sentiment_score": -1.0 to 1.0 (negative to positive),
            "summary": "One clear sentence summarizing the complaint",
            "root_cause": "Likely underlying cause based on the complaint text",
            "suggested_action": "Specific, actionable step Ziv should take",
            "urgency": "immediate|today|this_week|routine",
            "requires_vendor_action": true|false,
            "time_pattern": "Any time-of-day pattern mentioned (e.g., 'lunch rush', '12:45pm', 'morning')"
        }}

        Be specific and actionable in suggested_action. Consider:
        - Is this a recurring issue that needs systematic fix?
        - Is this a vendor performance issue?
        - Is this an equipment/facility issue?
        - Is this a one-time incident?
        """

        analysis = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        complaint.category = ComplaintCategory(analysis["category"])
        complaint.severity = ComplaintSeverity(analysis["severity"])
        complaint.sentiment_score = float(analysis["sentiment_score"])
        complaint.ai_summary = analysis["summary"]
        complaint.ai_root_cause = analysis["root_cause"]
        complaint.ai_suggested_action = analysis["suggested_action"]
        complaint.requires_vendor_action = analysis.get("requires_vendor_action", False)

        return analysis

    async def detect_patterns(
        self,
        db: AsyncSession,
        lookback_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Detect patterns across recent complaints"""

        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        result = await db.execute(
            select(Complaint)
            .where(Complaint.received_at >= cutoff_date)
            .order_by(Complaint.received_at.desc())
        )
        complaints = result.scalars().all()

        if len(complaints) < 2:
            return []

        complaint_data = []
        for c in complaints:
            complaint_data.append({
                "id": c.id,
                "date": c.received_at.isoformat(),
                "category": c.category.value if c.category else None,
                "severity": c.severity.value if c.severity else None,
                "summary": c.ai_summary or c.complaint_text[:100],
                "root_cause": c.ai_root_cause
            })

        prompt = f"""
        Analyze these {len(complaints)} complaints from the last {lookback_days} days for patterns:

        COMPLAINTS:
        {json.dumps(complaint_data, indent=2)}

        Identify meaningful patterns. Return as JSON array:
        [{{
            "pattern_type": "recurring_issue|time_based|location_based|trend",
            "description": "Clear description of the pattern",
            "complaint_ids": [list of complaint IDs that share this pattern],
            "severity": "low|medium|high|critical",
            "recommendation": "Specific action to address this pattern",
            "evidence": "What makes this a real pattern, not coincidence"
        }}]

        Only report patterns where:
        - At least 2-3 complaints share the same specific issue
        - There's a clear time, location, or cause pattern
        - It's actionable (not just "people complain sometimes")

        Return empty array [] if no meaningful patterns found.
        """

        patterns = await self.generate_structured_response(prompt)

        if not isinstance(patterns, list):
            return []

        for pattern_data in patterns:
            pattern_id = str(uuid.uuid4())

            for complaint_id in pattern_data.get("complaint_ids", []):
                result = await db.execute(
                    select(Complaint).where(Complaint.id == complaint_id)
                )
                complaint = result.scalar_one_or_none()
                if complaint:
                    complaint.pattern_group_id = pattern_id

            complaint_ids = pattern_data.get("complaint_ids", [])
            first_complaint = await db.execute(
                select(Complaint)
                .where(Complaint.id.in_(complaint_ids))
                .order_by(Complaint.received_at.asc())
                .limit(1)
            )
            last_complaint = await db.execute(
                select(Complaint)
                .where(Complaint.id.in_(complaint_ids))
                .order_by(Complaint.received_at.desc())
                .limit(1)
            )

            first = first_complaint.scalar_one_or_none()
            last = last_complaint.scalar_one_or_none()

            if first and last:
                pattern = ComplaintPattern(
                    pattern_id=pattern_id,
                    pattern_type=pattern_data["pattern_type"],
                    description=pattern_data["description"],
                    severity=pattern_data["severity"],
                    complaint_count=len(complaint_ids),
                    first_occurrence=first.received_at,
                    last_occurrence=last.received_at,
                    recommendation=pattern_data.get("recommendation")
                )
                db.add(pattern)

        await db.commit()

        return patterns

    async def draft_acknowledgment(
        self,
        db: AsyncSession,
        complaint: Complaint
    ) -> str:
        """Draft an acknowledgment response for a complaint"""

        site_name = "Unknown"
        if complaint.site_id:
            result = await db.execute(select(Site).where(Site.id == complaint.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name

        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in complaint.complaint_text)
        language = "Hebrew" if has_hebrew else "English"

        prompt = f"""
        Draft an acknowledgment email for this complaint:

        COMPLAINT: {complaint.complaint_text}
        SITE: {site_name}
        AI ANALYSIS: {complaint.ai_summary}
        SUGGESTED ACTION: {complaint.ai_suggested_action}
        SEVERITY: {complaint.severity.value if complaint.severity else 'unknown'}

        TONE: Professional, empathetic, action-oriented
        LENGTH: 2-3 sentences
        LANGUAGE: {language}

        Structure:
        1. Thank them for the specific feedback
        2. Brief acknowledgment of the issue
        3. What you're doing about it (be honest, don't over-promise)

        Return ONLY the email text, no subject line, no preamble.
        """

        draft = await self.generate_response(prompt, system_prompt=self._get_system_prompt())

        return draft.strip()

    async def generate_weekly_summary(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate weekly summary of complaints for dashboard"""

        week_ago = datetime.utcnow() - timedelta(days=7)

        result = await db.execute(
            select(Complaint).where(Complaint.received_at >= week_ago)
        )
        complaints = result.scalars().all()

        patterns_result = await db.execute(
            select(ComplaintPattern)
            .where(
                and_(
                    ComplaintPattern.is_active == True,
                    ComplaintPattern.last_occurrence >= week_ago
                )
            )
        )
        patterns = patterns_result.scalars().all()

        category_counts = {}
        for c in complaints:
            if c.category:
                cat = c.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1

        severity_counts = {}
        for c in complaints:
            if c.severity:
                sev = c.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        responded = len([c for c in complaints if c.acknowledged_at])
        response_rate = (responded / len(complaints) * 100) if complaints else 0

        resolved = [c for c in complaints if c.resolved_at and c.received_at]
        if resolved:
            avg_resolution_hours = sum(
                (c.resolved_at - c.received_at).total_seconds() / 3600
                for c in resolved
            ) / len(resolved)
        else:
            avg_resolution_hours = 0

        return {
            "total_complaints": len(complaints),
            "by_category": category_counts,
            "by_severity": severity_counts,
            "active_patterns": len(patterns),
            "response_rate": round(response_rate, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "critical_count": severity_counts.get("critical", 0),
            "high_count": severity_counts.get("high", 0)
        }

    def _get_system_prompt(self) -> str:
        """System prompt for complaint analysis"""
        return (
            "You are an AI assistant helping Ziv Reshef-Simchoni, "
            "the Food Service Manager at HP Israel.\n\n"
            "Your role is to analyze employee complaints about catering "
            "services and provide actionable insights.\n\n"
            "Context:\n"
            "- Ziv manages catering across two sites: Nes Ziona and Kiryat Gat\n"
            "- He works with vendors (Foodhouse, L.Eshel, etc.) who provide meals\n"
            "- Common issues: food temperature, quality, variety, dietary accommodations\n"
            "- Ziv values specific, actionable recommendations over vague advice\n\n"
            "When analyzing complaints:\n"
            "- Be specific about root causes\n"
            "- Suggest concrete actions Ziv can take\n"
            "- Consider if it's a vendor issue, equipment issue, or process issue\n"
            "- Note if it's part of a larger pattern\n"
            "- Be empathetic but professional"
        )

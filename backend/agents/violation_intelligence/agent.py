"""
Violation Intelligence Agent
Analyzes inspection findings (violations), detects patterns, suggests actions
"""
from backend.agents.base_agent import BaseAgent
from backend.models.violation import (
    Violation, ViolationPattern, ViolationSeverity,
    ViolationCategory, ViolationStatus, FineRule,
    CATEGORY_LABELS_HE,
)
from backend.models.site import Site
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
import json
import uuid

logger = logging.getLogger(__name__)

# Build category options string for AI prompts
_CATEGORY_OPTIONS = "|".join(c.value for c in ViolationCategory)


class ViolationIntelligenceAgent(BaseAgent):
    """Analyzes inspection violations, detects patterns, and suggests responses"""

    def __init__(self):
        super().__init__(name="ViolationIntelligenceAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process violation context"""
        action = context.get("action", "analyze")
        db = context["db"]

        if action == "analyze":
            violation = context["violation"]
            analysis = await self.analyze_violation(db, violation)
            return {"analysis": analysis}
        elif action == "detect_patterns":
            days = context.get("lookback_days", 7)
            patterns = await self.detect_patterns(db, lookback_days=days)
            return {"patterns": patterns}
        elif action == "draft_response":
            violation = context["violation"]
            draft = await self.draft_acknowledgment(db, violation)
            return {"draft": draft}
        elif action == "weekly_summary":
            summary = await self.generate_weekly_summary(db)
            return {"summary": summary}

        return {"error": f"Unknown action: {action}"}

    async def analyze_violation(
        self,
        db: AsyncSession,
        violation: Violation,
        image_base64: Optional[str] = None,
        image_content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze a single violation using AI, optionally with an attached image"""

        site_name = "Unknown"
        if violation.site_id:
            result = await db.execute(select(Site).where(Site.id == violation.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name

        # Step 0: If image provided, get visual description via Claude Vision
        image_description = ""
        if image_base64 and image_content_type:
            try:
                image_description = await self.generate_vision_response(
                    prompt=(
                        "Describe what you see in this image from a catering/food service inspection context. "
                        "Focus on: food condition, hygiene issues, equipment damage, cleanliness problems, "
                        "portion size, presentation quality, staff attire, or any other issue relevant to "
                        "a restaurant inspection finding. "
                        "Be specific and factual. Keep your description under 200 words."
                    ),
                    image_base64=image_base64,
                    image_media_type=image_content_type,
                    system_prompt=self._get_system_prompt(),
                )
            except Exception as e:
                logger.warning(f"Vision analysis failed: {e}")
                image_description = "[Image provided but vision analysis failed]"

        image_section = ""
        if image_description:
            image_section = f"""
        IMAGE ANALYSIS (from attached photo):
        {image_description}
        """

        restaurant_info = ""
        if violation.restaurant_type:
            restaurant_info = f"\n        - Restaurant type: {violation.restaurant_type.value}"

        prompt = f"""
        Analyze this inspection finding from HP Israel catering services:

        VIOLATION TEXT:
        {violation.violation_text}
        {image_section}
        CONTEXT:
        - Source: {violation.source}
        - Site: {site_name}{restaurant_info}
        - Date: {violation.received_at.strftime('%Y-%m-%d %H:%M')}
        - Has attached photo: {"Yes" if image_base64 else "No"}

        Provide detailed analysis as JSON:
        {{
            "category": "{_CATEGORY_OPTIONS}",
            "severity": "low|medium|high|critical",
            "sentiment_score": -1.0 to 1.0 (negative to positive),
            "summary": "One clear sentence summarizing the finding",
            "root_cause": "Likely underlying cause based on the violation text",
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

        violation.category = ViolationCategory(analysis["category"])
        violation.severity = ViolationSeverity(analysis["severity"])
        violation.sentiment_score = float(analysis["sentiment_score"])
        violation.ai_summary = analysis["summary"]
        violation.ai_root_cause = analysis["root_cause"]
        violation.ai_suggested_action = analysis["suggested_action"]
        violation.requires_vendor_action = analysis.get("requires_vendor_action", False)

        # Step 2: Match violation to fine rule from catalog
        fine_match = await self._match_fine_rule(db, violation)
        if fine_match:
            analysis["suggested_fine_rule_id"] = fine_match.get("suggested_fine_rule_id")
            analysis["suggested_fine_rule_name"] = fine_match.get("suggested_fine_rule_name")
            analysis["suggested_fine_amount"] = fine_match.get("suggested_fine_amount")
            analysis["fine_match_confidence"] = fine_match.get("fine_match_confidence", 0.0)
            analysis["fine_match_reasoning"] = fine_match.get("fine_match_reasoning", "")

        return analysis

    async def _match_fine_rule(
        self,
        db: AsyncSession,
        violation: Violation
    ) -> Optional[Dict[str, Any]]:
        """Match a violation to the best fine rule from the catalog"""
        try:
            result = await db.execute(
                select(FineRule).where(FineRule.is_active == True)
            )
            rules = result.scalars().all()

            if not rules:
                return None

            rules_list = [
                {
                    "id": r.id,
                    "name": r.name,
                    "category": r.category.value if r.category else "other",
                    "amount": r.amount,
                    "description": r.description or "",
                }
                for r in rules
            ]

            prompt = f"""
            Given this inspection violation and the fine rule catalog below,
            determine which fine rule best matches the violation.

            VIOLATION TEXT:
            {violation.violation_text}

            AI ANALYSIS SUMMARY:
            {violation.ai_summary or "N/A"}

            AI CATEGORY:
            {violation.category.value if violation.category else "unknown"}

            FINE RULE CATALOG:
            {json.dumps(rules_list, indent=2, ensure_ascii=False)}

            Return a JSON object:
            {{
                "suggested_fine_rule_id": <rule id or null if no match>,
                "suggested_fine_rule_name": "<rule name or null>",
                "suggested_fine_amount": <rule amount or null>,
                "fine_match_confidence": <0.0 to 1.0>,
                "fine_match_reasoning": "<brief explanation of why this rule matches>"
            }}

            Guidelines:
            - Only suggest a rule if the violation clearly describes a finding matching that rule
            - Confidence >= 0.7 means strong match (auto-apply)
            - Confidence 0.4-0.7 means possible match (suggest but don't auto-apply)
            - Confidence < 0.4 means no meaningful match (return null for id/name/amount)
            - Consider the violation category and the rule category
            - Hebrew text violations are common — match based on meaning
            """

            match_result = await self.generate_structured_response(
                prompt=prompt,
                system_prompt=self._get_system_prompt()
            )

            if not match_result or not isinstance(match_result, dict):
                return None

            return {
                "suggested_fine_rule_id": match_result.get("suggested_fine_rule_id"),
                "suggested_fine_rule_name": match_result.get("suggested_fine_rule_name"),
                "suggested_fine_amount": match_result.get("suggested_fine_amount"),
                "fine_match_confidence": float(match_result.get("fine_match_confidence", 0.0)),
                "fine_match_reasoning": match_result.get("fine_match_reasoning", ""),
            }
        except Exception as e:
            logger.warning("Fine rule matching failed: %s", e)
            return None

    async def detect_patterns(
        self,
        db: AsyncSession,
        lookback_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Detect patterns across recent violations"""

        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        result = await db.execute(
            select(Violation)
            .where(Violation.received_at >= cutoff_date)
            .order_by(Violation.received_at.desc())
        )
        violations = result.scalars().all()

        if len(violations) < 2:
            return []

        violation_data = []
        for v in violations:
            violation_data.append({
                "id": v.id,
                "date": v.received_at.isoformat(),
                "category": v.category.value if v.category else None,
                "severity": v.severity.value if v.severity else None,
                "summary": v.ai_summary or v.violation_text[:100],
                "root_cause": v.ai_root_cause
            })

        prompt = f"""
        Analyze these {len(violations)} inspection violations from the last {lookback_days} days for patterns:

        VIOLATIONS:
        {json.dumps(violation_data, indent=2)}

        Identify meaningful patterns. Return as JSON array:
        [{{
            "pattern_type": "recurring_issue|time_based|location_based|trend",
            "description": "Clear description of the pattern",
            "violation_ids": [list of violation IDs that share this pattern],
            "severity": "low|medium|high|critical",
            "recommendation": "Specific action to address this pattern",
            "evidence": "What makes this a real pattern, not coincidence"
        }}]

        Only report patterns where:
        - At least 2-3 violations share the same specific issue
        - There's a clear time, location, or cause pattern
        - It's actionable (not just random findings)

        Return empty array [] if no meaningful patterns found.
        """

        patterns = await self.generate_structured_response(prompt)

        if not isinstance(patterns, list):
            return []

        for pattern_data in patterns:
            pattern_id = str(uuid.uuid4())

            for violation_id in pattern_data.get("violation_ids", []):
                result = await db.execute(
                    select(Violation).where(Violation.id == violation_id)
                )
                violation = result.scalar_one_or_none()
                if violation:
                    violation.pattern_group_id = pattern_id

            violation_ids = pattern_data.get("violation_ids", [])
            first_violation = await db.execute(
                select(Violation)
                .where(Violation.id.in_(violation_ids))
                .order_by(Violation.received_at.asc())
                .limit(1)
            )
            last_violation = await db.execute(
                select(Violation)
                .where(Violation.id.in_(violation_ids))
                .order_by(Violation.received_at.desc())
                .limit(1)
            )

            first = first_violation.scalar_one_or_none()
            last = last_violation.scalar_one_or_none()

            if first and last:
                pattern = ViolationPattern(
                    pattern_id=pattern_id,
                    pattern_type=pattern_data["pattern_type"],
                    description=pattern_data["description"],
                    severity=pattern_data["severity"],
                    violation_count=len(violation_ids),
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
        violation: Violation
    ) -> str:
        """Draft an acknowledgment response for a violation"""

        site_name = "Unknown"
        if violation.site_id:
            result = await db.execute(select(Site).where(Site.id == violation.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name

        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in violation.violation_text)
        language = "Hebrew" if has_hebrew else "English"

        prompt = f"""
        Draft an acknowledgment email for this inspection finding:

        VIOLATION: {violation.violation_text}
        SITE: {site_name}
        AI ANALYSIS: {violation.ai_summary}
        SUGGESTED ACTION: {violation.ai_suggested_action}
        SEVERITY: {violation.severity.value if violation.severity else 'unknown'}

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
        """Generate weekly summary of violations for dashboard"""

        week_ago = datetime.utcnow() - timedelta(days=7)

        result = await db.execute(
            select(Violation).where(Violation.received_at >= week_ago)
        )
        violations = result.scalars().all()

        patterns_result = await db.execute(
            select(ViolationPattern)
            .where(
                and_(
                    ViolationPattern.is_active == True,
                    ViolationPattern.last_occurrence >= week_ago
                )
            )
        )
        patterns = patterns_result.scalars().all()

        category_counts = {}
        for v in violations:
            if v.category:
                cat = v.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1

        severity_counts = {}
        for v in violations:
            if v.severity:
                sev = v.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        responded = len([v for v in violations if v.acknowledged_at])
        response_rate = (responded / len(violations) * 100) if violations else 0

        resolved = [v for v in violations if v.resolved_at and v.received_at]
        if resolved:
            avg_resolution_hours = sum(
                (v.resolved_at - v.received_at).total_seconds() / 3600
                for v in resolved
            ) / len(resolved)
        else:
            avg_resolution_hours = 0

        return {
            "total_violations": len(violations),
            "by_category": category_counts,
            "by_severity": severity_counts,
            "active_patterns": len(patterns),
            "response_rate": round(response_rate, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "critical_count": severity_counts.get("critical", 0),
            "high_count": severity_counts.get("high", 0)
        }

    def _get_system_prompt(self) -> str:
        """System prompt for violation analysis"""
        return (
            "You are an AI assistant helping Ziv Reshef-Simchoni, "
            "the Food Service Manager at HP Israel.\n\n"
            "Your role is to analyze inspection findings (violations and exceptions) "
            "from professional inspectors visiting HP catering facilities, "
            "and provide actionable insights.\n\n"
            "Context:\n"
            "- Ziv manages catering across two sites: Nes Ziona and Kiryat Gat\n"
            "- Each site has a Meat restaurant and a Dairy restaurant\n"
            "- He works with vendors (Foodhouse, L.Eshel, etc.) who provide meals\n"
            "- Professional inspectors visit kitchens and dining rooms to report findings\n"
            "- Common issues: kitchen cleanliness, dining room cleanliness, staff attire, "
            "missing equipment, portion weight, menu variety, depleted main courses, "
            "staff shortage, service quality\n"
            "- Ziv values specific, actionable recommendations over vague advice\n\n"
            "When analyzing violations:\n"
            "- Be specific about root causes\n"
            "- Suggest concrete actions Ziv can take\n"
            "- Consider if it's a vendor issue, equipment issue, or process issue\n"
            "- Note if it's part of a larger pattern\n"
            "- Be professional and factual"
        )

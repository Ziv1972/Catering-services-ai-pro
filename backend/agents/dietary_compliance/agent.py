"""
Dietary Compliance Agent
Validates menu compliance with dietary requirements and regulations
"""
from backend.agents.base_agent import BaseAgent
from backend.models.menu_compliance import MenuCheck, CheckResult
from backend.models.site import Site
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List
import json


class DietaryComplianceAgent(BaseAgent):
    """Validates menus against dietary requirements and kosher regulations"""

    def __init__(self):
        super().__init__(name="DietaryComplianceAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action", "check_menu")
        db = context["db"]

        if action == "check_menu":
            menu_text = context.get("menu_text", "")
            site_id = context.get("site_id")
            return await self.check_menu_compliance(db, menu_text, site_id)
        elif action == "summary":
            return await self.get_compliance_summary(db)

        return {"error": f"Unknown action: {action}"}

    async def check_menu_compliance(
        self,
        db: AsyncSession,
        menu_text: str,
        site_id: int | None = None,
    ) -> Dict[str, Any]:
        """Check a menu against dietary compliance rules"""
        site_name = "Unknown"
        if site_id:
            result = await db.execute(select(Site).where(Site.id == site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name

        prompt = f"""
        Check this catering menu for dietary compliance at HP Israel ({site_name}):

        MENU:
        {menu_text}

        RULES TO CHECK:
        1. Kosher separation (meat/dairy) - no mixing in same meal
        2. Vegetarian option available at every meal
        3. Allergen labeling present (gluten, nuts, dairy, eggs)
        4. Caloric variety (not all heavy/light meals)
        5. Fresh fruit/vegetables included daily
        6. No repeated main dishes within same week
        7. Cultural diversity in menu offerings
        8. Portion sizes appropriate

        Return JSON:
        {{
            "overall_status": "pass|warning|fail",
            "score": 0-100,
            "findings": [
                {{
                    "rule": "rule name",
                    "status": "pass|warning|fail",
                    "severity": "low|medium|high|critical",
                    "finding": "what was found",
                    "recommendation": "how to fix"
                }}
            ],
            "summary": "1-2 sentence overall assessment"
        }}
        """

        analysis = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"compliance_check": analysis, "site": site_name}

    async def get_compliance_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get overall compliance summary from existing checks"""
        result = await db.execute(
            select(MenuCheck).order_by(MenuCheck.check_date.desc()).limit(10)
        )
        checks = result.scalars().all()

        if not checks:
            return {"summary": "No compliance checks on record."}

        checks_data = []
        for check in checks:
            results_q = await db.execute(
                select(CheckResult).where(CheckResult.menu_check_id == check.id)
            )
            findings = results_q.scalars().all()

            critical = sum(1 for f in findings if f.severity == "critical")
            warnings = sum(1 for f in findings if f.severity in ("high", "medium"))
            passed = sum(1 for f in findings if f.passed)

            checks_data.append({
                "id": check.id,
                "date": check.check_date.isoformat() if check.check_date else None,
                "site_id": check.site_id,
                "critical": critical,
                "warnings": warnings,
                "passed": passed,
                "total_rules": len(findings),
            })

        return {
            "recent_checks": checks_data,
            "total_checks": len(checks),
        }

    def _get_system_prompt(self) -> str:
        return (
            "You are a dietary compliance specialist for HP Israel catering.\n\n"
            "Your role is to validate menus against health regulations, "
            "kosher requirements, and company dietary policies.\n\n"
            "Context:\n"
            "- Israeli workplace catering must follow kashrut (kosher) rules\n"
            "- Meat and dairy must never be served in the same meal\n"
            "- Vegetarian and allergen-friendly options are mandatory\n"
            "- All ingredients must be labeled for common allergens\n"
            "- Menus should have variety across the week\n\n"
            "Be strict on kosher and allergen rules, moderate on variety."
        )

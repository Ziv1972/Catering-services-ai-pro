"""
Budget Intelligence Agent
Analyzes spending patterns, forecasts budgets, detects cost anomalies
"""
from backend.agents.base_agent import BaseAgent
from backend.models.proforma import Proforma, ProformaItem
from backend.models.site import Site
from backend.models.operations import Anomaly
from backend.models.historical_data import HistoricalMealData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
from typing import Dict, Any, List
import json


class BudgetIntelligenceAgent(BaseAgent):
    """Analyzes spending, forecasts budgets, and flags cost anomalies"""

    def __init__(self):
        super().__init__(name="BudgetIntelligenceAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action", "analyze_spending")
        db = context["db"]

        if action == "analyze_spending":
            months = context.get("months", 6)
            return await self.analyze_spending(db, months)
        elif action == "forecast":
            site_id = context.get("site_id")
            return await self.forecast_budget(db, site_id)
        elif action == "detect_anomalies":
            return await self.detect_cost_anomalies(db)

        return {"error": f"Unknown action: {action}"}

    async def analyze_spending(
        self, db: AsyncSession, months: int = 6
    ) -> Dict[str, Any]:
        """Analyze spending patterns across vendors and sites"""
        cutoff = date.today() - timedelta(days=months * 30)

        result = await db.execute(
            select(Proforma).where(Proforma.invoice_date >= cutoff)
        )
        proformas = result.scalars().all()

        if not proformas:
            return {"summary": "No proforma data available for analysis."}

        monthly_totals: Dict[str, float] = {}
        for p in proformas:
            key = p.invoice_date.strftime("%Y-%m")
            monthly_totals[key] = monthly_totals.get(key, 0) + p.total_amount

        total = sum(monthly_totals.values())
        avg_monthly = total / len(monthly_totals) if monthly_totals else 0

        sites_result = await db.execute(select(Site))
        sites = {s.id: s for s in sites_result.scalars().all()}

        prompt = f"""
        Analyze spending data for HP Israel catering:

        MONTHLY TOTALS (last {months} months):
        {json.dumps(dict(sorted(monthly_totals.items())), indent=2)}

        TOTAL SPEND: {total:,.2f} ILS
        AVG MONTHLY: {avg_monthly:,.2f} ILS
        SITES: {', '.join(s.name for s in sites.values())}

        Provide analysis as JSON:
        {{
            "trend": "increasing|stable|decreasing",
            "trend_summary": "1-2 sentence trend description",
            "month_over_month_change_pct": number,
            "risk_areas": ["list of areas with budget risk"],
            "savings_opportunities": ["specific actionable savings ideas"],
            "forecast_next_month": estimated amount
        }}
        """

        analysis = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {
            "spending_data": dict(sorted(monthly_totals.items())),
            "total": round(total, 2),
            "avg_monthly": round(avg_monthly, 2),
            "ai_analysis": analysis,
        }

    async def forecast_budget(
        self, db: AsyncSession, site_id: int | None = None
    ) -> Dict[str, Any]:
        """Forecast next month budget based on historical data"""
        cutoff = date.today() - timedelta(days=180)

        query = select(
            func.strftime("%Y-%m", HistoricalMealData.date).label("month"),
            func.sum(HistoricalMealData.cost).label("total_cost"),
            func.sum(HistoricalMealData.meal_count).label("total_meals"),
        ).where(HistoricalMealData.date >= cutoff.isoformat())

        if site_id:
            query = query.where(HistoricalMealData.site_id == site_id)

        query = query.group_by("month").order_by("month")

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return {"forecast": "Insufficient data for forecasting."}

        historical = [
            {"month": r.month, "cost": float(r.total_cost or 0), "meals": int(r.total_meals or 0)}
            for r in rows
        ]

        prompt = f"""
        Forecast next month's catering budget for HP Israel:

        HISTORICAL DATA:
        {json.dumps(historical, indent=2)}

        Return JSON:
        {{
            "forecast_cost": estimated total cost,
            "forecast_meals": estimated meal count,
            "forecast_cost_per_meal": estimated cost per meal,
            "confidence": "high|medium|low",
            "reasoning": "brief explanation of methodology",
            "risks": ["factors that could change forecast"]
        }}
        """

        forecast = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"historical": historical, "forecast": forecast}

    async def detect_cost_anomalies(self, db: AsyncSession) -> Dict[str, Any]:
        """Detect price anomalies in recent proformas"""
        cutoff = date.today() - timedelta(days=90)

        result = await db.execute(
            select(ProformaItem)
            .join(Proforma)
            .where(Proforma.invoice_date >= cutoff)
        )
        items = result.scalars().all()

        product_prices: Dict[str, List[float]] = {}
        for item in items:
            name = item.product_name
            if name not in product_prices:
                product_prices[name] = []
            product_prices[name].append(item.unit_price)

        flagged = []
        for name, prices in product_prices.items():
            if len(prices) < 2:
                continue
            avg = sum(prices) / len(prices)
            latest = prices[-1]
            if avg > 0:
                variance = ((latest - avg) / avg) * 100
                if abs(variance) > 15:
                    flagged.append({
                        "product": name,
                        "avg_price": round(avg, 2),
                        "latest_price": round(latest, 2),
                        "variance_pct": round(variance, 1),
                    })

        return {
            "products_analyzed": len(product_prices),
            "anomalies_found": len(flagged),
            "flagged_items": flagged,
        }

    def _get_system_prompt(self) -> str:
        return (
            "You are a budget intelligence assistant for Ziv Reshef-Simchoni, "
            "Food Service Manager at HP Israel.\n\n"
            "Your role is to analyze catering spending data and provide "
            "actionable budget insights.\n\n"
            "Context:\n"
            "- Manages catering across Nes Ziona and Kiryat Gat sites\n"
            "- Works with multiple vendors (Foodhouse, L.Eshel, etc.)\n"
            "- Budget is tracked per site with monthly limits\n"
            "- Currency is ILS (Israeli Shekel)\n\n"
            "Focus on: trends, anomalies, savings opportunities, and forecasting."
        )

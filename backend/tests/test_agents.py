"""
Agent unit tests - test agent methods with mocked Claude responses.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, date, timedelta

from backend.agents.meeting_prep.agent import MeetingPrepAgent
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent
from backend.agents.budget_intelligence.agent import BudgetIntelligenceAgent
from backend.agents.event_coordination.agent import EventCoordinationAgent
from backend.agents.dietary_compliance.agent import DietaryComplianceAgent
from backend.agents.communication_hub.agent import CommunicationHubAgent
from backend.agents.orchestrator import AgentOrchestrator

from backend.models.complaint import Complaint, ComplaintSource, ComplaintStatus
from backend.models.meeting import Meeting, MeetingType
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.models.historical_data import HistoricalMealData
from backend.models.operations import Anomaly


# ===================== ORCHESTRATOR =====================


class TestOrchestrator:

    def test_all_agents_registered(self):
        orch = AgentOrchestrator()
        agents = orch.list_agents()
        assert "meeting_prep" in agents
        assert "complaint_intelligence" in agents
        assert "budget_intelligence" in agents
        assert "event_coordination" in agents
        assert "dietary_compliance" in agents
        assert "communication_hub" in agents
        assert len(agents) == 6

    @pytest.mark.asyncio
    async def test_route_unknown_agent(self):
        orch = AgentOrchestrator()
        with pytest.raises(ValueError, match="Unknown agent"):
            await orch.route("nonexistent", {})


# ===================== COMPLAINT INTELLIGENCE =====================


class TestComplaintAgent:

    @pytest.mark.asyncio
    async def test_analyze_complaint(self, db_session, seed_data):
        agent = ComplaintIntelligenceAgent()

        mock_response = {
            "category": "food_quality",
            "severity": "high",
            "sentiment_score": -0.7,
            "summary": "Cold food complaint",
            "root_cause": "Serving temperature not maintained",
            "suggested_action": "Check food warmers",
            "urgency": "today",
            "requires_vendor_action": True,
            "time_pattern": "lunch",
        }

        complaint = Complaint(
            complaint_text="The chicken was ice cold at lunch today",
            source=ComplaintSource.MANUAL,
            received_at=datetime.utcnow(),
            site_id=seed_data["nz"].id,
        )
        db_session.add(complaint)
        await db_session.commit()

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await agent.analyze_complaint(db_session, complaint)

        assert result["category"] == "food_quality"
        assert result["severity"] == "high"
        assert complaint.ai_summary == "Cold food complaint"

    @pytest.mark.asyncio
    async def test_draft_acknowledgment(self, db_session, seed_data):
        agent = ComplaintIntelligenceAgent()

        complaint = Complaint(
            complaint_text="No vegan options available",
            source=ComplaintSource.EMAIL,
            received_at=datetime.utcnow(),
            ai_summary="Missing vegan options",
            ai_suggested_action="Add vegan menu items",
        )
        db_session.add(complaint)
        await db_session.commit()

        with patch.object(agent, "generate_response", new_callable=AsyncMock) as mock:
            mock.return_value = "Thank you for your feedback about vegan options."
            draft = await agent.draft_acknowledgment(db_session, complaint)

        assert "vegan" in draft.lower()

    @pytest.mark.asyncio
    async def test_weekly_summary(self, db_session, seed_data):
        agent = ComplaintIntelligenceAgent()

        for i in range(3):
            c = Complaint(
                complaint_text=f"Test complaint {i}",
                source=ComplaintSource.MANUAL,
                received_at=datetime.utcnow() - timedelta(days=i),
                status=ComplaintStatus.NEW,
            )
            db_session.add(c)
        await db_session.commit()

        summary = await agent.generate_weekly_summary(db_session)
        assert summary["total_complaints"] == 3


# ===================== BUDGET INTELLIGENCE =====================


class TestBudgetAgent:

    @pytest.mark.asyncio
    async def test_detect_cost_anomalies(self, db_session, seed_data):
        agent = BudgetIntelligenceAgent()

        s = Supplier(name="BudgetVendor", email="b@test.com")
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        for i in range(3):
            p = Proforma(
                supplier_id=s.id,
                invoice_date=date.today() - timedelta(days=30 * i),
                total_amount=5000,
                currency="ILS",
                status="paid",
            )
            db_session.add(p)
            await db_session.commit()
            await db_session.refresh(p)

            item = ProformaItem(
                proforma_id=p.id,
                product_name="Chicken",
                quantity=100,
                unit="kg",
                unit_price=30 if i > 0 else 45,  # spike on latest
                total_price=3000 if i > 0 else 4500,
                flagged=False,
            )
            db_session.add(item)
        await db_session.commit()

        result = await agent.detect_cost_anomalies(db_session)
        assert result["products_analyzed"] >= 1

    @pytest.mark.asyncio
    async def test_analyze_spending(self, db_session, seed_data):
        agent = BudgetIntelligenceAgent()

        s = Supplier(name="SpendAnalysis", email="sa@test.com")
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        p = Proforma(
            supplier_id=s.id,
            invoice_date=date.today(),
            total_amount=10000,
            currency="ILS",
            status="paid",
        )
        db_session.add(p)
        await db_session.commit()

        mock_analysis = {
            "trend": "stable",
            "trend_summary": "Spending is stable",
            "month_over_month_change_pct": 2.0,
            "risk_areas": [],
            "savings_opportunities": ["Bulk ordering"],
            "forecast_next_month": 10200,
        }

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_analysis
            result = await agent.analyze_spending(db_session, months=6)

        assert result["total"] > 0
        assert result["ai_analysis"]["trend"] == "stable"


# ===================== EVENT COORDINATION =====================


class TestEventAgent:

    @pytest.mark.asyncio
    async def test_get_upcoming_events(self, db_session, seed_data):
        agent = EventCoordinationAgent()

        m = Meeting(
            title="Vendor Review",
            meeting_type=MeetingType.VENDOR,
            scheduled_at=datetime.utcnow() + timedelta(days=3),
            duration_minutes=90,
        )
        db_session.add(m)
        await db_session.commit()

        result = await agent.get_upcoming_events(db_session, days=14)
        assert len(result["upcoming_events"]) >= 1
        assert result["events_needing_catering"] >= 1

    @pytest.mark.asyncio
    async def test_suggest_event_menu(self):
        agent = EventCoordinationAgent()

        mock_menu = {
            "menu": [{"item": "Sandwiches", "quantity": "40", "estimated_cost": 800, "dietary_info": "kosher"}],
            "total_estimated_cost": 800,
            "per_person_cost": 40,
            "notes": "All kosher",
        }

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_menu
            result = await agent.suggest_event_menu("meeting", 20)

        assert result["suggested_menu"]["total_estimated_cost"] == 800


# ===================== DIETARY COMPLIANCE =====================


class TestDietaryAgent:

    @pytest.mark.asyncio
    async def test_check_menu_compliance(self, db_session, seed_data):
        agent = DietaryComplianceAgent()

        mock_result = {
            "overall_status": "warning",
            "score": 75,
            "findings": [
                {
                    "rule": "Vegetarian option",
                    "status": "pass",
                    "severity": "low",
                    "finding": "Vegetarian option present",
                    "recommendation": "None needed",
                }
            ],
            "summary": "Menu mostly compliant with one issue",
        }

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_result
            result = await agent.check_menu_compliance(
                db_session,
                "Monday: Chicken Schnitzel, Rice, Salad\nTuesday: Beef Stew, Couscous",
                site_id=seed_data["nz"].id,
            )

        assert result["compliance_check"]["score"] == 75
        assert result["site"] == "Nes Ziona"


# ===================== COMMUNICATION HUB =====================


class TestCommunicationAgent:

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self, db_session, seed_data):
        agent = CommunicationHubAgent()

        mock_report = {
            "subject": "Weekly Catering Report",
            "summary": "Stable week with no major issues.",
            "highlights": ["100% resolution rate"],
            "concerns": [],
            "action_items": ["Review vendor contract"],
            "metrics_snapshot": {"complaints": 0, "meetings": 0, "anomalies": 0, "spend_ils": 0},
        }

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_report
            result = await agent.generate_weekly_report(db_session)

        assert "weekly_report" in result
        assert result["weekly_report"]["subject"] == "Weekly Catering Report"

    @pytest.mark.asyncio
    async def test_draft_vendor_email(self):
        agent = CommunicationHubAgent()

        mock_email = {
            "subject": "Service Quality Discussion",
            "body": "Dear Vendor, we need to discuss...",
            "tone": "firm",
            "follow_up_needed": True,
            "follow_up_date": "2026-03-01",
        }

        with patch.object(agent, "generate_structured_response", new_callable=AsyncMock) as mock:
            mock.return_value = mock_email
            result = await agent.draft_vendor_email(
                "Foodhouse", "quality concerns", {"details": "Cold food issues"}
            )

        assert result["draft_email"]["tone"] == "firm"

"""
Event Coordination Agent
Manages special events, coordinates catering for meetings and occasions
"""
from backend.agents.base_agent import BaseAgent
from backend.models.meeting import Meeting
from backend.models.site import Site
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json


class EventCoordinationAgent(BaseAgent):
    """Coordinates catering for events, meetings, and special occasions"""

    def __init__(self):
        super().__init__(name="EventCoordinationAgent")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action", "plan_event")
        db = context["db"]

        if action == "plan_event":
            event_details = context.get("event_details", {})
            return await self.plan_event_catering(db, event_details)
        elif action == "upcoming_events":
            days = context.get("days", 14)
            return await self.get_upcoming_events(db, days)
        elif action == "suggest_menu":
            event_type = context.get("event_type", "meeting")
            headcount = context.get("headcount", 20)
            return await self.suggest_event_menu(event_type, headcount)

        return {"error": f"Unknown action: {action}"}

    async def plan_event_catering(
        self, db: AsyncSession, event_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Plan catering for a specific event"""
        prompt = f"""
        Plan catering for this HP Israel event:

        EVENT DETAILS:
        {json.dumps(event_details, indent=2, default=str)}

        Provide a catering plan as JSON:
        {{
            "menu_suggestions": [
                {{
                    "item": "dish name",
                    "type": "main|side|drink|dessert",
                    "dietary_notes": "kosher, vegetarian, etc.",
                    "estimated_cost_per_person": number
                }}
            ],
            "logistics": {{
                "setup_time_minutes": number,
                "staff_needed": number,
                "equipment": ["items needed"]
            }},
            "estimated_total_cost": number,
            "vendor_recommendation": "which vendor to use and why",
            "special_considerations": ["list of things to watch for"]
        }}
        """

        plan = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"event_plan": plan}

    async def get_upcoming_events(
        self, db: AsyncSession, days: int = 14
    ) -> Dict[str, Any]:
        """Get upcoming events that need catering coordination"""
        cutoff = datetime.utcnow() + timedelta(days=days)

        result = await db.execute(
            select(Meeting)
            .where(Meeting.scheduled_at >= datetime.utcnow())
            .where(Meeting.scheduled_at <= cutoff)
            .order_by(Meeting.scheduled_at.asc())
        )
        meetings = result.scalars().all()

        events = []
        for m in meetings:
            events.append({
                "id": m.id,
                "title": m.title,
                "date": m.scheduled_at.isoformat(),
                "duration_minutes": m.duration_minutes,
                "type": m.meeting_type.value if m.meeting_type else "other",
                "site_id": m.site_id,
                "needs_catering": m.duration_minutes >= 60,
            })

        return {
            "upcoming_events": events,
            "events_needing_catering": sum(1 for e in events if e["needs_catering"]),
        }

    async def suggest_event_menu(
        self, event_type: str, headcount: int
    ) -> Dict[str, Any]:
        """Suggest a menu for a given event type and headcount"""
        prompt = f"""
        Suggest a catering menu for an HP Israel event:

        EVENT TYPE: {event_type}
        HEADCOUNT: {headcount}

        Return JSON:
        {{
            "menu": [
                {{
                    "item": "dish name",
                    "quantity": "amount for {headcount} people",
                    "estimated_cost": number in ILS,
                    "dietary_info": "kosher, vegetarian, etc."
                }}
            ],
            "total_estimated_cost": number,
            "per_person_cost": number,
            "notes": "any special considerations"
        }}

        Remember: All food must be kosher. Include vegetarian options.
        """

        menu = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )

        return {"suggested_menu": menu}

    def _get_system_prompt(self) -> str:
        return (
            "You are an event coordination assistant for HP Israel catering.\n\n"
            "Your role is to help plan catering for meetings, events, "
            "and special occasions at HP Israel sites.\n\n"
            "Context:\n"
            "- Two main sites: Nes Ziona and Kiryat Gat\n"
            "- All food must follow kosher (kashrut) rules\n"
            "- Common event types: team meetings, HP management visits, "
            "vendor reviews, holiday celebrations\n"
            "- Budget-conscious but quality-focused\n"
            "- Vendors: Foodhouse, L.Eshel, and others\n\n"
            "Provide practical, cost-effective catering suggestions."
        )

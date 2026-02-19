"""
Meeting Prep Agent - Generates comprehensive meeting briefs
"""
from backend.agents.base_agent import BaseAgent
from backend.agents.meeting_prep.prompts import (
    SYSTEM_PROMPT,
    MEETING_BRIEF_PROMPT,
    MEETING_BRIEF_RESPONSE_FORMAT
)
from backend.agents.meeting_prep.data_gatherer import MeetingDataGatherer
from backend.models.meeting import Meeting
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import json


class MeetingPrepAgent(BaseAgent):
    """
    Prepares comprehensive briefs for upcoming meetings
    """

    def __init__(self):
        super().__init__(name="MeetingPrepAgent")
        self.data_gatherer = MeetingDataGatherer()

    async def prepare_meeting_brief(
        self,
        db: AsyncSession,
        meeting: Meeting
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive meeting brief
        """
        # Gather context
        context = await self.data_gatherer.gather_context(db, meeting)

        # Format prompt
        prompt = MEETING_BRIEF_PROMPT.format(
            meeting_title=context["meeting_info"]["title"],
            meeting_type=context["meeting_info"]["type"],
            scheduled_at=context["meeting_info"]["scheduled_at"],
            duration_minutes=context["meeting_info"]["duration_minutes"],
            site_name=context["meeting_info"]["site"],
            context_data=json.dumps(context, indent=2, ensure_ascii=False)
        )

        # Generate brief using Claude
        brief = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            response_format=MEETING_BRIEF_RESPONSE_FORMAT
        )

        # Save brief to meeting
        meeting.ai_brief = json.dumps(brief, ensure_ascii=False)
        meeting.ai_agenda = self._format_agenda(brief)

        return brief

    def _format_agenda(self, brief: Dict[str, Any]) -> str:
        """Format the brief into a readable agenda"""
        agenda_parts = ["# Meeting Agenda\n"]

        # Priority Topics
        agenda_parts.append("## Priority Topics\n")
        for i, topic in enumerate(brief.get("priority_topics", []), 1):
            agenda_parts.append(f"{i}. **{topic['title']}** ({topic['urgency']})")
            agenda_parts.append(f"   - {topic['description']}\n")

        # Follow-ups
        if brief.get("follow_ups"):
            agenda_parts.append("\n## Follow-up from Last Meeting\n")
            for followup in brief["follow_ups"]:
                status_icon = "✅" if followup["status"] == "completed" else "⏳"
                agenda_parts.append(f"- {status_icon} {followup['item']}")

        # Questions
        if brief.get("questions_to_ask"):
            agenda_parts.append("\n## Key Questions\n")
            for question in brief["questions_to_ask"]:
                agenda_parts.append(f"- {question}")

        return "\n".join(agenda_parts)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of BaseAgent.process"""
        db = context["db"]
        meeting = context["meeting"]
        return await self.prepare_meeting_brief(db, meeting)

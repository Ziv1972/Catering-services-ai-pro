"""
Agent Orchestrator - Routes requests to specialist agents
"""
from typing import Dict, Any
from backend.agents.meeting_prep.agent import MeetingPrepAgent


class AgentOrchestrator:
    """
    Routes incoming requests to the appropriate specialist agent
    """

    def __init__(self):
        self.agents = {
            "meeting_prep": MeetingPrepAgent(),
            # Future agents:
            # "complaint_intelligence": ComplaintIntelligenceAgent(),
            # "budget_intelligence": BudgetIntelligenceAgent(),
            # "event_coordination": EventCoordinationAgent(),
            # "dietary_compliance": DietaryComplianceAgent(),
            # "communication_hub": CommunicationHubAgent(),
        }

    async def route(self, agent_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a request to the appropriate agent

        Args:
            agent_name: Name of the target agent
            context: Context data for the agent

        Returns:
            Agent response

        Raises:
            ValueError: If agent_name is not recognized
        """
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}. Available: {list(self.agents.keys())}")

        return await agent.process(context)

    def list_agents(self) -> list[str]:
        """List all available agents"""
        return list(self.agents.keys())


orchestrator = AgentOrchestrator()

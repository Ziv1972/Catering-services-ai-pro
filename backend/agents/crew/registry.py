"""
Agent_crew - Catering AI Pro
Agent registry: maps role IDs to their agent class instances.
Bridges the crew system to the existing BaseAgent-based agents.
"""
from typing import Any
from backend.agents.crew.roles import ALL_ROLES, SPECIALIST_ROLES, AgentRole
from backend.agents.crew.models import AgentStatus


class AgentEntry:
    """Wraps an existing BaseAgent with its crew role metadata."""

    def __init__(self, role: AgentRole, agent_instance: Any):
        self.role = role
        self.agent = agent_instance
        self.status = AgentStatus.IDLE
        self.invocation_count = 0
        self.total_tokens = 0
        self.total_time_ms = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.role.id,
            "title": self.role.title,
            "goal": self.role.goal,
            "backstory": self.role.backstory,
            "responsibilities": list(self.role.responsibilities),
            "tools": list(self.role.tools),
            "interacts_with": list(self.role.interacts_with),
            "icon": self.role.icon,
            "color": self.role.color,
            "status": self.status.value,
            "stats": {
                "invocations": self.invocation_count,
                "total_tokens": self.total_tokens,
                "total_time_ms": self.total_time_ms,
                "avg_time_ms": (
                    round(self.total_time_ms / self.invocation_count)
                    if self.invocation_count > 0 else 0
                ),
            },
        }


class AgentRegistry:
    """
    Central registry for all crew agents.
    Lazily instantiates agents on first access to avoid import loops.
    """

    def __init__(self):
        self._entries: dict[str, AgentEntry] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        from backend.agents.meeting_prep.agent import MeetingPrepAgent
        from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent
        from backend.agents.budget_intelligence.agent import BudgetIntelligenceAgent
        from backend.agents.event_coordination.agent import EventCoordinationAgent
        from backend.agents.dietary_compliance.agent import DietaryComplianceAgent
        from backend.agents.communication_hub.agent import CommunicationHubAgent

        agent_map = {
            "data_analyst": BudgetIntelligenceAgent(),
            "menu_compliance": DietaryComplianceAgent(),
            "invoice_analyst": BudgetIntelligenceAgent(),
            "budget_intelligence": BudgetIntelligenceAgent(),
            "complaint_intelligence": ComplaintIntelligenceAgent(),
            "daily_ops_monitor": BudgetIntelligenceAgent(),
            "supplier_manager": BudgetIntelligenceAgent(),
            "event_coordinator": EventCoordinationAgent(),
            "communication_hub": CommunicationHubAgent(),
        }

        for role_id, role in SPECIALIST_ROLES.items():
            agent_instance = agent_map.get(role_id)
            if agent_instance:
                self._entries[role_id] = AgentEntry(role=role, agent_instance=agent_instance)

        self._initialized = True

    def get(self, agent_id: str) -> AgentEntry | None:
        self._ensure_initialized()
        return self._entries.get(agent_id)

    def get_all(self) -> dict[str, AgentEntry]:
        self._ensure_initialized()
        return dict(self._entries)

    def get_specialist_ids(self) -> list[str]:
        self._ensure_initialized()
        return list(self._entries.keys())

    def get_role(self, agent_id: str) -> AgentRole | None:
        return ALL_ROLES.get(agent_id)

    def get_manager_role(self) -> AgentRole:
        return ALL_ROLES["operations_manager"]

    def list_all_roles(self) -> list[dict[str, Any]]:
        """Return all roles (including manager) for the UI."""
        self._ensure_initialized()
        roles = []

        manager_role = self.get_manager_role()
        roles.append({
            "id": manager_role.id,
            "title": manager_role.title,
            "goal": manager_role.goal,
            "backstory": manager_role.backstory,
            "responsibilities": list(manager_role.responsibilities),
            "tools": list(manager_role.tools),
            "interacts_with": list(manager_role.interacts_with),
            "icon": manager_role.icon,
            "color": manager_role.color,
            "status": "active",
            "is_manager": True,
            "stats": {"invocations": 0, "total_tokens": 0, "total_time_ms": 0, "avg_time_ms": 0},
        })

        for entry in self._entries.values():
            info = entry.to_dict()
            info["is_manager"] = False
            roles.append(info)

        return roles


agent_registry = AgentRegistry()

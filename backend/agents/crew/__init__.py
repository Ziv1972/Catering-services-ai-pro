"""
Agent_crew - Catering AI Pro
Full-stack crew of AI agents with a manager overseeing operations.
"""
from backend.agents.crew.manager import CrewManager
from backend.agents.crew.registry import agent_registry
from backend.agents.crew.session import CrewSession

__all__ = ["CrewManager", "agent_registry", "CrewSession"]

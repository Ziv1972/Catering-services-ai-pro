"""
Base class for all AI agents
"""
from abc import ABC, abstractmethod
from backend.services.claude_service import claude_service
from typing import Dict, Any, Optional


class BaseAgent(ABC):
    """
    Base class for all specialized agents in the system
    """

    def __init__(self, name: str):
        self.name = name
        self.claude = claude_service

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the given context and return results
        """
        pass

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Wrapper for Claude service"""
        return await self.claude.generate_response(prompt, system_prompt)

    async def generate_structured_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Wrapper for structured Claude responses"""
        return await self.claude.generate_structured_response(
            prompt, system_prompt, response_format
        )

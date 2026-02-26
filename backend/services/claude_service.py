"""
Claude API service wrapper
"""
from anthropic import AsyncAnthropic
from backend.config import get_settings
from typing import Optional, Dict, Any
import json

settings = get_settings()


class ClaudeService:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.CLAUDE_MAX_TOKENS

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response from Claude
        """
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=messages
        )

        return response.content[0].text

    async def generate_structured_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured JSON response from Claude
        """
        structured_prompt = f"""{prompt}

IMPORTANT: Respond with ONLY a valid JSON object matching this schema:
{json.dumps(response_format, indent=2)}

Do not include any markdown formatting, code blocks, or explanatory text.
Just return the raw JSON."""

        response_text = await self.generate_response(
            prompt=structured_prompt,
            system_prompt=system_prompt
        )

        # Clean up response (remove markdown if present)
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Claude response as JSON: {e}\n\nResponse: {response_text}")


# Singleton instance
claude_service = ClaudeService()

"""
Chat interface API - Natural language interaction with the AI system
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.api.auth import get_current_user
from backend.services.claude_service import claude_service

router = APIRouter()

CHAT_SYSTEM_PROMPT = """You are an AI assistant for Catering Services at HP Israel.
You help Ziv manage catering operations across Nes Ziona and Kiryat Gat sites.

You can help with:
- Meeting preparation and briefs
- Complaint tracking and analysis
- Budget questions and forecasting
- Event planning and coordination
- Dietary compliance queries
- General catering operations questions

Be concise, actionable, and data-driven. If you don't have specific data,
say so and suggest how to get it."""


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: list[str] = []


@router.post("/", response_model=ChatResponse)
async def chat(
    chat_message: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message to the AI assistant"""
    try:
        response = await claude_service.generate_response(
            prompt=chat_message.message,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )

        suggestions = [
            "Prepare brief for next meeting",
            "Show recent complaints",
            "Check budget status",
        ]

        return ChatResponse(response=response, suggestions=suggestions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

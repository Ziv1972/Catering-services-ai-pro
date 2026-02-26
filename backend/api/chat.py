"""
Chat interface API - Natural language interaction with the AI system
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import date, datetime

from backend.database import get_db
from backend.models.user import User
from backend.models.proforma import Proforma
from backend.models.supplier_budget import SupplierBudget
from backend.models.complaint import Complaint
from backend.models.meeting import Meeting
from backend.models.todo import TodoItem
from backend.api.auth import get_current_user
from backend.services.claude_service import claude_service

router = APIRouter()

CHAT_SYSTEM_PROMPT = """You are an AI assistant for Catering Services at HP Israel.
You help Ziv manage catering operations across Nes Ziona (NZ) and Kiryat Gat (KG) sites.

You can help with:
- Meeting preparation and briefs
- Complaint tracking and analysis
- Budget questions and forecasting
- Event planning and coordination
- Dietary compliance queries
- General catering operations questions

Be concise, actionable, and data-driven. When provided with live data context,
reference specific numbers. Respond in the same language as the user's message
(Hebrew or English)."""


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: list[str] = []


async def _build_context(db: AsyncSession, user: User) -> str:
    """Build live data context for the AI from the database."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    today = date.today()

    context_parts = []

    try:
        # Budget summary
        budget_result = await db.execute(
            select(SupplierBudget)
            .where(SupplierBudget.year == current_year, SupplierBudget.is_active == True)
        )
        budgets = budget_result.scalars().all()
        if budgets:
            month_cols = ["jan", "feb", "mar", "apr", "may", "jun",
                          "jul", "aug", "sep", "oct", "nov", "dec"]
            month_col = month_cols[current_month - 1]
            total_monthly_budget = sum(getattr(b, month_col) or 0 for b in budgets)
            total_yearly_budget = sum(b.yearly_amount or 0 for b in budgets)
            context_parts.append(
                f"Budget: {len(budgets)} supplier budgets for {current_year}. "
                f"Total monthly budget for {month_cols[current_month-1].title()}: "
                f"₪{total_monthly_budget:,.0f}. Yearly total: ₪{total_yearly_budget:,.0f}."
            )

        # Recent complaints
        complaint_result = await db.execute(
            select(func.count(Complaint.id))
            .where(Complaint.status != "resolved")
        )
        open_complaints = complaint_result.scalar() or 0
        if open_complaints > 0:
            context_parts.append(f"Open complaints: {open_complaints}")

        # Upcoming meetings
        meeting_result = await db.execute(
            select(func.count(Meeting.id))
            .where(Meeting.scheduled_at >= now)
        )
        upcoming = meeting_result.scalar() or 0
        if upcoming > 0:
            context_parts.append(f"Upcoming meetings: {upcoming}")

        # Open todos
        todo_result = await db.execute(
            select(func.count(TodoItem.id))
            .where(TodoItem.user_id == user.id, TodoItem.status != "done")
        )
        open_todos = todo_result.scalar() or 0
        overdue_result = await db.execute(
            select(func.count(TodoItem.id))
            .where(
                TodoItem.user_id == user.id,
                TodoItem.status != "done",
                TodoItem.due_date < today
            )
        )
        overdue = overdue_result.scalar() or 0
        if open_todos > 0:
            todo_text = f"Open tasks: {open_todos}"
            if overdue > 0:
                todo_text += f" ({overdue} overdue)"
            context_parts.append(todo_text)

        # Proforma spending this month
        proforma_result = await db.execute(
            select(func.count(Proforma.id), func.sum(Proforma.total_amount))
        )
        row = proforma_result.one()
        if row[0] and row[0] > 0:
            context_parts.append(
                f"Total proformas in system: {row[0]}, "
                f"total value: ₪{row[1]:,.0f}"
            )

    except Exception:
        pass

    if context_parts:
        return "\n\nLive data context:\n- " + "\n- ".join(context_parts)
    return ""


@router.post("/", response_model=ChatResponse)
async def chat(
    chat_message: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message to the AI assistant"""
    try:
        context = await _build_context(db, current_user)
        prompt = chat_message.message
        if context:
            prompt = f"{chat_message.message}\n{context}"

        response = await claude_service.generate_response(
            prompt=prompt,
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

"""
Agent_crew - Catering AI Pro
API endpoints for the crew system.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.api.auth import get_current_user
from backend.models import User

router = APIRouter(prefix="/api/agent-crew", tags=["Agent Crew"])


class CrewChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class SingleAgentRequest(BaseModel):
    agent_id: str
    action: str
    context: dict = {}


# ── Crew Info ──────────────────────────────────────────

@router.get("")
async def get_crew_info(
    current_user: User = Depends(get_current_user),
):
    """Get full crew metadata: all agents, roles, stats."""
    from backend.agents.crew.manager import crew_manager
    return crew_manager.get_crew_info()


# ── Crew Chat (Manager-orchestrated) ──────────────────

@router.post("/chat")
async def crew_chat(
    request: CrewChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the crew manager.
    The manager analyzes intent, delegates to specialists, and synthesizes.
    """
    from backend.agents.crew.manager import crew_manager
    try:
        result = await crew_manager.handle_request(
            user_message=request.message,
            db=db,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Direct Agent Invocation ───────────────────────────

@router.post("/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: SingleAgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a specific agent directly (bypass manager)."""
    from backend.agents.crew.manager import crew_manager
    result = await crew_manager.run_single_agent(
        agent_id=agent_id,
        action=request.action,
        context=request.context,
        db=db,
    )
    if "error" in result and result.get("status") != "completed":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Agent Details ─────────────────────────────────────

@router.get("/agents/{agent_id}")
async def get_agent_details(
    agent_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get detailed info about a specific agent."""
    from backend.agents.crew.registry import agent_registry
    from backend.agents.crew.roles import ALL_ROLES

    role = ALL_ROLES.get(agent_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    entry = agent_registry.get(agent_id)
    if entry:
        return entry.to_dict()

    # Manager role (no entry in registry)
    return {
        "id": role.id,
        "title": role.title,
        "goal": role.goal,
        "backstory": role.backstory,
        "responsibilities": list(role.responsibilities),
        "tools": list(role.tools),
        "interacts_with": list(role.interacts_with),
        "icon": role.icon,
        "color": role.color,
        "is_manager": role.id == "operations_manager",
    }


# ── Sessions ──────────────────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get session details and metrics."""
    from backend.agents.crew.manager import crew_manager
    session = crew_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── Agent Roles List ──────────────────────────────────

@router.get("/roles")
async def list_roles(
    current_user: User = Depends(get_current_user),
):
    """List all agent roles with their descriptions."""
    from backend.agents.crew.registry import agent_registry
    return {"roles": agent_registry.list_all_roles()}

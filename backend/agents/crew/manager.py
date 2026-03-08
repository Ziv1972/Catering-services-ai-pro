"""
Agent_crew - Catering AI Pro
CrewManager: The overseer agent that analyzes intent, delegates to specialists,
runs parallel fan-out, and synthesizes results.
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from backend.agents.crew.models import (
    AgentTask, AgentMessage, TaskPriority, TaskStatus, MessageType,
)
from backend.agents.crew.registry import agent_registry
from backend.agents.crew.roles import OPERATIONS_MANAGER, SPECIALIST_ROLES
from backend.agents.crew.session import CrewSession
from backend.services.claude_service import claude_service

logger = logging.getLogger(__name__)


class CrewManager:
    """
    The Operations Manager agent — overseer of the entire crew.

    - Analyzes user intent using Claude
    - Delegates to specialist agents (single or parallel)
    - Synthesizes multi-agent outputs
    - Handles escalation
    - Tracks session metrics
    """

    CREW_NAME = "Agent_crew - Catering AI Pro"
    MAX_PARALLEL_AGENTS = 4
    AGENT_TIMEOUT_SECONDS = 60

    def __init__(self):
        self.role = OPERATIONS_MANAGER
        self._sessions: dict[str, CrewSession] = {}

    # ── Public API ─────────────────────────────────────────

    async def handle_request(
        self,
        user_message: str,
        db: Any,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Main entry point. Analyze intent, delegate, synthesize.

        Returns:
            {
                "response": str,
                "agents_used": [str],
                "session": {...},
                "tasks": [...]
            }
        """
        session = self._get_or_create_session(session_id)

        # Step 1: Analyze intent — determine which agents to invoke
        task_plan = await self._analyze_intent(user_message, session)

        if not task_plan.get("agents"):
            return {
                "response": task_plan.get("direct_response", "I can help with that. Could you be more specific?"),
                "agents_used": [],
                "session": session.to_dict(),
                "tasks": [],
            }

        # Step 2: Create tasks for each agent
        tasks = self._create_tasks(task_plan, user_message, db)

        # Step 3: Execute — parallel if independent, sequential if dependent
        completed_tasks = await self._execute_tasks(tasks, db, session)

        # Step 4: Synthesize results
        response = await self._synthesize_results(
            user_message, completed_tasks, session
        )

        agents_used = list({t.agent_id for t in completed_tasks})

        return {
            "response": response,
            "agents_used": agents_used,
            "session": session.to_dict(),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "agent_id": t.agent_id,
                    "agent_title": SPECIALIST_ROLES.get(t.agent_id, OPERATIONS_MANAGER).title,
                    "objective": t.objective,
                    "status": t.status.value,
                    "execution_time_ms": t.execution_time_ms,
                    "result_summary": self._summarize_result(t.result) if t.result else t.error,
                }
                for t in completed_tasks
            ],
        }

    async def run_single_agent(
        self,
        agent_id: str,
        action: str,
        context: dict[str, Any],
        db: Any,
    ) -> dict[str, Any]:
        """Direct invocation of a single agent (bypasses intent analysis)."""
        entry = agent_registry.get(agent_id)
        if not entry:
            return {"error": f"Agent not found: {agent_id}"}

        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_id=agent_id,
            objective=action,
            context={**context, "action": action, "db": db},
        )

        completed = await self._execute_single_task(task, db)

        session = CrewSession()
        session.log_task(completed)

        return {
            "agent_id": agent_id,
            "agent_title": entry.role.title,
            "status": completed.status.value,
            "result": completed.result,
            "error": completed.error,
            "execution_time_ms": completed.execution_time_ms,
            "session": session.to_dict(),
        }

    def get_crew_info(self) -> dict[str, Any]:
        """Return full crew metadata for the dashboard."""
        return {
            "crew_name": self.CREW_NAME,
            "manager": {
                "id": self.role.id,
                "title": self.role.title,
                "goal": self.role.goal,
                "backstory": self.role.backstory,
                "responsibilities": list(self.role.responsibilities),
                "icon": self.role.icon,
                "color": self.role.color,
            },
            "agents": agent_registry.list_all_roles(),
            "total_agents": len(agent_registry.get_specialist_ids()) + 1,
            "active_sessions": len(self._sessions),
        }

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(session_id)
        return session.to_dict() if session else None

    # ── Intent Analysis ────────────────────────────────────

    async def _analyze_intent(
        self, user_message: str, session: CrewSession
    ) -> dict[str, Any]:
        """Use Claude to determine which agents to invoke."""
        agent_descriptions = "\n".join(
            f"- {role.id}: {role.title} — {role.goal}"
            for role in SPECIALIST_ROLES.values()
        )

        context_summary = ""
        if session.context:
            context_summary = f"\nPREVIOUS CONTEXT:\n{json.dumps(list(session.context.keys()))}"

        prompt = f"""
        You are the Operations Manager of "{self.CREW_NAME}".

        Analyze this request and determine which specialist agent(s) should handle it.

        AVAILABLE AGENTS:
        {agent_descriptions}

        USER REQUEST:
        {user_message}
        {context_summary}

        Return JSON:
        {{
            "agents": ["agent_id_1", "agent_id_2"],
            "tasks": [
                {{
                    "agent_id": "agent_id",
                    "objective": "what this agent should do",
                    "action": "the action parameter for the agent",
                    "priority": "critical|high|normal|low",
                    "depends_on": null or "agent_id it depends on"
                }}
            ],
            "parallel": true or false,
            "reasoning": "brief explanation of delegation decision"
        }}

        Rules:
        - Choose 1-4 agents maximum
        - Set parallel=true if agents can work independently
        - Set parallel=false if one agent's output feeds another
        - If the request is simple conversation not related to catering operations, return:
          {{"agents": [], "direct_response": "your helpful response"}}
        """

        system_prompt = (
            f"You are {self.role.title}. {self.role.backstory}\n\n"
            "Your job is ONLY to analyze and delegate. Never do the specialist work yourself."
        )

        try:
            plan = await claude_service.generate_structured_response(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            return plan
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return {
                "agents": [],
                "direct_response": "I encountered an issue analyzing your request. Please try again.",
            }

    # ── Task Creation ──────────────────────────────────────

    def _create_tasks(
        self, task_plan: dict[str, Any], user_message: str, db: Any
    ) -> list[AgentTask]:
        """Convert the AI-generated plan into executable tasks."""
        tasks = []
        for task_spec in task_plan.get("tasks", []):
            agent_id = task_spec.get("agent_id", "")
            if agent_id not in SPECIALIST_ROLES:
                continue

            priority_str = task_spec.get("priority", "normal")
            try:
                priority = TaskPriority(priority_str)
            except ValueError:
                priority = TaskPriority.NORMAL

            tasks.append(AgentTask(
                task_id=str(uuid.uuid4()),
                agent_id=agent_id,
                objective=task_spec.get("objective", user_message),
                context={
                    "action": task_spec.get("action", "analyze"),
                    "user_message": user_message,
                    "db": db,
                },
                priority=priority,
            ))

        return tasks

    # ── Task Execution ─────────────────────────────────────

    async def _execute_tasks(
        self,
        tasks: list[AgentTask],
        db: Any,
        session: CrewSession,
    ) -> list[AgentTask]:
        """Execute tasks — parallel or sequential based on dependencies."""
        if not tasks:
            return []

        # For now, run all tasks in parallel (fan-out pattern)
        completed = await asyncio.gather(
            *[self._execute_single_task(t, db) for t in tasks],
            return_exceptions=True,
        )

        results: list[AgentTask] = []
        for i, result in enumerate(completed):
            if isinstance(result, Exception):
                failed_task = tasks[i].fail(str(result))
                session.log_task(failed_task)
                results.append(failed_task)
            elif isinstance(result, AgentTask):
                session.log_task(result)
                results.append(result)

        return results

    async def _execute_single_task(
        self, task: AgentTask, db: Any
    ) -> AgentTask:
        """Execute a single agent task with error handling and metrics."""
        entry = agent_registry.get(task.agent_id)
        if not entry:
            return task.fail(f"Agent not found: {task.agent_id}")

        start_time = time.monotonic()

        try:
            context = {**task.context, "db": db}
            result = await asyncio.wait_for(
                entry.agent.process(context),
                timeout=self.AGENT_TIMEOUT_SECONDS,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Update registry stats
            entry.invocation_count += 1
            entry.total_time_ms += elapsed_ms

            return task.complete(
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning(f"Agent {task.agent_id} timed out after {elapsed_ms}ms")
            return task.fail(f"Agent timed out after {self.AGENT_TIMEOUT_SECONDS}s")

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Agent {task.agent_id} failed: {e}")
            entry.invocation_count += 1
            return task.fail(str(e))

    # ── Result Synthesis ───────────────────────────────────

    async def _synthesize_results(
        self,
        user_message: str,
        tasks: list[AgentTask],
        session: CrewSession,
    ) -> str:
        """Synthesize outputs from multiple agents into a unified response."""
        if not tasks:
            return "No agents were able to process your request."

        # Single agent — return its result directly as formatted text
        successful = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]

        if len(successful) == 1 and not failed:
            return self._format_single_result(successful[0])

        # Multiple agents — use Claude to synthesize
        agent_outputs = []
        for task in tasks:
            role = SPECIALIST_ROLES.get(task.agent_id)
            title = role.title if role else task.agent_id
            if task.status == TaskStatus.COMPLETED:
                agent_outputs.append(
                    f"[{title}] (SUCCESS, {task.execution_time_ms}ms):\n"
                    f"{json.dumps(task.result, indent=2, default=str)[:2000]}"
                )
            else:
                agent_outputs.append(
                    f"[{title}] (FAILED): {task.error}"
                )

        prompt = f"""
        You are the Operations Manager synthesizing outputs from your specialist agents.

        USER REQUEST: {user_message}

        AGENT OUTPUTS:
        {chr(10).join(agent_outputs)}

        Synthesize these into a clear, unified response for the user (Ziv).
        - Combine insights from all successful agents
        - Note any agents that failed and what was missed
        - Be concise but thorough
        - Use bullet points for key findings
        - End with recommended next actions

        Write in professional English. Return ONLY the response text (no JSON).
        """

        try:
            response = await claude_service.generate_response(
                prompt=prompt,
                system_prompt=f"You are {self.role.title}. {self.role.goal}",
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return self._fallback_synthesis(tasks)

    # ── Helpers ─────────────────────────────────────────────

    def _get_or_create_session(self, session_id: Optional[str]) -> CrewSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = CrewSession()
        self._sessions[session.session_id] = session
        return session

    def _format_single_result(self, task: AgentTask) -> str:
        """Format a single agent's result as readable text."""
        if not task.result:
            return "Task completed but returned no data."

        parts = []
        role = SPECIALIST_ROLES.get(task.agent_id)
        if role:
            parts.append(f"**{role.title}** completed in {task.execution_time_ms}ms:\n")

        result = task.result
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, dict):
                    parts.append(f"**{key.replace('_', ' ').title()}:**")
                    for k, v in value.items():
                        parts.append(f"  - {k}: {v}")
                elif isinstance(value, list):
                    parts.append(f"**{key.replace('_', ' ').title()}:** ({len(value)} items)")
                    for item in value[:5]:
                        if isinstance(item, dict):
                            summary = item.get("description") or item.get("summary") or item.get("name") or str(item)[:100]
                            parts.append(f"  - {summary}")
                        else:
                            parts.append(f"  - {item}")
                else:
                    parts.append(f"**{key.replace('_', ' ').title()}:** {value}")
        else:
            parts.append(str(result))

        return "\n".join(parts)

    def _fallback_synthesis(self, tasks: list[AgentTask]) -> str:
        """Fallback when Claude synthesis fails."""
        parts = ["Here are the results from the crew:\n"]
        for task in tasks:
            role = SPECIALIST_ROLES.get(task.agent_id)
            title = role.title if role else task.agent_id
            if task.status == TaskStatus.COMPLETED:
                parts.append(f"**{title}**: Completed ({task.execution_time_ms}ms)")
                if task.result:
                    summary = self._summarize_result(task.result)
                    parts.append(f"  {summary}")
            else:
                parts.append(f"**{title}**: Failed — {task.error}")
        return "\n".join(parts)

    def _summarize_result(self, result: Any) -> str:
        """Create a brief summary of an agent result."""
        if not result:
            return "No data"
        if isinstance(result, str):
            return result[:200]
        if isinstance(result, dict):
            keys = list(result.keys())[:5]
            return f"Keys: {', '.join(keys)}"
        return str(result)[:200]


# Singleton
crew_manager = CrewManager()

"""
Agent_crew - Catering AI Pro
Session management: shared context (blackboard), task log, metrics.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

from backend.agents.crew.models import (
    AgentTask, AgentMessage, CrewMetrics, TaskStatus, MessageType,
)


@dataclass
class CrewSession:
    """
    Maintains state for a single crew workflow.
    Implements the Blackboard pattern for inter-agent data sharing.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)
    context: dict[str, Any] = field(default_factory=dict)
    agent_results: dict[str, Any] = field(default_factory=dict)
    task_log: list[AgentTask] = field(default_factory=list)
    message_log: list[AgentMessage] = field(default_factory=list)
    status: str = "active"

    # ── Blackboard (shared state) ──────────────────────────

    def write_context(self, agent_id: str, key: str, value: Any) -> None:
        """Agent writes data to the shared blackboard."""
        self.context[key] = value
        self.message_log.append(AgentMessage(
            source_agent=agent_id,
            target_agent="blackboard",
            message_type=MessageType.DATA_SHARE,
            task_id="context_write",
            payload={"key": key, "summary": str(value)[:200]},
        ))

    def read_context(self, key: str, default: Any = None) -> Any:
        """Read a value from the shared blackboard."""
        return self.context.get(key, default)

    # ── Task tracking ──────────────────────────────────────

    def log_task(self, task: AgentTask) -> None:
        """Record a task in the session log."""
        self.task_log.append(task)
        self.agent_results[task.agent_id] = task.result

    def log_message(self, message: AgentMessage) -> None:
        """Record an inter-agent message."""
        self.message_log.append(message)

    # ── Metrics ────────────────────────────────────────────

    def get_metrics(self) -> CrewMetrics:
        """Compute aggregate metrics from the session."""
        metrics = CrewMetrics()
        metrics.total_tasks = len(self.task_log)

        invocations: dict[str, int] = {}
        latencies: dict[str, list[int]] = {}
        errors: dict[str, int] = {}

        for task in self.task_log:
            invocations[task.agent_id] = invocations.get(task.agent_id, 0) + 1

            if task.status == TaskStatus.COMPLETED:
                metrics.completed_tasks += 1
                metrics.total_execution_time_ms += task.execution_time_ms
                metrics.total_token_usage += task.token_usage
                latencies.setdefault(task.agent_id, []).append(task.execution_time_ms)
            elif task.status == TaskStatus.FAILED:
                metrics.failed_tasks += 1
                errors[task.agent_id] = errors.get(task.agent_id, 0) + 1
            elif task.status == TaskStatus.ESCALATED:
                metrics.escalated_tasks += 1

        metrics.agent_invocations = invocations

        for agent_id, lats in latencies.items():
            metrics.agent_avg_latency_ms[agent_id] = sum(lats) / len(lats) if lats else 0

        for agent_id, count in invocations.items():
            metrics.agent_error_rates[agent_id] = (
                errors.get(agent_id, 0) / count if count > 0 else 0
            )

        return metrics

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state for API responses."""
        metrics = self.get_metrics()
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "agent_id": t.agent_id,
                    "objective": t.objective,
                    "status": t.status.value,
                    "execution_time_ms": t.execution_time_ms,
                    "created_at": t.created_at.isoformat(),
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in self.task_log
            ],
            "metrics": {
                "total_tasks": metrics.total_tasks,
                "completed": metrics.completed_tasks,
                "failed": metrics.failed_tasks,
                "escalated": metrics.escalated_tasks,
                "total_time_ms": metrics.total_execution_time_ms,
                "total_tokens": metrics.total_token_usage,
                "agent_invocations": metrics.agent_invocations,
            },
            "context_keys": list(self.context.keys()),
        }

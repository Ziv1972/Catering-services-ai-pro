"""
Agent_crew - Catering AI Pro
Data models for the crew system: roles, tasks, messages, sessions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    ESCALATION = "escalation"
    DATA_SHARE = "data_share"
    STATUS_UPDATE = "status_update"


@dataclass(frozen=True)
class AgentRole:
    """Immutable role definition for a crew agent."""
    id: str
    title: str
    goal: str
    backstory: str
    responsibilities: tuple[str, ...]
    tools: tuple[str, ...]
    interacts_with: tuple[str, ...]
    icon: str = "bot"
    color: str = "#6366f1"


@dataclass
class AgentTask:
    """A task assigned by the manager to a specialist agent."""
    task_id: str
    agent_id: str
    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    output_format: Optional[str] = None
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    token_usage: int = 0

    def complete(self, result: dict[str, Any], execution_time_ms: int = 0, token_usage: int = 0) -> "AgentTask":
        return AgentTask(
            task_id=self.task_id,
            agent_id=self.agent_id,
            objective=self.objective,
            context=self.context,
            output_format=self.output_format,
            priority=self.priority,
            status=TaskStatus.COMPLETED,
            result=result,
            error=None,
            created_at=self.created_at,
            completed_at=datetime.utcnow(),
            execution_time_ms=execution_time_ms,
            token_usage=token_usage,
        )

    def fail(self, error: str) -> "AgentTask":
        return AgentTask(
            task_id=self.task_id,
            agent_id=self.agent_id,
            objective=self.objective,
            context=self.context,
            output_format=self.output_format,
            priority=self.priority,
            status=TaskStatus.FAILED,
            result=None,
            error=error,
            created_at=self.created_at,
            completed_at=datetime.utcnow(),
            execution_time_ms=0,
            token_usage=0,
        )


@dataclass
class AgentMessage:
    """Structured message between agents."""
    source_agent: str
    target_agent: str
    message_type: MessageType
    task_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CrewMetrics:
    """Aggregated metrics for the crew."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    escalated_tasks: int = 0
    total_execution_time_ms: int = 0
    total_token_usage: int = 0
    agent_invocations: dict[str, int] = field(default_factory=dict)
    agent_avg_latency_ms: dict[str, float] = field(default_factory=dict)
    agent_error_rates: dict[str, float] = field(default_factory=dict)

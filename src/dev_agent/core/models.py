"""Contratos trocados entre orquestrador e subagents."""

from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor metadados dos agentes disponíveis na API local.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Informar o comando de execução de cada agente.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Formalizar prontidão, planos e tarefas assíncronas dos agents.

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Formalizar a máquina de estados e os checkpoints de uma tarefa.
class TaskStatus(str, Enum):
    """Fases da máquina de estados de uma tarefa (ver ``core/state_machine.py``)."""

    RECEIVED = "received"
    DISCOVERING = "discovering"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DOCUMENTING = "documenting"
    PREPARING_GIT = "preparing_git"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ContextPacket(BaseModel):
    project_name: str
    project_root: Path
    objective: str
    instructions: list[str] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)
    git_diff: str | None = None
    previous_summary: str | None = None
    file_contents: dict[str, str] = Field(default_factory=dict)


class SubAgentResult(BaseModel):
    agent: str
    summary: str
    files_read: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    tests_executed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    architecture_decision_required: bool = False
    next_actions: list[str] = Field(default_factory=list)


class AgentDescriptor(BaseModel):
    name: str
    description: str
    mode: str
    command: str


class AgentManifest(BaseModel):
    """Metadados versionados de um Agent ou componente de coordenação."""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    module: str
    class_name: str
    purpose: str
    mode: Literal["read", "write", "execute", "guard", "orchestrate"]
    kind: Literal["subagent", "service", "policy", "orchestrator"] = "subagent"
    prompt_source: str | None = None
    tools: list[str] = Field(default_factory=list)
    input_model: str = "ContextPacket"
    output_model: str = "SubAgentResult"
    provider_profile: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    registration: str = "agents/catalog.yaml"
    invocation: str = ""
    legacy: bool = True
    status: Literal["active", "adapter", "guard"] = "active"

    def descriptor(self) -> AgentDescriptor:
        return AgentDescriptor(
            name=self.name,
            description=self.purpose,
            mode=self.mode,
            command=self.invocation,
        )


class ReviewFinding(BaseModel):
    severity: str
    message: str
    file: str | None = None
    line: int | None = None


class CommitSuggestion(BaseModel):
    message: str
    files: list[str]
    rationale: str


class CodexReadiness(BaseModel):
    """Estado sanitizado da capacidade de executar o Codex local."""

    ready: bool
    executable: str | None = None
    version: str | None = None
    category: Literal["ready", "unavailable", "authentication", "network", "limit", "unknown"]
    detail: str
    checked_at: datetime


class TaskPlan(BaseModel):
    """Plano revisável antes de uma tarefa poder alterar código."""

    id: str
    project_root: Path
    project_name: str
    objective: str
    base_branch: str | None = None
    relevant_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    architecture_decision_required: bool = False
    architecture_approved: bool = False
    architecture_decision: str | None = None
    requires_confirmation: bool = True
    created_at: datetime


class Checkpoint(BaseModel):
    """Snapshot retomável do progresso de uma tarefa ao final de uma fase."""

    job_id: str
    phase: TaskStatus
    step_index: int
    completed_agents: list[str] = Field(default_factory=list)
    results: list[SubAgentResult] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    created_at: datetime


class AgentJob(BaseModel):
    """Estado persistível de uma execução assíncrona em worktree isolado."""

    id: str
    plan_id: str
    project_root: Path
    objective: str
    status: Literal["queued", "running", "completed", "partially_completed", "failed", "cancelled", "blocked"]
    phase: TaskStatus | None = None
    branch: str | None = None
    worktree_path: Path | None = None
    worktree_removed: bool = False
    results: list[SubAgentResult] = Field(default_factory=list)
    diff: str = ""
    error: str | None = None
    cancellation_requested: bool = False
    resumable: bool = False
    last_checkpoint: Checkpoint | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

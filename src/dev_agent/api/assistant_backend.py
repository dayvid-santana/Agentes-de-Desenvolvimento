"""Backend REST local para uma assistente externa acionar os agents."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Receber solicitações de agents vindas de uma assistente externa.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Retomar jobs interrompidos a partir do último checkpoint da tarefa.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor planos aprováveis e jobs isolados para tarefas de escrita.

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dev_agent.core.assistant_gateway import AssistantGateway
from dev_agent.core.job_manager import TaskJobManager
from dev_agent.core.models import AgentDescriptor, AgentJob, CommitSuggestion, SubAgentResult, TaskPlan
from dev_agent.config.loader import discover_project
from dev_agent.core.orchestrator import Orchestrator
from dev_agent.errors import DevAgentError
from dev_agent.providers.codex.provider import CodexProvider

router = APIRouter(prefix="/assistant", tags=["assistant-backend"])


class AssistantAgentRequest(BaseModel):
    """Solicitação normalizada enviada pelo repositório da assistente."""

    cwd: Path
    agent: str = Field(min_length=1, max_length=80)
    objective: str = Field(default="Compreender o projeto", min_length=1, max_length=4_000)
    staged: bool = False
    confirmed_write: bool = False


class AssistantAgentResponse(BaseModel):
    """Resultado uniforme para consumo pela assistente chamadora."""

    agent: str
    results: list[SubAgentResult] = Field(default_factory=list)
    commit_suggestions: list[CommitSuggestion] = Field(default_factory=list)


class TaskPlanRequest(BaseModel):
    cwd: Path
    objective: str = Field(min_length=1, max_length=4_000)


class JobStartRequest(BaseModel):
    confirmed_write: bool = False


class ArchitectureApprovalRequest(BaseModel):
    decision: str = Field(min_length=10, max_length=1_000)


class WorktreeCleanupRequest(BaseModel):
    confirmed_cleanup: bool = False


def _gateway(cwd: Path) -> AssistantGateway:
    return AssistantGateway(_orchestrator(cwd))


def _orchestrator(cwd: Path, _cancel_event=None) -> Orchestrator:
    return Orchestrator(discover_project(cwd), CodexProvider(cancel_event=_cancel_event))


jobs = TaskJobManager(_orchestrator)


@router.get("/agents", response_model=list[AgentDescriptor])
def available_agents() -> list[AgentDescriptor]:
    """Lista os agents que a assistente externa pode solicitar diretamente."""
    return AssistantGateway.available_agents()


@router.post("/invocations", response_model=AssistantAgentResponse)
def invoke_agent(request: AssistantAgentRequest) -> AssistantAgentResponse:
    """Encaminha uma solicitação ao agent selecionado."""
    results, suggestions = _gateway(request.cwd).invoke(
        request.agent,
        request.objective,
        staged=request.staged,
        confirmed_write=request.confirmed_write,
    )
    return AssistantAgentResponse(
        agent=request.agent,
        results=results,
        commit_suggestions=suggestions,
    )


@router.post("/task-plans", response_model=TaskPlan)
def create_task_plan(request: TaskPlanRequest) -> TaskPlan:
    """Cria um plano revisável sem alterar o checkout do projeto."""
    service = _orchestrator(request.cwd)
    packet, _ = service.context(request.objective)
    return jobs.create_plan(service.root, service.config.project.name, request.objective, packet.relevant_files)


@router.post("/task-plans/{plan_id}/architecture-approval", response_model=TaskPlan)
def approve_architecture(plan_id: str, request: ArchitectureApprovalRequest) -> TaskPlan:
    """Registra a decisão humana exigida antes de uma mudança estrutural."""
    return jobs.approve_architecture(plan_id, request.decision)


@router.post("/task-plans/{plan_id}/start", response_model=AgentJob)
def start_task_plan(plan_id: str, request: JobStartRequest) -> AgentJob:
    """Executa um plano aprovado em background e worktree próprio."""
    plan = jobs.get_plan(plan_id)
    readiness = CodexProvider().readiness(plan.project_root)
    if not readiness.ready:
        raise DevAgentError(f"Codex indisponível: {readiness.detail}")
    return jobs.start(plan_id, confirmed_write=request.confirmed_write)


@router.get("/jobs/{job_id}", response_model=AgentJob)
def get_job(job_id: str) -> AgentJob:
    return jobs.get_job(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=AgentJob)
def cancel_job(job_id: str) -> AgentJob:
    return jobs.cancel(job_id)


@router.post("/jobs/{job_id}/resume", response_model=AgentJob)
def resume_job(job_id: str) -> AgentJob:
    """Retoma um job bloqueado (ex.: após reinício da API) a partir do último checkpoint."""
    return jobs.resume(job_id)


@router.post("/jobs/{job_id}/cleanup", response_model=AgentJob)
def cleanup_worktree(job_id: str, request: WorktreeCleanupRequest) -> AgentJob:
    """Remove o worktree de um job finalizado após confirmação explícita."""
    return jobs.cleanup_worktree(job_id, confirmed_cleanup=request.confirmed_cleanup)

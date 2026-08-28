"""Backend REST local para uma assistente externa acionar os agents."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Receber solicitações de agents vindas de uma assistente externa.

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dev_agent.core.assistant_gateway import AssistantGateway
from dev_agent.core.models import AgentDescriptor, CommitSuggestion, SubAgentResult

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


def _gateway(cwd: Path) -> AssistantGateway:
    # Import tardio evita um ciclo entre a aplicação FastAPI e o gateway.
    from dev_agent.api.app import orchestrator

    return AssistantGateway(orchestrator(cwd))


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

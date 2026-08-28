"""Contrato de integração para assistentes externos consumirem agents."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Disponibilizar agents por um contrato estável para assistentes externas.

from dev_agent.agents.api_contract_agent import ApiContractAgent
from dev_agent.agents.bug_reproduction_agent import BugReproductionAgent
from dev_agent.agents.database_agent import DatabaseAgent
from dev_agent.agents.dependency_agent import DependencyAgent
from dev_agent.agents.documentation_agent import DocumentationAgent
from dev_agent.agents.frontend_agent import FrontendAgent
from dev_agent.agents.observability_agent import ObservabilityAgent
from dev_agent.agents.performance_agent import PerformanceAgent
from dev_agent.agents.quality_agent import QualityAgent
from dev_agent.agents.refactor_agent import RefactorAgent
from dev_agent.agents.release_agent import ReleaseAgent
from dev_agent.agents.requirements_agent import RequirementsAgent
from dev_agent.agents.security_agent import SecurityAgent
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent
from dev_agent.core.models import AgentDescriptor, CommitSuggestion, SubAgentResult
from dev_agent.errors import DevAgentError, UnsafeCommandError


class AssistantGateway:
    """Expõe apenas operações seguras e públicas do orquestrador."""

    _SPECIALISTS: dict[str, type[ReadOnlySpecialistAgent]] = {
        "requirements": RequirementsAgent,
        "security": SecurityAgent,
        "database": DatabaseAgent,
        "api_contract": ApiContractAgent,
        "quality": QualityAgent,
        "dependency": DependencyAgent,
        "performance": PerformanceAgent,
        "frontend": FrontendAgent,
        "observability": ObservabilityAgent,
        "release": ReleaseAgent,
        "refactor": RefactorAgent,
    }
    _DIRECT_AGENTS = frozenset({
        "ask", "context", "review", "test", "debug", "task", "git", "documentation", "bug_reproduction", *_SPECIALISTS,
    })

    def __init__(self, orchestrator) -> None:
        self.orchestrator = orchestrator

    @classmethod
    def available_agents(cls) -> list[AgentDescriptor]:
        """Lista somente os agents acionáveis diretamente pela integração."""
        descriptors = [
            descriptor
            for descriptor in cls._orchestrator_descriptors()
            if descriptor.name in cls._DIRECT_AGENTS
        ]
        descriptors[0:0] = [
            AgentDescriptor(
                name="ask",
                description="Responde perguntas sobre o contexto selecionado do projeto.",
                mode="read",
                command='POST /assistant/invocations {"agent": "ask"}',
            ),
            AgentDescriptor(
                name="task",
                description="Executa o fluxo controlado de escrita após confirmação explícita.",
                mode="write",
                command='POST /assistant/invocations {"agent": "task", "confirmed_write": true}',
            ),
        ]
        return descriptors

    @staticmethod
    def _orchestrator_descriptors() -> list[AgentDescriptor]:
        # Import tardio evita acoplamento circular durante a inicialização da API.
        from dev_agent.core.orchestrator import Orchestrator

        return Orchestrator.available_agents()

    def invoke(
        self,
        agent: str,
        objective: str,
        *,
        staged: bool = False,
        confirmed_write: bool = False,
    ) -> tuple[list[SubAgentResult], list[CommitSuggestion]]:
        """Executa um agent pelo nome, preservando o fluxo de escrita do orquestrador."""
        if agent not in self._DIRECT_AGENTS:
            raise DevAgentError(f"Agent indisponível para integração: {agent}.")

        if agent == "task":
            if not confirmed_write:
                raise UnsafeCommandError(
                    "A execução de 'task' pode alterar arquivos. Envie confirmed_write=true após confirmação explícita do usuário."
                )
            return self.orchestrator.task(objective), []

        if agent == "git":
            return [], self.orchestrator.commit_plan()

        if agent == "ask":
            return [self.orchestrator.ask(objective)], []
        if agent == "review":
            return [self.orchestrator.review(staged)], []
        if agent == "test":
            return [self.orchestrator.test()], []
        if agent == "debug":
            return [self.orchestrator.debug(objective)], []

        packet, context_result = self.orchestrator.context(objective)
        if agent == "context":
            return [context_result], []
        if agent == "documentation":
            return [DocumentationAgent().run(packet)], []
        if agent == "bug_reproduction":
            return [BugReproductionAgent(self.orchestrator.provider).run(packet)], []

        specialist = self._SPECIALISTS[agent](self.orchestrator.provider)
        return [specialist.run(packet)], []

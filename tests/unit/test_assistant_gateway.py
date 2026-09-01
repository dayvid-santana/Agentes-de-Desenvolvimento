# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o gateway de integração para assistentes externas.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a exposição do agente de padrões de projeto no gateway.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Cobrir a exposição do agente de modelagem de código no gateway.
from pathlib import Path

import pytest

from dev_agent.core.assistant_gateway import AssistantGateway
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.errors import UnsafeCommandError


class FakeProvider:
    def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
        return "Análise recebida"


class FakeOrchestrator:
    provider = FakeProvider()

    def __init__(self) -> None:
        self.task_objective = ""

    def context(self, objective: str):
        packet = ContextPacket(project_name="Demo", project_root=Path("."), objective=objective)
        return packet, SubAgentResult(agent="context", summary="Contexto selecionado")

    def task(self, objective: str):
        self.task_objective = objective
        return [SubAgentResult(agent="implementation", summary="Tarefa executada")]

    def commit_plan(self):
        return []


def test_gateway_exposes_only_direct_agents():
    names = {item.name for item in AssistantGateway.available_agents()}

    assert {"ask", "code_modeling", "security", "design_patterns", "task", "review"} <= names
    assert "implementation" not in names


def test_gateway_runs_a_read_only_specialist():
    results, suggestions = AssistantGateway(FakeOrchestrator()).invoke("security", "Avaliar autenticação")

    assert results[0].agent == "security"
    assert results[0].summary == "Análise recebida"
    assert suggestions == []


def test_gateway_runs_design_patterns_agent():
    results, suggestions = AssistantGateway(FakeOrchestrator()).invoke("design_patterns", "Avaliar a arquitetura")

    assert results[0].agent == "design_patterns"
    assert results[0].summary == "Análise recebida"
    assert suggestions == []


def test_gateway_runs_code_modeling_agent():
    results, suggestions = AssistantGateway(FakeOrchestrator()).invoke("code_modeling", "Modelar o domínio")

    assert results[0].agent == "code_modeling"
    assert results[0].summary == "Análise recebida"
    assert suggestions == []


def test_gateway_rejects_direct_task_execution():
    service = FakeOrchestrator()

    with pytest.raises(UnsafeCommandError):
        AssistantGateway(service).invoke("task", "Alterar projeto")
    with pytest.raises(UnsafeCommandError):
        AssistantGateway(service).invoke("task", "Alterar projeto", confirmed_write=True)

"""Planejamento de reprodução verificável para relatos de falha."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Transformar relatos de erro em reproduções e testes de regressão.
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider


class BugReproductionAgent(SubAgent):
    """Produz um plano de reprodução somente para objetivos que descrevem falhas."""

    name = "bug_reproduction"
    _signals = ("bug", "erro", "falha", "exceção", "exception", "traceback", "regressão", "regression")

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        if not any(signal in packet.objective.lower() for signal in self._signals):
            return SubAgentResult(agent=self.name, summary="Não aplicável: o objetivo não descreve uma falha a reproduzir.")
        context = "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items())
        response = self.provider.run(
            f"""Você é o BugReproductionAgent do DevAgent. Use somente as evidências abaixo para transformar
o relato em uma reprodução verificável. Não altere arquivos e não invente dados, causas ou resultados.
Responda no formato: Pré-condições; Passos numerados; Resultado observado; Resultado esperado; Teste de
regressão sugerido; Evidências ausentes.

Relato: {packet.objective}

Diff atual:
{packet.git_diff or "Sem diff disponível."}

Contexto selecionado:
{context}""",
            packet.project_root,
            write_access=False,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.relevant_files)

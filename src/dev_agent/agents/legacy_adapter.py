# dev-agent
# Autor: Dayvid Santana
# Criado em: 28/08/2026
# Editado em: 28/08/2026
# Objetivo: Adaptar Agents legados ao contrato comum de SubAgent.
"""Adapter de compatibilidade para Agents que ainda expõem APIs antigas."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult


class LegacyAgentAdapter(SubAgent):
    """Normaliza retornos de objetos legados sem exigir sua reescrita."""

    def __init__(self, legacy_agent: Any, name: str | None = None) -> None:
        self.legacy_agent = legacy_agent
        self.name = name or getattr(legacy_agent, "name", legacy_agent.__class__.__name__)

    def run(self, packet: ContextPacket) -> SubAgentResult:
        runner: Callable[[ContextPacket], Any] = getattr(self.legacy_agent, "run", self.legacy_agent)
        result = runner(packet)
        if isinstance(result, SubAgentResult):
            return result.model_copy(update={"agent": self.name})
        if isinstance(result, str):
            return SubAgentResult(agent=self.name, summary=result, files_read=packet.relevant_files)
        raise TypeError(f"Agent legado {self.name!r} retornou {type(result).__name__}; esperado SubAgentResult ou str.")

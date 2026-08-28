"""Base compartilhada dos agentes especialistas de análise."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Compartilhar a execução somente leitura dos agentes especialistas.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Aplicar revisão baseada em evidências aos agentes especialistas.
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider
from dev_agent.skills.registry import get_skill


class ReadOnlySpecialistAgent(SubAgent):
    """Base para análises especializadas que nunca alteram o projeto."""

    name = "specialist"
    specialty = "qualidade geral"
    instructions = "Aponte riscos concretos, prioridades e próximos passos."

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        context = "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items())
        response = self.provider.run(
            f"""Você é o {self.__class__.__name__} do DevAgent. Analise o objetivo e o diff do projeto
{packet.project_name}, limitando-se ao contexto fornecido. Sua especialidade é {self.specialty}.
{self.instructions}
Skill evidence-review: {get_skill("evidence-review").instructions}
Não altere arquivos, não invente fatos fora do contexto e não faça sugestões cosméticas.

Objetivo: {packet.objective}

Diff atual:
{packet.git_diff or "Sem diff disponível."}

Contexto selecionado:
{context}""",
            packet.project_root,
            write_access=False,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.relevant_files)

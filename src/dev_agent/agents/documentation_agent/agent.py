"""Avalia impactos simples da documentação relacionados à alteração."""
from __future__ import annotations
from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult

class DocumentationAgent(SubAgent):
    name = "documentation"
    def run(self, packet: ContextPacket) -> SubAgentResult:
        changed_api = any(path.endswith((".py", ".ts", ".js")) for path in packet.relevant_files)
        next_actions = ["Avaliar atualização de README.md ou docs/ para contrato alterado."] if changed_api else []
        return SubAgentResult(agent=self.name, summary="Documentação analisada no escopo selecionado.", files_read=packet.documentation, next_actions=next_actions)

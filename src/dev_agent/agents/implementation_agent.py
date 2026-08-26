"""Execução autônoma de implementação através do provider configurado."""
from __future__ import annotations
from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider

class ImplementationAgent(SubAgent):
    name = "implementation"
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
    def run(self, packet: ContextPacket) -> SubAgentResult:
        prompt = self._prompt(packet)
        response = self.provider.run(prompt, packet.project_root, write_access=True)
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.relevant_files, next_actions=["Executar testes e revisão."])
    def _prompt(self, packet: ContextPacket) -> str:
        context = "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items())
        return f"""Você é o ImplementationAgent do DevAgent. Trabalhe somente em {packet.project_root}.
Objetivo: {packet.objective}
Siga estritamente AGENTS.md e documentação fornecidos. Não faça operações destrutivas, push, reset ou clean. Preserve mudanças preexistentes não relacionadas. Implemente e teste a tarefa. Ao criar ou alterar código de forma significativa, mantenha o cabeçalho/histórico exigido pelo projeto; não coloque comentários em JSON, lockfiles, gerados ou binários.
Contexto selecionado:\n{context}\n
Responda com resumo, arquivos modificados, testes e riscos."""

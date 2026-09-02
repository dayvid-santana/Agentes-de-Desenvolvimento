"""Atualização da documentação externa do projeto."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de escrita de documentação em módulo próprio.
# DevAgent
# Autor: Dayvid Santana
# Data: 02/09/2026
# Objetivo: Restringir a escrita à documentação destinada a pessoas.
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider


class DocumentationWriterAgent(SubAgent):
    """Atualiza documentação apenas quando a implementação exigir essa mudança."""

    name = "documentation_writer"

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        context = "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items())
        response = self.provider.run(
            f"""Você é o DocumentationWriterAgent do DevAgent. Trabalhe somente em {packet.project_root}.
Verifique se o diff abaixo alterou comportamento, configuração, operação ou contrato que precise ser documentado.
Se precisar, siga docs/documentation.md quando esse arquivo existir e atualize exclusivamente README.md, docs/
ou documentação de API já existente; se não precisar, não altere arquivo algum. Não altere AGENTS.md,
agent-context/, código, dependências, arquivos gerados, JSON estrito ou lockfiles.
Responda com o que foi alterado ou com a justificativa para não alterar documentação.

Objetivo: {packet.objective}

Diff atual:
{packet.git_diff or "Sem diff disponível."}

Contexto selecionado:
{context}""",
            packet.project_root,
            write_access=True,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.documentation)

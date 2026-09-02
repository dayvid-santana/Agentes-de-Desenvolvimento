"""Documentação abrangente e orientada ao estado atual do projeto."""
# DevAgent
# Autor: Dayvid Santana
# Data: 02/09/2026
# Objetivo: Preservar a separação entre documentação humana e contexto de IA.
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 31/08/2026
# Objetivo: Criar e atualizar a documentação completa de projetos.
# DevAgent-Task: project-documentation-agent-20260831

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider


class ProjectDocumentationAgent(SubAgent):
    """Atualiza documentação de projeto sem modificar código ou configuração."""

    name = "project_documentation"

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        response = self.provider.run(
            f"""Você é o ProjectDocumentationAgent do DevAgent. Trabalhe somente em {packet.project_root}.
Documente o projeto como ele existe hoje. Inspecione README.md, docs/, configuração, código-fonte e testes
necessários para entender instalação, execução, arquitetura, fluxos, configuração, segurança e testes.
Siga o padrão em docs/documentation.md quando ele existir. Crie ou atualize apenas README.md, arquivos em docs/
e documentação de API já existente. Não altere AGENTS.md, agent-context/, código, dependências, configuração,
lockfiles ou artefatos gerados. Não invente comportamento.
Se houver lacunas de informação, registre-as claramente em vez de supor.

Objetivo: {packet.objective}

Contexto inicial:
{chr(10).join(f'### {name}{chr(10)}{content}' for name, content in packet.file_contents.items())}

Responda com os documentos atualizados, os tópicos cobertos e lacunas restantes.""",
            packet.project_root,
            write_access=True,
            timeout_seconds=1800,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.documentation)

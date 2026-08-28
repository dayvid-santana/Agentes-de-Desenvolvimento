"""Agentes especializados de análise e documentação para tarefas completas."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Adicionar análises especializadas ao fluxo de tarefas.
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider


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


class RequirementsAgent(ReadOnlySpecialistAgent):
    name = "requirements"
    specialty = "requisitos, critérios de aceite, casos de borda e riscos de escopo"
    instructions = "Transforme o pedido em critérios verificáveis e destaque ambiguidades que possam afetar a implementação."


class SecurityAgent(ReadOnlySpecialistAgent):
    name = "security"
    specialty = "autenticação, autorização, validação de entrada, segredos e vulnerabilidades comuns"
    instructions = "Priorize falhas exploráveis e exposição de dados; indique severidade apenas quando houver evidência no diff ou contexto."


class DatabaseAgent(ReadOnlySpecialistAgent):
    name = "database"
    specialty = "migrations, integridade, índices, consultas, concorrência e rollback de dados"
    instructions = "Avalie somente impactos de persistência que a mudança realmente introduz ou pode introduzir."


class ApiContractAgent(ReadOnlySpecialistAgent):
    name = "api_contract"
    specialty = "compatibilidade de endpoints, schemas, status HTTP, paginação e contratos públicos"
    instructions = "Identifique quebras de compatibilidade e proponha uma mitigação objetiva quando aplicável."


class QualityAgent(ReadOnlySpecialistAgent):
    name = "quality"
    specialty = "lacunas de testes unitários, integração e casos de borda"
    instructions = "Liste os cenários de teste ausentes mais importantes e relacione-os à alteração observada."


class DependencyAgent(ReadOnlySpecialistAgent):
    name = "dependency"
    specialty = "dependências desnecessárias, duplicadas, vulneráveis ou desatualizadas"
    instructions = "Não recomende atualização especulativa; destaque somente dependências visíveis no contexto ou diff."


class PerformanceAgent(ReadOnlySpecialistAgent):
    name = "performance"
    specialty = "N+1, I/O, loops custosos, cache e gargalos de execução"
    instructions = "Diferencie gargalos comprováveis de hipóteses e sugira como medir cada hipótese."


class FrontendAgent(ReadOnlySpecialistAgent):
    name = "frontend"
    specialty = "acessibilidade, responsividade, consistência visual e estados de interface"
    instructions = "Quando não houver interface no contexto, registre que a análise não se aplica em vez de inventar problemas."


class ObservabilityAgent(ReadOnlySpecialistAgent):
    name = "observability"
    specialty = "logs seguros, métricas, rastreamento e mensagens de erro acionáveis"
    instructions = "Sugira instrumentação mínima e não permita dados sensíveis em logs."


class ReleaseAgent(ReadOnlySpecialistAgent):
    name = "release"
    specialty = "versão, changelog, migrations, configuração e checklist de publicação"
    instructions = "Produza somente itens de release pertinentes à alteração atual."


class RefactorAgent(ReadOnlySpecialistAgent):
    name = "refactor"
    specialty = "refatorações pequenas, seguras e com cobertura de testes"
    instructions = "Separe refatorações necessárias para a tarefa das melhorias opcionais que devem ficar fora do escopo."


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
Se precisar, atualize exclusivamente README.md, docs/ ou documentação de API já existente; se não precisar, não altere arquivo algum.
Não altere código, dependências, arquivos gerados, JSON estrito ou lockfiles. Preserve instruções de AGENTS.md.
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

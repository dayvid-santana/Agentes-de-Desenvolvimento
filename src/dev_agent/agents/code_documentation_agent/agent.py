"""Documentação do código alterado durante uma tarefa."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Documentar código alterado sem modificar cabeçalhos existentes.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Aplicar a Skill reutilizável de documentação de código.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Exigir documentação de classes, funções e declarações de tipos selecionadas.
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider
from dev_agent.skills.registry import get_skill


class CodeDocumentationAgent(SubAgent):
    """Documenta todas as declarações de código presentes nos arquivos selecionados."""

    name = "code_documentation"
    _code_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".c", ".cpp", ".h"}

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        files = [name for name in packet.relevant_files if self._is_code(name)]
        if not files:
            return SubAgentResult(agent=self.name, summary="Não aplicável: nenhum arquivo de código alterado foi selecionado.")
        context = "\n\n".join(f"### {name}\n{packet.file_contents[name]}" for name in files)
        documentation_skill = get_skill("code-documentation")
        header_skill = get_skill("code-header")
        response = self.provider.run(
            f"""Você é o CodeDocumentationAgent do DevAgent. Trabalhe somente em {packet.project_root}.
Documente todas as classes, funções, métodos e declarações de tipos dos arquivos de código selecionados,
incluindo elementos privados. Para Python, use docstrings; para JavaScript, TypeScript e JSX/TSX, use JSDoc;
para as demais linguagens, use o formato idiomático de comentário de documentação. Cada descrição deve indicar
a responsabilidade, entradas, saídas, efeitos colaterais ou invariantes quando aplicável. Comentários internos
só devem ser usados para decisões não óbvias. Não refatore, não altere comportamento e não modifique nenhum
cabeçalho existente. Para arquivos novos sem cabeçalho, o orquestrador aplicará o padrão do projeto após sua execução.

Skills aplicadas:
code-documentation: {documentation_skill.instructions}
code-header: {header_skill.instructions}

Objetivo: {packet.objective}

Diff atual:
{packet.git_diff or "Sem diff disponível."}

Código selecionado:
{context}

Responda com arquivos documentados e a justificativa de cada alteração.""",
            packet.project_root,
            write_access=True,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=files)

    @classmethod
    def _is_code(cls, name: str) -> bool:
        return any(name.endswith(suffix) for suffix in cls._code_suffixes)

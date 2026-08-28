"""Criação dirigida de testes para alterações de código."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Criar testes de regressão para mudanças implementadas.
from __future__ import annotations

from pathlib import Path

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.providers.base import LLMProvider


class TestAuthorAgent(SubAgent):
    """Cria apenas testes relacionados ao código presente no contexto."""

    __test__ = False
    name = "test_author"
    _source_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".c", ".cpp", ".h"}

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        source = [name for name in packet.relevant_files if self._is_source(name)]
        if not source:
            return SubAgentResult(agent=self.name, summary="Não aplicável: nenhum código-fonte alterado foi selecionado.")
        context = "\n\n".join(f"### {name}\n{packet.file_contents[name]}" for name in packet.relevant_files)
        response = self.provider.run(
            f"""Você é o TestAuthorAgent do DevAgent. Trabalhe somente em {packet.project_root}.
Com base no diff e no código selecionado, crie ou atualize somente testes automatizados que cubram o
comportamento alterado e casos de borda reais. Não altere código de produção, dependências, configuração,
arquivos gerados ou lockfiles. Use o padrão de testes já existente no projeto. Se a cobertura atual for
suficiente, não altere arquivos e explique por quê.

Objetivo: {packet.objective}

Diff atual:
{packet.git_diff or "Sem diff disponível."}

Contexto selecionado:
{context}

Responda com os cenários cobertos, arquivos de teste alterados e lacunas restantes.""",
            packet.project_root,
            write_access=True,
        )
        return SubAgentResult(agent=self.name, summary=response, files_read=packet.relevant_files)

    @classmethod
    def _is_source(cls, name: str) -> bool:
        return not name.startswith(("tests/", "test/")) and not Path(name).name.startswith("test_") and Path(name).suffix in cls._source_suffixes

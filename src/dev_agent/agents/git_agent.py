"""Análise Git e plano de Conventional Commits sem criar commits."""
from __future__ import annotations
from pathlib import Path
from dev_agent.core.models import CommitSuggestion
from dev_agent.tools.git import GitTool

class GitAgent:
    def __init__(self, root: Path) -> None: self.git = GitTool(root)
    def commit_plan(self) -> list[CommitSuggestion]:
        status = self.git.status()
        files = [line[3:].strip() for line in status.splitlines() if len(line) > 3 and not line.startswith("##")]
        if not files: return []
        tests = [item for item in files if item.startswith("tests/") or "test_" in item]
        docs = [item for item in files if item.lower().endswith((".md", ".rst"))]
        code = [item for item in files if item not in tests and item not in docs]
        result: list[CommitSuggestion] = []
        if code: result.append(CommitSuggestion(message="feat(scope): descreve a alteração principal", files=code, rationale="Arquivos de implementação devem formar um commit coeso."))
        if tests: result.append(CommitSuggestion(message="test(scope): cobre a alteração principal", files=tests, rationale="Testes foram separados para facilitar revisão; podem ser unidos ao commit funcional se forem inseparáveis."))
        if docs: result.append(CommitSuggestion(message="docs(scope): atualiza documentação", files=docs, rationale="Documentação é semanticamente distinta."))
        return result

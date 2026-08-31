"""Chamadas Git explícitas para inspeção e worktrees isolados."""

from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar tarefas aprovadas em worktrees Git dedicados.

from pathlib import Path

from dev_agent.errors import DevAgentError, ToolExecutionError
from dev_agent.tools.terminal import TerminalTool


class GitTool:
    def __init__(self, project_root: Path) -> None:
        self.root = project_root.resolve()
        self.terminal = TerminalTool(project_root)

    def _git(self, *args: str) -> str:
        result = self.terminal.run(["git", *args])
        return result.stdout if result.exit_code == 0 else ""

    def status(self) -> str:
        return self._git("status", "--short", "--branch")

    def diff(self, staged: bool = False) -> str:
        return self._git("diff", "--staged" if staged else "") if staged else self._git("diff")

    def full_diff(self) -> str:
        """Diff incluindo arquivos novos ainda não rastreados, via intent-to-add."""
        self._git("add", "-A", "-N", ".")
        return self._git("diff")

    def log(self, limit: int = 10) -> str:
        return self._git("log", f"-{limit}", "--oneline")

    def branch(self) -> str:
        return self._git("branch", "--show-current")

    def is_repository(self) -> bool:
        return self._git("rev-parse", "--is-inside-work-tree").strip() == "true"

    def is_clean(self) -> bool:
        return not self._git("status", "--porcelain").strip()

    def create_worktree(self, job_id: str) -> tuple[Path, str]:
        """Cria uma branch de tarefa fora do checkout ativo, sem tocar nele."""
        if not self.is_repository():
            raise DevAgentError("A execução isolada requer um repositório Git.")
        if not self.is_clean():
            raise DevAgentError("O projeto possui alterações locais. Faça commit ou stash antes de iniciar uma tarefa isolada.")

        parent = self.root.parent / f".{self.root.name}-dev-agent-worktrees"
        target = (parent / job_id).resolve()
        if target.parent != parent.resolve():
            raise DevAgentError("O destino do worktree é inválido.")
        if target.exists():
            raise DevAgentError("Já existe um worktree para esta tarefa.")
        branch = f"dev-agent/{job_id}"
        result = self.terminal.run(["git", "worktree", "add", "-b", branch, str(target), "HEAD"], timeout_seconds=60)
        if result.exit_code != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "erro desconhecido"
            raise ToolExecutionError(f"Não foi possível criar o worktree: {detail}")
        return target, branch

    def remove_worktree(self, target: Path) -> None:
        """Remove somente um worktree criado pelo DevAgent após confirmação externa."""
        parent = (self.root.parent / f".{self.root.name}-dev-agent-worktrees").resolve()
        resolved = target.resolve()
        if resolved.parent != parent:
            raise DevAgentError("O worktree informado não pertence a este projeto.")
        result = self.terminal.run(["git", "worktree", "remove", "--force", str(resolved)], timeout_seconds=60, confirmed_destructive=True)
        if result.exit_code != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "erro desconhecido"
            raise ToolExecutionError(f"Não foi possível remover o worktree: {detail}")

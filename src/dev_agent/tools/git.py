"""Chamadas Git explícitas, somente de leitura para o MVP."""

from __future__ import annotations

from pathlib import Path

from dev_agent.tools.terminal import TerminalTool


class GitTool:
    def __init__(self, project_root: Path) -> None:
        self.terminal = TerminalTool(project_root)

    def _git(self, *args: str) -> str:
        result = self.terminal.run(["git", *args])
        return result.stdout if result.exit_code == 0 else ""

    def status(self) -> str:
        return self._git("status", "--short", "--branch")

    def diff(self, staged: bool = False) -> str:
        return self._git("diff", "--staged" if staged else "") if staged else self._git("diff")

    def log(self, limit: int = 10) -> str:
        return self._git("log", f"-{limit}", "--oneline")

    def branch(self) -> str:
        return self._git("branch", "--show-current")


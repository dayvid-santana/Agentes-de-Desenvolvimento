"""Provider para Codex CLI 0.149+ usando `codex exec`."""
from __future__ import annotations
import shutil
from pathlib import Path

from dev_agent.errors import CodexUnavailableError, ToolExecutionError
from dev_agent.tools.terminal import TerminalTool

class CodexProvider:
    def available(self) -> bool:
        return shutil.which("codex") is not None

    def run(self, prompt: str, project_root: Path, *, write_access: bool = False, timeout_seconds: int = 600) -> str:
        if not self.available():
            raise CodexUnavailableError("A CLI `codex` não foi encontrada no PATH.")
        sandbox = "workspace-write" if write_access else "read-only"
        result = TerminalTool(project_root, timeout_seconds).run(["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-C", str(project_root), "--sandbox", sandbox, "--ask-for-approval", "never", prompt], timeout_seconds)
        if result.exit_code != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ToolExecutionError(f"Codex falhou: {detail}")
        return result.stdout.strip()

"""Execução de processos sem shell por padrão."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

from dev_agent.errors import ToolExecutionError
from dev_agent.logging import event


class CommandResult(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class TerminalTool:
    def __init__(self, cwd: Path, timeout_seconds: int = 120) -> None:
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds

    def run(self, command: list[str], timeout_seconds: int | None = None) -> CommandResult:
        started = time.monotonic()
        event("tool.terminal.started", command=" ".join(command), cwd=str(self.cwd))
        try:
            completed = subprocess.run(command, cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds or self.timeout_seconds, shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolExecutionError(f"Falha ao executar {' '.join(command)}: {exc}") from exc
        result = CommandResult(command=command, exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr, duration_ms=int((time.monotonic() - started) * 1000))
        event("tool.terminal.finished", command=" ".join(command), exit_code=result.exit_code, duration_ms=result.duration_ms)
        return result

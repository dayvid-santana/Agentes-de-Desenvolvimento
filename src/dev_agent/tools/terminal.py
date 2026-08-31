"""Execução de processos sem shell por padrão."""

from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Permitir cancelamento cooperativo de processos dos jobs dos agents.

import subprocess
import threading
import time
from pathlib import Path

from pydantic import BaseModel

from dev_agent.errors import ToolExecutionError
from dev_agent.logging import event
from dev_agent.security.command_policy import CommandPolicy


class CommandResult(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class TerminalTool:
    def __init__(self, cwd: Path, timeout_seconds: int = 120, cancel_event: threading.Event | None = None) -> None:
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self.cancel_event = cancel_event

    def run(self, command: list[str], timeout_seconds: int | None = None, cancel_event: threading.Event | None = None, *, confirmed_destructive: bool = False, input_text: str | None = None) -> CommandResult:
        CommandPolicy().ensure_safe(" ".join(command), confirmed=confirmed_destructive)
        started = time.monotonic()
        event("tool.terminal.started", command=" ".join(command), cwd=str(self.cwd))
        timeout = timeout_seconds or self.timeout_seconds
        active_cancellation = cancel_event or self.cancel_event
        try:
            if active_cancellation is None:
                completed = subprocess.run(command, cwd=self.cwd, input=input_text, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False)
            else:
                completed = self._run_cancellable(command, timeout, active_cancellation, input_text)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolExecutionError(f"Falha ao executar {' '.join(command)}: {exc}") from exc
        result = CommandResult(command=command, exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr, duration_ms=int((time.monotonic() - started) * 1000))
        event("tool.terminal.finished", command=" ".join(command), exit_code=result.exit_code, duration_ms=result.duration_ms)
        return result

    def _run_cancellable(self, command: list[str], timeout_seconds: int, cancel_event: threading.Event, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        stdin = subprocess.PIPE if input_text is not None else None
        process = subprocess.Popen(command, cwd=self.cwd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False)
        deadline = time.monotonic() + timeout_seconds
        pending_input = input_text
        while True:
            if cancel_event.is_set():
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise ToolExecutionError("Execução cancelada pelo usuário.")
            try:
                stdout, stderr = process.communicate(input=pending_input, timeout=min(0.2, max(0.01, deadline - time.monotonic())))
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                pending_input = None
                if time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    raise

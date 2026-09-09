"""Cria checkpoints Git locais após um período de inatividade."""

from __future__ import annotations

import threading
import time
from pathlib import Path, PurePath
from typing import Callable

from pydantic import BaseModel, Field

from dev_agent.config.models import DevAgentConfig
from dev_agent.errors import DevAgentError
from dev_agent.logging import event
from dev_agent.tools.git import GitTool
from dev_agent.tools.tests import TestResult, TestTool


class AutoCommitResult(BaseModel):
    committed: bool = False
    reason: str
    tests_executed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AutoCommitAgent:
    """Serviço opt-in que nunca faz push nem altera um índice Git já preparado."""

    name = "auto_commit"

    def __init__(
        self,
        root: Path,
        config: DevAgentConfig,
        *,
        git: GitTool | None = None,
        tests: TestTool | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root = root.resolve()
        self.config = config
        self.git = git or GitTool(self.root)
        self.tests = tests or TestTool(self.git.terminal, config.testing.command)
        self.clock = clock

    def commit_if_ready(self) -> AutoCommitResult:
        """Valida e cria um único checkpoint se o worktree estiver seguro."""
        if not self.config.autocommit.enabled:
            return AutoCommitResult(reason="Checkpoint automático não está habilitado na configuração do projeto.")
        if not self.git.is_repository():
            return AutoCommitResult(reason="O projeto atual não é um repositório Git.")
        if self.git.operation_in_progress():
            return AutoCommitResult(reason="Há uma operação Git em andamento; checkpoint adiado.")

        status_before = self.git.porcelain_status()
        if not status_before.strip():
            return AutoCommitResult(reason="Não há alterações locais para registrar.")
        if self._has_staged_changes(status_before):
            return AutoCommitResult(reason="O índice Git já possui alterações; checkpoint adiado para preservar o preparo manual.")
        sensitive = self._sensitive_paths(status_before)
        if sensitive:
            return AutoCommitResult(reason="Foram encontradas alterações em caminhos sensíveis; checkpoint bloqueado.", warnings=sensitive)

        tests_executed: list[str] = []
        if self.config.autocommit.run_tests:
            test_result = self.tests.run()
            tests_executed.append(test_result.command)
            if test_result.exit_code != 0:
                warning = (test_result.stderr or test_result.stdout).strip()[-2000:]
                return AutoCommitResult(reason="Os testes falharam; checkpoint não criado.", tests_executed=tests_executed, warnings=[warning] if warning else [])

        if self.git.operation_in_progress():
            return AutoCommitResult(reason="Uma operação Git começou durante a validação; checkpoint adiado.", tests_executed=tests_executed)
        if self.git.porcelain_status() != status_before:
            return AutoCommitResult(reason="O estado do projeto mudou durante a validação; checkpoint adiado.", tests_executed=tests_executed)

        try:
            self.git.stage_all()
            self.git.commit(self.config.autocommit.message)
        except DevAgentError as exc:
            return AutoCommitResult(reason="Não foi possível criar o checkpoint.", tests_executed=tests_executed, warnings=[str(exc)])
        event("agent.auto_commit.created", root=str(self.root))
        return AutoCommitResult(committed=True, reason="Checkpoint local criado.", tests_executed=tests_executed)

    def watch(self, stop_event: threading.Event | None = None) -> list[AutoCommitResult]:
        """Observa o estado Git por polling até interrupção cooperativa."""
        if not self.config.autocommit.enabled:
            return [AutoCommitResult(reason="Checkpoint automático não está habilitado na configuração do projeto.")]
        stopper = stop_event or threading.Event()
        last_status = self.git.porcelain_status()
        last_change_at = self.clock()
        results: list[AutoCommitResult] = []
        while not stopper.is_set():
            if stopper.wait(self.config.autocommit.polling_seconds):
                break
            current_status = self.git.porcelain_status()
            if current_status != last_status:
                last_status = current_status
                last_change_at = self.clock()
                continue
            if current_status.strip() and self.clock() - last_change_at >= self.config.autocommit.inactivity_seconds:
                result = self.commit_if_ready()
                results.append(result)
                last_status = self.git.porcelain_status()
                last_change_at = self.clock()
        return results

    @staticmethod
    def _has_staged_changes(status: str) -> bool:
        return any(line and line[0] not in {" ", "?"} for line in status.splitlines())

    def _sensitive_paths(self, status: str) -> list[str]:
        blocked: list[str] = []
        patterns = [pattern.lower() for pattern in self.config.security.sensitive_patterns]
        for line in status.splitlines():
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ")[-1]
            name = PurePath(path.replace("\\", "/")).name.lower()
            if any(PurePath(name).match(pattern) for pattern in patterns):
                blocked.append(path)
        return blocked

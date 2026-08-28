"""Provider para Codex CLI 0.149+ usando `codex exec`."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Verificar a prontidão autenticada do Codex sem expor credenciais.

import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dev_agent.core.models import CodexReadiness
from dev_agent.errors import CodexUnavailableError, ToolExecutionError
from dev_agent.tools.terminal import TerminalTool


class CodexProvider:
    _readiness_cache: dict[str, tuple[float, CodexReadiness]] = {}
    _readiness_lock = threading.Lock()

    def __init__(self, cancel_event: threading.Event | None = None) -> None:
        self.cancel_event = cancel_event

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def readiness(self, project_root: Path, *, force: bool = False) -> CodexReadiness:
        """Confirma executável, autenticação e uma chamada mínima em modo leitura."""
        root = project_root.resolve()
        cache_key = str(root)
        now = time.monotonic()
        with self._readiness_lock:
            cached = self._readiness_cache.get(cache_key)
        if cached and not force and now - cached[0] < 60:
            return cached[1]

        executable = shutil.which("codex")
        if not executable:
            readiness = self._readiness(False, None, None, "unavailable", "A CLI `codex` não foi encontrada no PATH.")
            self._cache(cache_key, readiness)
            return readiness

        terminal = TerminalTool(root, timeout_seconds=30)
        try:
            version_result = terminal.run(["codex", "--version"], timeout_seconds=10)
            if version_result.exit_code != 0:
                readiness = self._failure(executable, version_result.stderr or version_result.stdout)
            else:
                version = version_result.stdout.strip().splitlines()[0][:120] if version_result.stdout.strip() else "versão não informada"
                probe = terminal.run(
                    [
                        "codex", "exec", "--ephemeral", "--skip-git-repo-check", "-C", str(root),
                        "--sandbox", "read-only", "--ask-for-approval", "never", "Responda somente: READY.",
                    ],
                    timeout_seconds=30,
                )
                readiness = self._readiness(True, executable, version, "ready", "Codex autenticado e pronto.") if probe.exit_code == 0 else self._failure(executable, probe.stderr or probe.stdout, version)
        except ToolExecutionError as exc:
            readiness = self._failure(executable, str(exc))
        self._cache(cache_key, readiness)
        return readiness

    def _cache(self, key: str, readiness: CodexReadiness) -> None:
        with self._readiness_lock:
            self._readiness_cache[key] = (time.monotonic(), readiness)

    @staticmethod
    def _readiness(ready: bool, executable: str | None, version: str | None, category: str, detail: str) -> CodexReadiness:
        return CodexReadiness(
            ready=ready,
            executable=executable,
            version=version,
            category=category,
            detail=detail,
            checked_at=datetime.now(timezone.utc),
        )

    def _failure(self, executable: str, raw_detail: str, version: str | None = None) -> CodexReadiness:
        detail = raw_detail.lower()
        if any(term in detail for term in ("login", "sign in", "authentication", "unauthorized", "401")):
            return self._readiness(False, executable, version, "authentication", "Codex não está autenticado. Execute `codex` e conclua o login.")
        if any(term in detail for term in ("rate limit", "usage limit", "quota", "429")):
            return self._readiness(False, executable, version, "limit", "O limite de uso do Codex foi atingido. Tente novamente mais tarde.")
        if any(term in detail for term in ("network", "connection", "dns", "timed out", "timeout")):
            return self._readiness(False, executable, version, "network", "Não foi possível alcançar o Codex. Verifique a conexão de rede.")
        return self._readiness(False, executable, version, "unknown", "O Codex não respondeu à verificação de prontidão.")

    def run(self, prompt: str, project_root: Path, *, write_access: bool = False, timeout_seconds: int = 600) -> str:
        if not self.available():
            raise CodexUnavailableError("A CLI `codex` não foi encontrada no PATH.")
        sandbox = "workspace-write" if write_access else "read-only"
        attempts = 1 if write_access else 3
        for attempt in range(attempts):
            try:
                result = TerminalTool(project_root, timeout_seconds).run(
                    ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-C", str(project_root), "--sandbox", sandbox, "--ask-for-approval", "never", prompt],
                    timeout_seconds,
                    cancel_event=self.cancel_event,
                )
                if result.exit_code != 0:
                    detail = result.stderr.strip() or result.stdout.strip()
                    raise ToolExecutionError(f"Codex falhou: {detail}")
                return result.stdout.strip()
            except ToolExecutionError as exc:
                if write_access or attempt == attempts - 1 or not self._is_transient(str(exc)):
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise ToolExecutionError("Codex não respondeu após as tentativas permitidas.")

    @staticmethod
    def _is_transient(detail: str) -> bool:
        normalized = detail.lower()
        return any(term in normalized for term in ("network", "connection", "dns", "timed out", "timeout", "429", "rate limit", "server error", "502", "503"))

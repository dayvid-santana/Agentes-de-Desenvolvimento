"""Coordena o ciclo de vida do observador local de checkpoints Git."""

from __future__ import annotations

import threading
from pathlib import Path

from dev_agent.agents.auto_commit_agent import AutoCommitAgent, AutoCommitResult
from dev_agent.config.models import DevAgentConfig
from dev_agent.errors import DevAgentError


class AutoCommitManager:
    """Mantém no máximo um observador ativo por processo da API local."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._root: Path | None = None
        self._last_results: list[AutoCommitResult] = []
        self._last_error: str | None = None

    def start(self, root: Path, config: DevAgentConfig) -> dict[str, object]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise DevAgentError("Já há um observador de checkpoints ativo neste processo.")
            self._root = root.resolve()
            self._stop_event = threading.Event()
            self._last_results = []
            self._last_error = None
            self._thread = threading.Thread(target=self._watch, args=(self._root, config, self._stop_event), daemon=True)
            self._thread.start()
        return self.status()

    def run_once(self, root: Path, config: DevAgentConfig) -> AutoCommitResult:
        return AutoCommitAgent(root, config).commit_if_ready()

    def stop(self) -> dict[str, object]:
        with self._lock:
            stopper = self._stop_event
            worker = self._thread
        if stopper is not None:
            stopper.set()
        if worker is not None:
            worker.join(timeout=5)
        return self.status()

    def status(self) -> dict[str, object]:
        with self._lock:
            active = bool(self._thread and self._thread.is_alive())
            return {
                "running": active,
                "project_root": str(self._root) if self._root else None,
                "last_results": [result.model_dump() for result in self._last_results],
                "last_error": self._last_error,
            }

    def _watch(self, root: Path, config: DevAgentConfig, stop_event: threading.Event) -> None:
        try:
            results = AutoCommitAgent(root, config).watch(stop_event)
            with self._lock:
                self._last_results = results
        except DevAgentError as exc:
            with self._lock:
                self._last_error = str(exc)

"""Persistência local do estado de planos e jobs dos agents."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Preservar status e resultados de tarefas assíncronas locais.

import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, Field

from dev_agent.core.models import AgentJob, TaskPlan


class JobState(BaseModel):
    plans: dict[str, TaskPlan] = Field(default_factory=dict)
    jobs: dict[str, AgentJob] = Field(default_factory=dict)


class JobStore:
    """Armazena planos e resumos locais; nunca grava prompts ou credenciais."""

    def __init__(self, path: Path | None = None) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DevAgent"
        self.path = path or base / "agent-jobs.json"

    def load(self) -> JobState:
        if not self.path.exists():
            return JobState()
        try:
            return JobState.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return JobState()

    def save(self, state: JobState) -> None:
        try:
            self._write(state)
        except PermissionError:
            self.path = Path(tempfile.gettempdir()) / "DevAgent" / "agent-jobs.json"
            self._write(state)

    def _write(self, state: JobState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._exclusive_lock():
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.path)

    @contextmanager
    def _exclusive_lock(self):
        lock_path = self.path.with_suffix(".lock")
        deadline = time.monotonic() + 5
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise OSError(f"Não foi possível obter lock do estado de jobs: {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

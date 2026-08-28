"""Persistência local do estado de planos e jobs dos agents."""
from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Preservar status e resultados de tarefas assíncronas locais.

import os
import tempfile
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
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self.path)

"""Contratos trocados entre orquestrador e subagents."""

from __future__ import annotations

# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Expor metadados dos agentes disponíveis na API local.
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Informar o comando de execução de cada agente.

from pathlib import Path

from pydantic import BaseModel, Field


class ContextPacket(BaseModel):
    project_name: str
    project_root: Path
    objective: str
    instructions: list[str] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)
    git_diff: str | None = None
    previous_summary: str | None = None
    file_contents: dict[str, str] = Field(default_factory=dict)


class SubAgentResult(BaseModel):
    agent: str
    summary: str
    files_read: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    tests_executed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    architecture_decision_required: bool = False
    next_actions: list[str] = Field(default_factory=list)


class AgentDescriptor(BaseModel):
    name: str
    description: str
    mode: str
    command: str


class ReviewFinding(BaseModel):
    severity: str
    message: str
    file: str | None = None
    line: int | None = None


class CommitSuggestion(BaseModel):
    message: str
    files: list[str]
    rationale: str

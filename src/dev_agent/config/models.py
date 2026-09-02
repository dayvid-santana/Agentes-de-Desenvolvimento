"""Modelos Pydantic para dev-agent.yaml."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectSettings(BaseModel):
    name: str
    author: str = "Dayvid Santana"


class DocumentationSettings(BaseModel):
    priority: list[str] = Field(default_factory=lambda: ["AGENTS.md", "docs/**", "README.md"])


class ContextSettings(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["src/**", "tests/**", "docs/**", "AGENTS.md", "README.md"])
    exclude: list[str] = Field(default_factory=lambda: [".git/**", ".venv/**", "venv/**", "node_modules/**", "dist/**", "build/**", "coverage/**", "__pycache__/**", "*.pyc", "*.log"])
    contextosAgentes: list[str] = Field(default_factory=lambda: ["agent-context/**"])
    max_files: int = Field(default=12, ge=1, le=100)
    max_file_chars: int = Field(default=16_000, ge=1_000)
    max_total_chars: int = Field(default=80_000, ge=5_000)
    dependency_depth: int = Field(default=1, ge=0, le=5)


class TestingSettings(BaseModel):
    command: str = "pytest"


class GitSettings(BaseModel):
    conventional_commits: bool = True
    review_staged: bool = True
    suggest_commit_split: bool = True


class HeaderSettings(BaseModel):
    enabled: bool = True
    author: str = "Dayvid Santana"
    date_format: str = "%d/%m/%Y"
    history: bool = True


class SecuritySettings(BaseModel):
    require_architecture_approval: bool = True
    require_destructive_command_approval: bool = True
    sensitive_patterns: list[str] = Field(default_factory=lambda: [".env", ".env.*", "credentials*", "secrets*", "*.pem", "*.key"])


class DevAgentConfig(BaseModel):
    project: ProjectSettings
    documentation: DocumentationSettings = Field(default_factory=DocumentationSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    testing: TestingSettings = Field(default_factory=TestingSettings)
    git: GitSettings = Field(default_factory=GitSettings)
    headers: HeaderSettings = Field(default_factory=HeaderSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

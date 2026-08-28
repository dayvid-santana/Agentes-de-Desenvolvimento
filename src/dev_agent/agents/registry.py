# dev-agent
# Autor: Dayvid Santana
# Criado em: 28/08/2026
# Editado em: 28/08/2026
# Objetivo: Carregar e consultar o catálogo único de Agents do projeto.
"""Registry declarativo de Agents, sem acoplamento ao orquestrador legado."""

from __future__ import annotations

import importlib
from pathlib import Path

import yaml

from dev_agent.core.models import AgentManifest


class AgentRegistry:
    """Lê ``agents/catalog.yaml`` e verifica os entrypoints declarados."""

    def __init__(self, catalog_path: Path | None = None) -> None:
        self.catalog_path = catalog_path or Path(__file__).resolve().parents[3] / "agents" / "catalog.yaml"
        self._manifests = self._load()

    def _load(self) -> dict[str, AgentManifest]:
        raw = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("agents"), list):
            raise ValueError(f"Catálogo inválido em {self.catalog_path}: esperado campo 'agents'.")
        manifests = [AgentManifest.model_validate(item) for item in raw["agents"]]
        duplicates = {item.id for item in manifests if sum(other.id == item.id for other in manifests) > 1}
        if duplicates:
            raise ValueError(f"IDs de Agent duplicados: {', '.join(sorted(duplicates))}.")
        return {item.id: item for item in manifests}

    def list(self) -> list[AgentManifest]:
        return sorted(self._manifests.values(), key=lambda item: item.id)

    def get(self, agent_id: str) -> AgentManifest:
        normalized = agent_id.strip().lower()
        for manifest in self._manifests.values():
            if normalized in {manifest.id, manifest.name, *manifest.aliases}:
                return manifest
        raise KeyError(f"Agent não encontrado: {agent_id}")

    def graph(self) -> dict[str, list[str]]:
        return {manifest.id: manifest.dependencies for manifest in self.list()}

    def doctor(self) -> list[dict[str, str]]:
        diagnostics: list[dict[str, str]] = []
        for manifest in self.list():
            missing = [dependency for dependency in manifest.dependencies if dependency not in self._manifests]
            if missing:
                diagnostics.append({"agent": manifest.id, "status": "error", "detail": f"Dependências ausentes: {', '.join(missing)}"})
                continue
            try:
                module = importlib.import_module(manifest.module)
                getattr(module, manifest.class_name)
            except (ImportError, AttributeError) as exc:
                diagnostics.append({"agent": manifest.id, "status": "error", "detail": str(exc)})
            else:
                diagnostics.append({"agent": manifest.id, "status": "ok", "detail": "Entry point disponível."})
        return diagnostics

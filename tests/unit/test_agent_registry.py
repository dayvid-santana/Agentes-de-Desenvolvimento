# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o AgentRegistry, o catálogo declarativo e o LegacyAgentAdapter.
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dev_agent.agents.base import SubAgent
from dev_agent.agents.legacy_adapter import LegacyAgentAdapter
from dev_agent.agents.registry import AgentRegistry
from dev_agent.core.models import AgentManifest, ContextPacket, SubAgentResult


def _packet() -> ContextPacket:
    return ContextPacket(project_name="Demo", project_root=Path("."), objective="Testar")


def test_registry_loads_the_real_catalog_without_duplicates_or_missing_entrypoints():
    registry = AgentRegistry()
    manifests = registry.list()
    assert len(manifests) >= 20
    assert len({item.id for item in manifests}) == len(manifests)
    assert all(item["status"] == "ok" for item in registry.doctor())


def test_registry_get_resolves_by_id_and_is_case_insensitive():
    registry = AgentRegistry()
    assert registry.get("context").class_name == "ContextAgent"
    assert registry.get("Context").id == "context"


def test_registry_get_raises_for_unknown_agent():
    with pytest.raises(KeyError):
        AgentRegistry().get("does-not-exist")


def test_registry_graph_maps_ids_to_declared_dependencies():
    graph = AgentRegistry().graph()
    assert graph["implementation"] == ["context", "requirements"]


def test_registry_rejects_duplicate_ids(tmp_path: Path):
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "agents": [
                    {"id": "dup", "name": "dup", "module": "dev_agent.agents.git_agent.agent", "class_name": "GitAgent", "purpose": "x", "mode": "read"},
                    {"id": "dup", "name": "dup", "module": "dev_agent.agents.git_agent.agent", "class_name": "GitAgent", "purpose": "x", "mode": "read"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicados"):
        AgentRegistry(catalog)


def test_registry_doctor_reports_missing_dependency(tmp_path: Path):
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "agents": [
                    {"id": "a", "name": "a", "module": "dev_agent.agents.git_agent.agent", "class_name": "GitAgent", "purpose": "x", "mode": "read", "dependencies": ["ghost"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    diagnostics = AgentRegistry(catalog).doctor()
    assert diagnostics == [{"agent": "a", "status": "error", "detail": "Dependências ausentes: ghost"}]


def test_manifest_descriptor_matches_the_agent_descriptor_shape():
    manifest = AgentManifest(id="x", name="x", module="m", class_name="C", purpose="Faz algo.", mode="read", invocation="dev-agent x")
    descriptor = manifest.descriptor()
    assert (descriptor.name, descriptor.description, descriptor.mode, descriptor.command) == ("x", "Faz algo.", "read", "dev-agent x")


class _LegacyStringAgent:
    name = "legacy-string"

    def run(self, packet: ContextPacket) -> str:
        return f"resumo para {packet.objective}"


class _LegacyStructuredAgent(SubAgent):
    name = "legacy-structured"

    def run(self, packet: ContextPacket) -> SubAgentResult:
        return SubAgentResult(agent="ignored", summary="ok", files_read=packet.relevant_files)


def test_legacy_adapter_wraps_string_returning_agents():
    result = LegacyAgentAdapter(_LegacyStringAgent()).run(_packet())
    assert result.agent == "legacy-string"
    assert "Testar" in result.summary


def test_legacy_adapter_preserves_structured_results_and_renames_agent():
    result = LegacyAgentAdapter(_LegacyStructuredAgent()).run(_packet())
    assert result.agent == "legacy-structured"
    assert result.summary == "ok"


def test_legacy_adapter_rejects_unsupported_return_types():
    class _Broken:
        name = "broken"

        def run(self, packet: ContextPacket) -> int:
            return 42

    with pytest.raises(TypeError, match="broken"):
        LegacyAgentAdapter(_Broken()).run(_packet())

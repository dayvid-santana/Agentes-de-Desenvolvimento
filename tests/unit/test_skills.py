# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Cobrir o catálogo de Skills reutilizadas pelos agentes.
from dev_agent.skills.registry import get_skill, list_skills


def test_skill_catalog_contains_the_prioritized_skills():
    names = {skill.name for skill in list_skills()}
    assert {"code-header", "code-documentation", "test-design", "bug-reproduction", "evidence-review"} <= names


def test_skill_instructions_are_available_by_name():
    assert "cabeçalho" in get_skill("code-header").description

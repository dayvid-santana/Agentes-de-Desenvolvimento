"""Catálogo de Skills internas aplicadas aos prompts dos agentes."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Centralizar as regras reutilizáveis dos agentes especializados.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str


_SKILLS = {
    "code-header": Skill(
        name="code-header",
        description="Insere cabeçalhos em arquivos novos sem alterar os existentes.",
        instructions="Use exclusivamente o HeaderService. Insira projeto, autor, data e objetivo apenas quando o arquivo não possuir cabeçalho; preserve todo cabeçalho existente.",
    ),
    "code-documentation": Skill(
        name="code-documentation",
        description="Documenta decisões e contratos não óbvios no código alterado.",
        instructions="Prefira docstrings e comentários curtos para regras de negócio, efeitos colaterais e contratos. Não documente o óbvio, não refatore e não modifique comportamento.",
    ),
    "test-design": Skill(
        name="test-design",
        description="Converte alterações em cenários de teste e regressão verificáveis.",
        instructions="Cubra o comportamento alterado, casos de borda e regressões prováveis. Reutilize o padrão de testes do projeto e não modifique código de produção.",
    ),
    "bug-reproduction": Skill(
        name="bug-reproduction",
        description="Transforma relatos de falha em reproduções verificáveis.",
        instructions="Separe pré-condições, passos, resultado observado, resultado esperado, teste de regressão e evidências ausentes. Não invente causas ou dados.",
    ),
    "evidence-review": Skill(
        name="evidence-review",
        description="Exige achados de revisão rastreáveis e não genéricos.",
        instructions="Para cada achado, informe severidade, evidência no diff ou contexto, arquivo ou trecho quando disponível, impacto e ação sugerida. Sem evidência suficiente, responda não aplicável.",
    ),
}


def get_skill(name: str) -> Skill:
    return _SKILLS[name]


def list_skills() -> list[Skill]:
    return list(_SKILLS.values())

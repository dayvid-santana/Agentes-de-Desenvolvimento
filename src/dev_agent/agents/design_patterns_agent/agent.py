# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Analisar padrões de projeto somente com evidências do contexto selecionado.
"""Análise especializada de padrões de projeto."""

from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class DesignPatternsAgent(ReadOnlySpecialistAgent):
    name = "design_patterns"
    specialty = "padrões de projeto, coesão, acoplamento e extensibilidade"
    instructions = (
        "Identifique somente padrões sustentados pelo contexto. Para cada sugestão, informe o problema "
        "concreto, os arquivos envolvidos, uma alternativa simples e os trade-offs. Não recomende "
        "padrões apenas por preferência ou estética."
    )

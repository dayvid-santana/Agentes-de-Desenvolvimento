"""Análise especializada da qualidade e cobertura."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de qualidade em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class QualityAgent(ReadOnlySpecialistAgent):
    name = "quality"
    specialty = "lacunas de testes unitários, integração e casos de borda"
    instructions = "Liste os cenários de teste ausentes mais importantes e relacione-os à alteração observada."

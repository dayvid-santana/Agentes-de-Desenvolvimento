"""Análise especializada de desempenho."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de desempenho em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class PerformanceAgent(ReadOnlySpecialistAgent):
    name = "performance"
    specialty = "N+1, I/O, loops custosos, cache e gargalos de execução"
    instructions = "Diferencie gargalos comprováveis de hipóteses e sugira como medir cada hipótese."

"""Análise especializada de observabilidade."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de observabilidade em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class ObservabilityAgent(ReadOnlySpecialistAgent):
    name = "observability"
    specialty = "logs seguros, métricas, rastreamento e mensagens de erro acionáveis"
    instructions = "Sugira instrumentação mínima e não permita dados sensíveis em logs."

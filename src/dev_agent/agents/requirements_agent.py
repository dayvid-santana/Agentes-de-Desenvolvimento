"""Análise de requisitos e critérios de aceite."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de requisitos em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class RequirementsAgent(ReadOnlySpecialistAgent):
    name = "requirements"
    specialty = "requisitos, critérios de aceite, casos de borda e riscos de escopo"
    instructions = "Transforme o pedido em critérios verificáveis e destaque ambiguidades que possam afetar a implementação."

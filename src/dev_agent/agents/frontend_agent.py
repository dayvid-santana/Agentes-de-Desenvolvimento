"""Análise especializada de interface."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de frontend em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class FrontendAgent(ReadOnlySpecialistAgent):
    name = "frontend"
    specialty = "acessibilidade, responsividade, consistência visual e estados de interface"
    instructions = "Quando não houver interface no contexto, registre que a análise não se aplica em vez de inventar problemas."

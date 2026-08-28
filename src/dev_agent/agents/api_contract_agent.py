"""Análise especializada de contratos de API."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de contratos de API em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class ApiContractAgent(ReadOnlySpecialistAgent):
    name = "api_contract"
    specialty = "compatibilidade de endpoints, schemas, status HTTP, paginação e contratos públicos"
    instructions = "Identifique quebras de compatibilidade e proponha uma mitigação objetiva quando aplicável."

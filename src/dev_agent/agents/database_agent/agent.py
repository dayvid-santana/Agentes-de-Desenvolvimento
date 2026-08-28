"""Análise especializada do banco de dados."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de banco de dados em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class DatabaseAgent(ReadOnlySpecialistAgent):
    name = "database"
    specialty = "migrations, integridade, índices, consultas, concorrência e rollback de dados"
    instructions = "Avalie somente impactos de persistência que a mudança realmente introduz ou pode introduzir."

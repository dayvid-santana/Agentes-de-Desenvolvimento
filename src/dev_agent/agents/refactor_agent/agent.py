"""Análise especializada da refatoração."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de refatoração em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class RefactorAgent(ReadOnlySpecialistAgent):
    name = "refactor"
    specialty = "refatorações pequenas, seguras e com cobertura de testes"
    instructions = "Separe refatorações necessárias para a tarefa das melhorias opcionais que devem ficar fora do escopo."

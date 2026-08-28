"""Análise especializada de dependências."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de dependências em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class DependencyAgent(ReadOnlySpecialistAgent):
    name = "dependency"
    specialty = "dependências desnecessárias, duplicadas, vulneráveis ou desatualizadas"
    instructions = "Não recomende atualização especulativa; destaque somente dependências visíveis no contexto ou diff."

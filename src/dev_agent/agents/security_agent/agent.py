"""Análise especializada da segurança."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de segurança em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class SecurityAgent(ReadOnlySpecialistAgent):
    name = "security"
    specialty = "autenticação, autorização, validação de entrada, segredos e vulnerabilidades comuns"
    instructions = "Priorize falhas exploráveis e exposição de dados; indique severidade apenas quando houver evidência no diff ou contexto."

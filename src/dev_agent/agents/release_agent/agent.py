"""Análise especializada do release."""
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Isolar o agente de release em módulo próprio.
from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class ReleaseAgent(ReadOnlySpecialistAgent):
    name = "release"
    specialty = "versão, changelog, migrations, configuração e checklist de publicação"
    instructions = "Produza somente itens de release pertinentes à alteração atual."

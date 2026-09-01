# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Orientar a modelagem de código sem alterar arquivos do projeto.
"""Análise especializada para modelagem de código."""

from dev_agent.agents.specialist_base import ReadOnlySpecialistAgent


class CodeModelingAgent(ReadOnlySpecialistAgent):
    name = "code_modeling"
    specialty = "modelagem de domínio, responsabilidades, interfaces, contratos e pontos de extensão"
    instructions = (
        "Produza uma orientação autocontida, pronta para copiar em outro chat. Use exatamente as seções: "
        "Contexto observado, Modelo proposto, Componentes e responsabilidades, Contratos e dados, Estrutura de "
        "arquivos, Pontos de extensão para novas features, Decisões e trade-offs, Perguntas em aberto e Próximo "
        "prompt sugerido. Distinga fatos observados de hipóteses. Inclua pseudocódigo apenas quando esclarecer a "
        "modelagem e não proponha alterações diretas nos arquivos."
    )

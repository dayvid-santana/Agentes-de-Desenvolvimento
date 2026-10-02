"""Percorre a aplicação web como usuário e devolve cobertura com evidências."""
from __future__ import annotations

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.tools.application_exploration import FerramentaExploracaoAplicacao


class ExploradorAplicacaoAgent(SubAgent):
    name = "explorador_aplicacao"

    def __init__(self, ferramenta: FerramentaExploracaoAplicacao) -> None:
        self.ferramenta = ferramenta

    def run(self, packet: ContextPacket) -> SubAgentResult:
        relatorio = self.ferramenta.executar(packet.objective)
        cobertura = "não calculada" if relatorio.percentualExecucao is None else f"{relatorio.percentualExecucao:.1f}%"
        assertivas = "não configurada" if relatorio.percentualAssertivo is None else f"{relatorio.percentualAssertivo:.1f}%"
        resumo = (
            f"Exploração {relatorio.status}: {relatorio.paginasVisitadas}/{relatorio.paginasDescobertas} páginas "
            f"visitadas; {relatorio.controlesExercitados}/{relatorio.controlesDescobertos} controles exercitados "
            f"({cobertura} da cobertura de execução); assertivas explícitas aprovadas: {assertivas}; "
            f"{len(relatorio.achados)} achado(s)."
        )
        avisos = [
            f"[{achado.severidade.upper()}] {achado.titulo} — {achado.url or 'sem URL'}"
            for achado in relatorio.achados[:30]
        ]
        proximas = []
        if relatorio.limitacoes:
            proximas.extend(relatorio.limitacoes[:5])
        if relatorio.achados:
            proximas.append("Reproduzir os achados com os passos e artefatos do relatório.")
        if relatorio.percentualAssertivo is None:
            proximas.append("Configure jornadas com expectativas de negócio em testeAplicacao.jornadas para validar resultados funcionais.")
        return SubAgentResult(
            agent=self.name,
            summary=resumo,
            files_read=packet.relevant_files,
            tests_executed=[f"Playwright {self.ferramenta.configuracao.motor}: exploração de interface web"],
            warnings=avisos + relatorio.limitacoes[:10],
            relatorioAplicacao=relatorio,
            next_actions=proximas,
        )

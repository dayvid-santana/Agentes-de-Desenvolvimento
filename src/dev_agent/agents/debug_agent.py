# dev-agent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Diagnosticar falhas com evidências verificáveis.
# DevAgent-Task: debug-evidence-20260828
"""Diagnóstico de falhas baseado em testes, diff e contexto selecionado."""
from __future__ import annotations

import re

from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.errors import ToolExecutionError
from dev_agent.providers.base import LLMProvider
from dev_agent.tools.tests import TestResult, TestTool


class DebugAgent(SubAgent):
    """Investiga problemas sem alterar arquivos do projeto."""

    name = "debug"

    def __init__(self, provider: LLMProvider, tests: TestTool) -> None:
        self.provider = provider
        self.tests = tests

    def run(self, packet: ContextPacket) -> SubAgentResult:
        test_result, test_error = self._run_tests()
        evidence = self._evidence(packet, test_result, test_error)
        summary = self.provider.run(
            f"""Você é o DebugAgent do DevAgent. Investigue o problema abaixo usando somente as evidências fornecidas.
Não invente causas, arquivos, linhas ou resultados de testes. Não altere arquivos. Quando a evidência for insuficiente,
diga explicitamente o que falta para confirmar a causa. Responda em português, neste formato conciso:

Diagnóstico: confirmado, mais provável ou bloqueado.
Evidências: fatos observados, com arquivos ou trechos de saída quando existirem.
Hipóteses priorizadas: no máximo três, cada uma com a evidência que a sustenta.
Próxima ação: o menor passo concreto para confirmar ou corrigir.

Objetivo informado:
{packet.objective}

Evidências coletadas:
{evidence}

Arquivos de contexto:
{self._context(packet)}""",
            packet.project_root,
            write_access=False,
        )
        warnings = []
        if test_error:
            warnings.append(test_error)
        elif test_result and test_result.exit_code != 0:
            warnings.append("A suíte de testes configurada falhou; consulte as evidências no diagnóstico.")
        next_actions = ["Fornecer o traceback completo ou os passos de reprodução."] if test_error else ["Executar a próxima ação indicada no diagnóstico."]
        return SubAgentResult(
            agent=self.name,
            summary=summary,
            files_read=packet.relevant_files,
            tests_executed=[test_result.command] if test_result else [],
            warnings=warnings,
            next_actions=next_actions,
        )

    def _run_tests(self) -> tuple[TestResult | None, str | None]:
        try:
            return self.tests.run(), None
        except ToolExecutionError as exc:
            return None, f"Não foi possível executar a suíte configurada: {exc}"

    def _evidence(self, packet: ContextPacket, test_result: TestResult | None, test_error: str | None) -> str:
        parts = [f"Diff atual:\n{packet.git_diff or 'Nenhuma alteração local detectada.'}"]
        if test_error:
            parts.append(test_error)
        elif test_result:
            output = self._redact(f"{test_result.stdout}\n{test_result.stderr}").strip()
            parts.append(
                f"Teste executado: {test_result.command}\n"
                f"Exit code: {test_result.exit_code}\n"
                f"Resultado: {test_result.passed or 0} aprovados, {test_result.failed or 0} falhos.\n"
                f"Saída relevante:\n{output[-6_000:] or '(sem saída)'}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _context(packet: ContextPacket) -> str:
        return "\n\n".join(f"### {name}\n{text}" for name, text in packet.file_contents.items()) or "Nenhum arquivo selecionado."

    @staticmethod
    def _redact(output: str) -> str:
        return re.sub(r"(?im)^.*(?:password|passwd|secret|api[_-]?key|token)\s*[:=].*$", "[linha potencialmente sensível ocultada]", output)

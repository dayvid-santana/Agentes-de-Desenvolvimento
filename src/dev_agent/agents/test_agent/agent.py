"""Subagente de testes configuráveis."""
from __future__ import annotations
from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.tools.tests import TestTool

class TestAgent(SubAgent):
    name = "test"
    def __init__(self, tests: TestTool) -> None: self.tests = tests
    def run(self, packet: ContextPacket) -> SubAgentResult:
        result = self.tests.run()
        summary = f"Testes {'aprovados' if result.exit_code == 0 else 'falharam'} (exit code {result.exit_code})."
        warnings = [] if result.exit_code == 0 else [(result.stderr or result.stdout)[-2000:]]
        return SubAgentResult(agent=self.name, summary=summary, tests_executed=[result.command], warnings=warnings, next_actions=[] if result.exit_code == 0 else ["Investigar falhas de teste."])

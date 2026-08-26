"""Triagem inicial de erros com hipóteses priorizadas."""
from __future__ import annotations
from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, SubAgentResult

class DebugAgent(SubAgent):
    name = "debug"
    def run(self, packet: ContextPacket) -> SubAgentResult:
        text = packet.objective.lower()
        hypotheses = ["Hipótese 1 — alta probabilidade: falha no fluxo ou nos dados citados.", "Hipótese 2 — média probabilidade: dependência, configuração ou ambiente divergente.", "Hipótese 3 — baixa probabilidade: regressão fora do escopo imediato."]
        if "traceback" in text or "pytest" in text: hypotheses[0] = "Hipótese 1 — alta probabilidade: o traceback aponta para a alteração ou teste mais recente."
        return SubAgentResult(agent=self.name, summary="\n".join(hypotheses), files_read=packet.relevant_files, next_actions=["Executar o teste ou reproduzir o erro."])

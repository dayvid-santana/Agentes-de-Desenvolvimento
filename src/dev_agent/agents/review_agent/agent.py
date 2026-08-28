"""Revisão determinística inicial; pode receber o Codex posteriormente."""
from __future__ import annotations
import re
from dev_agent.agents.base import SubAgent
from dev_agent.core.models import ContextPacket, ReviewFinding, SubAgentResult
from dev_agent.providers.base import LLMProvider

class ReviewAgent(SubAgent):
    name = "review"
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    def run(self, packet: ContextPacket) -> SubAgentResult:
        findings = self.findings(packet.git_diff or "")
        summary = "Nenhum problema objetivo identificado." if not findings else "\n".join(f"[{item.severity}] {item.message}" for item in findings)
        if self.provider and packet.git_diff:
            review = self.provider.run(f"""Você é o ReviewAgent. Revise somente este git diff de {packet.project_name}. Priorize bugs reais, regressões, segurança, arquitetura, testes e regras de AGENTS.md. Classifique cada achado como CRITICAL, HIGH, MEDIUM, LOW ou INFO; não faça comentários cosméticos.\n\n{packet.git_diff}""", packet.project_root, write_access=False)
            summary = f"{summary}\n\nRevisão Codex:\n{review}"
        return SubAgentResult(agent=self.name, summary=summary, files_read=packet.relevant_files, warnings=[item.message for item in findings if item.severity in {"CRITICAL", "HIGH", "MEDIUM"}])
    def findings(self, diff: str) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        if re.search(r"(?i)(password|api[_-]?key|secret)\s*=\s*['\"]\w+", diff):
            findings.append(ReviewFinding(severity="CRITICAL", message="Possível segredo literal introduzido no diff."))
        if re.search(r"^\+.*(git reset --hard|git clean -fd|git push --force)", diff.lower(), re.MULTILINE):
            findings.append(ReviewFinding(severity="HIGH", message="Comando Git destrutivo introduzido."))
        return findings

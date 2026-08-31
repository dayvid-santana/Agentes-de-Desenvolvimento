"""Análise Git e plano de Conventional Commits sem criar um commit."""
from __future__ import annotations
from pathlib import Path
from dev_agent.core.models import CommitSuggestion
from dev_agent.errors import DevAgentError
from dev_agent.providers.base import LLMProvider
from dev_agent.tools.filesystem import FileSystem
from dev_agent.tools.git import GitTool

_MAX_DIFF_CHARS = 12000
_MAX_NEW_FILE_CHARS = 4000


class GitAgent:
    def __init__(self, root: Path, provider: LLMProvider | None = None) -> None:
        self.root = root
        self.git = GitTool(root)
        self.files = FileSystem(root)
        self.provider = provider

    def commit_plan(self) -> list[CommitSuggestion]:
        entries = self._status_entries()
        if not entries:
            return []
        tests = [item for item in entries if item[1].startswith("tests/") or "test_" in item[1]]
        docs = [item for item in entries if item[1].lower().endswith((".md", ".rst"))]
        used = {item[1] for item in (*tests, *docs)}
        code = [item for item in entries if item[1] not in used]
        result: list[CommitSuggestion] = []
        if code:
            result.append(self._suggest(code, "feat", "Arquivos de implementação devem formar um commit coeso."))
        if tests:
            result.append(self._suggest(tests, "test", "Testes foram separados para facilitar revisão; podem ser unidos ao commit funcional se forem inseparáveis."))
        if docs:
            result.append(self._suggest(docs, "docs", "Documentação é semanticamente distinta."))
        return result

    def _status_entries(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in self.git.status().splitlines():
            if line.startswith("##") or len(line) <= 3:
                continue
            entries.append((line[:2], line[3:].strip()))
        return entries

    def _suggest(self, entries: list[tuple[str, str]], default_type: str, default_rationale: str) -> CommitSuggestion:
        files = [path for _, path in entries]
        default = CommitSuggestion(message=f"{default_type}(scope): descreve a alteração principal", files=files, rationale=default_rationale)
        diff_context = self._diff_context(entries)
        if not self.provider or not diff_context.strip():
            return default
        try:
            response = self.provider.run(
                f"""Você é o GitAgent do DevAgent. Com base SOMENTE no diff real abaixo, gere uma sugestão de commit no padrão Conventional Commits. Responda em português, exatamente neste formato, sem texto adicional:

MENSAGEM: <tipo>(<escopo>): <descrição curta e específica no imperativo>
JUSTIFICATIVA: <1-2 frases sobre por que estes arquivos formam um commit coeso>

Tipo sugerido (ajuste apenas se o diff indicar claramente outro): {default_type}
Arquivos deste grupo: {", ".join(files)}

Diff:
{diff_context[:_MAX_DIFF_CHARS]}""",
                self.root,
                write_access=False,
            )
        except DevAgentError:
            return default
        message, rationale = self._parse(response)
        return CommitSuggestion(message=message or default.message, files=files, rationale=rationale or default.rationale)

    def _diff_context(self, entries: list[tuple[str, str]]) -> str:
        tracked = [path for code, path in entries if code.strip() != "??"]
        parts = []
        if tracked:
            diff = self.git.diff_paths(tracked)
            if diff.strip():
                parts.append(diff)
        for code, path in entries:
            if code.strip() != "??":
                continue
            try:
                content = self.files.read_text(path, max_chars=_MAX_NEW_FILE_CHARS).content
            except (OSError, UnicodeDecodeError):
                parts.append(f"### novo arquivo (binário ou ilegível): {path}")
            else:
                parts.append(f"### novo arquivo: {path}\n{content}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse(response: str) -> tuple[str, str]:
        message, rationale = "", ""
        for line in response.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("MENSAGEM:"):
                message = stripped.split(":", 1)[1].strip()
            elif stripped.upper().startswith("JUSTIFICATIVA:"):
                rationale = stripped.split(":", 1)[1].strip()
        return message, rationale

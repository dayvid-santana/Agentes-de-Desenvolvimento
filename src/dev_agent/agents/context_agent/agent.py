"""Seleção limitada e progressiva do contexto do projeto."""
# dev-agent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Priorizar contexto pertinente para análises e diagnósticos.
# DevAgent-Task: debug-evidence-20260828
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Selecionar código, testes e dependências locais relevantes.
# DevAgent-Task: context-code-selection-20260828
# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Incluir arquivos alterados ainda não rastreados pelo Git.
# DevAgent
# Autor: Dayvid Santana
# Data: 02/09/2026
# Objetivo: Selecionar contextos especializados somente quando forem relevantes.
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from dev_agent.agents.base import SubAgent
from dev_agent.config.models import DevAgentConfig
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.errors import PathOutsideProjectError
from dev_agent.security.redaction import SensitiveDataRedactor
from dev_agent.tools.filesystem import FileSystem
from dev_agent.tools.search import FileSearchTool


class ContextAgent(SubAgent):
    name = "context"
    _referenciaMarkdown = re.compile(r"\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)")

    def __init__(self, root: Path, config: DevAgentConfig) -> None:
        self.root, self.config = root, config
        self.files = FileSystem(root)
        self.search = FileSearchTool(
            root,
            config.context.exclude + config.security.sensitive_patterns,
            config.context.include,
        )

    def build(
        self,
        objective: str,
        previous_summary: str | None = None,
        git_diff: str | None = None,
        changed_files: list[str] | None = None,
    ) -> ContextPacket:
        docs = self._documentation()
        terms = re.findall(r"[\wÀ-ÿ_-]{3,}", objective.lower())
        explicit = self._explicit_paths(objective)
        candidates = list(
            dict.fromkeys(
                self.search.find_names(terms, self.config.context.max_files)
                + self.search.search_text(terms, self.config.context.max_files)
            )
        )
        changed = self._existing_paths([*self._changed_files(git_diff or ""), *(changed_files or [])])
        arquivosEscopo = self._agentsDoEscopo([*explicit, *changed, *candidates])
        arquivosInstrucoes = list(
            dict.fromkeys(
                [
                    *self._agentsRaiz(),
                    *arquivosEscopo,
                    *self._contextosEspecializados(terms, [*explicit, *changed, *candidates], arquivosEscopo),
                ]
            )
        )
        relevant_docs = [item for item in candidates if item in docs and item not in arquivosInstrucoes]
        code_and_tests = [item for item in [*explicit, *changed, *candidates] if item not in docs]
        related = self._related_files([*explicit, *changed, *code_and_tests])
        fallback_docs = self._documentacaoBase(docs, [*explicit, *changed, *code_and_tests, *related])
        selected = list(
            dict.fromkeys(
                [
                    *arquivosInstrucoes,
                    *explicit,
                    *changed,
                    *code_and_tests,
                    *related,
                    *relevant_docs,
                    *fallback_docs,
                ]
            )
        )[: self.config.context.max_files]
        contents: dict[str, str] = {}
        budget = self.config.context.max_total_chars
        for relative in selected:
            if budget <= 0:
                break
            try:
                item = self.files.read_text(relative, min(self.config.context.max_file_chars, budget))
            except (OSError, UnicodeDecodeError):
                continue
            redacted = SensitiveDataRedactor.redact(item.content) or ""
            contents[relative] = redacted
            budget -= len(redacted)
        instructions = [contents[item] for item in arquivosInstrucoes if item in contents]
        return ContextPacket(
            project_name=self.config.project.name,
            project_root=self.root,
            objective=objective,
            instructions=instructions,
            relevant_files=list(contents),
            documentation=docs,
            git_diff=SensitiveDataRedactor.redact(git_diff),
            previous_summary=previous_summary,
            file_contents=contents,
        )

    def run(self, packet: ContextPacket) -> SubAgentResult:
        return SubAgentResult(agent=self.name, summary=f"Contexto selecionou {len(packet.relevant_files)} arquivo(s).", files_read=packet.relevant_files)

    def _explicit_paths(self, objective: str) -> list[str]:
        paths = re.findall(r"(?<!\w)(?:[\w.-]+[\\/])+[\w.-]+", objective)
        return self._existing_paths([item.replace("\\", "/") for item in paths], allow_outside_include=True)

    def _existing_paths(self, paths: list[str], allow_outside_include: bool = False) -> list[str]:
        found: list[str] = []
        for relative in paths:
            try:
                path = self.files.resolve(relative)
            except PathOutsideProjectError:
                continue
            if not path.is_file() or self.search.is_excluded(path):
                continue
            if not allow_outside_include and not self.search.allows(path):
                continue
            found.append(path.relative_to(self.root).as_posix())
        return list(dict.fromkeys(found))

    def _related_files(self, seeds: list[str]) -> list[str]:
        related: list[str] = []
        frontier = [item for item in seeds if item.endswith(".py")]
        visited = set(frontier)
        for _ in range(self.config.context.dependency_depth):
            next_frontier: list[str] = []
            for relative in frontier:
                try:
                    source = self.files.read_text(relative, self.config.context.max_file_chars).content
                except (OSError, UnicodeDecodeError):
                    continue
                candidates = [*self._imported_modules(relative, source), *self._matching_tests(relative)]
                for candidate in self._existing_paths(candidates):
                    if candidate in visited:
                        continue
                    visited.add(candidate)
                    related.append(candidate)
                    if candidate.endswith(".py"):
                        next_frontier.append(candidate)
            frontier = next_frontier
            if not frontier:
                break
        return related

    def _imported_modules(self, relative: str, source: str) -> list[str]:
        modules = re.findall(r"(?m)^\s*from\s+([.\w]+)\s+import\s+", source)
        modules.extend(re.findall(r"(?m)^\s*import\s+([\w.]+)", source))
        candidates: list[str] = []
        current_dir = Path(relative).parent
        for module in modules:
            dots = len(module) - len(module.lstrip("."))
            if dots:
                base = current_dir
                for _ in range(max(0, dots - 1)):
                    base = base.parent
                module_path = Path(module[dots:].replace(".", "/"))
                bases = [base]
            else:
                module_path = Path(module.replace(".", "/"))
                bases = [Path(), Path("src")]
            for base in bases:
                candidates.extend(
                    [
                        (base / module_path).with_suffix(".py").as_posix(),
                        (base / module_path / "__init__.py").as_posix(),
                    ]
                )
        return candidates

    def _matching_tests(self, relative: str) -> list[str]:
        stem = Path(relative).stem
        candidates: list[Path] = [Path("tests") / f"test_{stem}.py", Path("tests") / f"{stem}_test.py"]
        candidates.extend(self.root.glob(f"tests/**/test_{stem}.py"))
        return [
            str(item.relative_to(self.root)).replace("\\", "/") if item.is_absolute() else str(item).replace("\\", "/")
            for item in candidates
        ]

    @staticmethod
    def _changed_files(git_diff: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"^\+\+\+ b/(.+)$", git_diff, re.MULTILINE)))

    def _documentation(self) -> list[str]:
        found: list[str] = []
        found.extend(self._agentsRaiz())
        found.extend(self._agentsAninhados())
        if (self.root / "README.md").is_file():
            found.append("README.md")
        docs_dir = self.root / "docs"
        if docs_dir.is_dir():
            found.extend(str(path.relative_to(self.root)).replace("\\", "/") for path in docs_dir.rglob("*") if path.is_file())
        return found

    def _agentsRaiz(self) -> list[str]:
        return ["AGENTS.md"] if (self.root / "AGENTS.md").is_file() else []

    @staticmethod
    def _documentacaoBase(documentos: list[str], arquivosTecnicos: list[str]) -> list[str]:
        if arquivosTecnicos:
            return []
        return ["README.md"] if "README.md" in documentos else []

    def _agentsAninhados(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.root)).replace("\\", "/")
            for path in self.root.rglob("AGENTS.md")
            if path.parent != self.root
        )

    def _agentsDoEscopo(self, caminhos: list[str]) -> list[str]:
        selecionados: list[str] = []
        for agente in self._agentsAninhados():
            diretorio = Path(agente).parent.as_posix()
            if any(caminho == agente or caminho.startswith(f"{diretorio}/") for caminho in caminhos):
                selecionados.append(agente)
        return selecionados

    def _contextosEspecializados(self, termos: list[str], caminhos: list[str], arquivosEscopo: list[str]) -> list[str]:
        selecionados: list[str] = []
        for instrucao in [*self._agentsRaiz(), *arquivosEscopo]:
            try:
                conteudo = self.files.read_text(instrucao, self.config.context.max_file_chars).content
            except (OSError, UnicodeDecodeError):
                continue
            for linha in conteudo.splitlines():
                for referencia in self._referenciaMarkdown.findall(linha):
                    caminho = self._caminhoContexto(instrucao, referencia)
                    if caminho and self._contextoRelevante(linha, caminho, termos, caminhos):
                        selecionados.append(caminho)
        return list(dict.fromkeys(selecionados))

    def _caminhoContexto(self, instrucao: str, referencia: str) -> str | None:
        try:
            caminho = self.files.resolve(Path(instrucao).parent / referencia)
        except PathOutsideProjectError:
            return None
        if not caminho.is_file() or not self._pertenceAosContextosAgentes(caminho):
            return None
        return caminho.relative_to(self.root).as_posix()

    def _pertenceAosContextosAgentes(self, caminho: Path) -> bool:
        relativo = caminho.relative_to(self.root).as_posix()
        return any(fnmatch.fnmatch(relativo, padrao) for padrao in self.config.context.contextosAgentes)

    @staticmethod
    def _contextoRelevante(linha: str, caminho: str, termos: list[str], caminhos: list[str]) -> bool:
        termosReferencia = set(re.findall(r"[\w_-]{3,}", f"{linha} {caminho}".lower()))
        termosTarefa = set(termos)
        for arquivo in caminhos:
            termosTarefa.update(re.findall(r"[\w_-]{3,}", arquivo.lower()))
        return any(
            termo == referencia
            or termo.startswith(referencia)
            or referencia.startswith(termo)
            or (len(termo) >= 6 and len(referencia) >= 6 and termo[:6] == referencia[:6])
            for termo in termosTarefa
            for referencia in termosReferencia
        )

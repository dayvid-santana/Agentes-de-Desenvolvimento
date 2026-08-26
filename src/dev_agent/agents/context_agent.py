"""Seleção progressiva e limitada de contexto do projeto."""
from __future__ import annotations
import re
from pathlib import Path

from dev_agent.agents.base import SubAgent
from dev_agent.config.models import DevAgentConfig
from dev_agent.core.models import ContextPacket, SubAgentResult
from dev_agent.tools.filesystem import FileSystem
from dev_agent.tools.search import FileSearchTool

class ContextAgent(SubAgent):
    name = "context"
    def __init__(self, root: Path, config: DevAgentConfig) -> None:
        self.root, self.config = root, config
        self.files = FileSystem(root)
        self.search = FileSearchTool(root, config.context.exclude + config.security.sensitive_patterns)

    def build(self, objective: str, previous_summary: str | None = None, git_diff: str | None = None) -> ContextPacket:
        instructions, docs = self._documentation()
        terms = re.findall(r"[\wÀ-ÿ_-]{3,}", objective.lower())
        candidates = list(dict.fromkeys(self.search.find_names(terms, self.config.context.max_files) + self.search.search_text(terms, self.config.context.max_files)))
        preferred = [item for item in docs if item not in candidates]
        selected = (preferred + candidates)[:self.config.context.max_files]
        contents: dict[str, str] = {}
        budget = self.config.context.max_total_chars
        for relative in selected:
            if budget <= 0:
                break
            try:
                item = self.files.read_text(relative, min(self.config.context.max_file_chars, budget))
            except (OSError, UnicodeDecodeError):
                continue
            contents[relative] = item.content
            budget -= len(item.content)
        return ContextPacket(project_name=self.config.project.name, project_root=self.root, objective=objective, instructions=instructions, relevant_files=list(contents), documentation=docs, git_diff=git_diff, previous_summary=previous_summary, file_contents=contents)

    def run(self, packet: ContextPacket) -> SubAgentResult:
        return SubAgentResult(agent=self.name, summary=f"Contexto selecionou {len(packet.relevant_files)} arquivo(s).", files_read=packet.relevant_files)

    def _documentation(self) -> tuple[list[str], list[str]]:
        found: list[str] = []
        if (self.root / "AGENTS.md").is_file():
            found.append("AGENTS.md")
        nested_agents = sorted(str(path.relative_to(self.root)).replace("\\", "/") for path in self.root.rglob("AGENTS.md") if path.parent != self.root)
        found.extend(nested_agents)
        if (self.root / "README.md").is_file():
            found.append("README.md")
        docs_dir = self.root / "docs"
        if docs_dir.is_dir():
            found.extend(str(path.relative_to(self.root)).replace("\\", "/") for path in docs_dir.rglob("*") if path.is_file())
        instructions: list[str] = []
        for item in found:
            if item.endswith("AGENTS.md"):
                try:
                    instructions.append(self.files.read_text(item, self.config.context.max_file_chars).content)
                except OSError:
                    pass
        return instructions, found

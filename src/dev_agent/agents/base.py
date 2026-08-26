"""Base pequena para subagents."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dev_agent.core.models import ContextPacket, SubAgentResult

class SubAgent(ABC):
    name: str
    @abstractmethod
    def run(self, packet: ContextPacket) -> SubAgentResult: ...

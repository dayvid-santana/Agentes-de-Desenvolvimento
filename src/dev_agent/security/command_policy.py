"""Bloqueia comandos destrutivos sem confirmação explícita."""
from __future__ import annotations

import re

from dev_agent.errors import UnsafeCommandError

class CommandPolicy:
    def ensure_safe(self, command: str, confirmed: bool = False) -> None:
        normalized = " ".join(command.lower().split())
        destructive = (
            bool(re.search(r"\bgit\s+reset\b.*(?:--hard|-hard)\b", normalized))
            or self._git_clean_is_destructive(normalized)
            or bool(re.search(r"\bgit\s+push\b.*(?:--force|-f)\b", normalized))
            or bool(re.search(r"\bgit\s+branch\s+-d\b", normalized))
            or self._deletes_files(normalized)
        )
        if destructive and not confirmed:
            raise UnsafeCommandError("Comando destrutivo bloqueado: requer confirmação explícita.")

    @staticmethod
    def _deletes_files(command: str) -> bool:
        words = set(re.findall(r"[^\s]+", command))
        if re.search(r"\b(?:rm|rmdir|del|erase|remove-item)\b", command):
            return bool(words & {"-r", "-rf", "-fr", "--recursive", "-recurse", "/s", "-f", "--force", "-force", "/q"})
        return False

    @staticmethod
    def _git_clean_is_destructive(command: str) -> bool:
        if not re.search(r"\bgit\s+clean\b", command):
            return False
        options = re.findall(r"(?:^|\s)(--[^\s]+|-[a-z]+)", command)
        joined = " ".join(options)
        return ("--force" in joined or any("f" in option[1:] for option in options if option.startswith("-"))) and (
            "--dirs" in joined or any("d" in option[1:] for option in options if option.startswith("-"))
        )

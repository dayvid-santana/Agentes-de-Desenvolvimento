"""Bloqueia comandos destrutivos sem confirmação explícita."""
from dev_agent.errors import UnsafeCommandError

DESTRUCTIVE_PATTERNS = ("git reset --hard", "git clean -fd", "git push --force", "git branch -d", "remove-item -recurse -force", "rm -rf")

class CommandPolicy:
    def ensure_safe(self, command: str, confirmed: bool = False) -> None:
        if any(pattern in command.lower() for pattern in DESTRUCTIVE_PATTERNS) and not confirmed:
            raise UnsafeCommandError("Comando destrutivo bloqueado: requer confirmação explícita.")

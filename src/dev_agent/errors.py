"""Erros de domínio apresentados de forma compreensível pela CLI."""


class DevAgentError(Exception):
    """Base para erros esperados do DevAgent."""


class ProjectNotFoundError(DevAgentError):
    """Não existe dev-agent.yaml acima do diretório informado."""


class InvalidProjectConfigError(DevAgentError):
    """A configuração YAML não é válida."""


class PathOutsideProjectError(DevAgentError):
    """Um caminho tentou escapar da raiz ativa."""


class ToolExecutionError(DevAgentError):
    """Uma ferramenta externa falhou."""


class UnsafeCommandError(DevAgentError):
    """Um comando requer confirmação explícita."""


class CodexUnavailableError(DevAgentError):
    """A CLI Codex não está disponível ou não pôde ser executada."""


class ArchitectureDecisionRequired(DevAgentError):
    """A tarefa exige uma escolha arquitetural do usuário."""


class InvalidStateTransitionError(DevAgentError):
    """A máquina de estados de uma tarefa recebeu uma transição de fase inválida."""


class TaskLoopDetectedError(DevAgentError):
    """A mesma fase da máquina de estados foi repetida além do limite configurado."""


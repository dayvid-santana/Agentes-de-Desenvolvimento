"""Cobertura do serviço local de checkpoints Git automáticos."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dev_agent.agents.auto_commit_agent import AutoCommitAgent
from dev_agent.config.loader import load_config, render_default_config
from dev_agent.tools.tests import TestResult as ResultadoTeste


class FakeTests:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls = 0

    def run(self) -> ResultadoTeste:
        self.calls += 1
        return ResultadoTeste(command="pytest", exit_code=self.exit_code, stdout="ok" if self.exit_code == 0 else "1 failed", stderr="")


def _repository(root: Path) -> Path:
    repository = root / "repo"
    repository.mkdir()
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "tests@example.invalid"],
        ["git", "config", "user.name", "Test Runner"],
    ):
        subprocess.run(command, cwd=repository, check=True, capture_output=True)
    (repository / "README.md").write_text("inicial\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: inicial"], cwd=repository, check=True, capture_output=True)
    return repository


def _config(repository: Path):
    content = render_default_config("Demo").replace("enabled: false", "enabled: true")
    (repository / "dev-agent.yaml").write_text(content, encoding="utf-8")
    return load_config(repository)


def test_auto_commit_creates_local_checkpoint_after_passing_tests(tmp_path: Path):
    repository = _repository(tmp_path)
    (repository / "servico.py").write_text("def executar(): return True\n", encoding="utf-8")
    tests = FakeTests()

    result = AutoCommitAgent(repository, _config(repository), tests=tests).commit_if_ready()

    assert result.committed and tests.calls == 1
    message = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=repository, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    assert message == "chore(checkpoint): salva alterações locais"


def test_auto_commit_does_not_commit_when_tests_fail(tmp_path: Path):
    repository = _repository(tmp_path)
    (repository / "servico.py").write_text("def executar(): return True\n", encoding="utf-8")

    result = AutoCommitAgent(repository, _config(repository), tests=FakeTests(exit_code=1)).commit_if_ready()

    assert not result.committed and "testes falharam" in result.reason.lower()
    status = subprocess.run(["git", "status", "--short"], cwd=repository, check=True, capture_output=True, text=True).stdout
    assert "?? servico.py" in status


def test_auto_commit_preserves_a_manually_staged_index(tmp_path: Path):
    repository = _repository(tmp_path)
    changed = repository / "README.md"
    changed.write_text("manual\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True, capture_output=True)

    result = AutoCommitAgent(repository, _config(repository), tests=FakeTests()).commit_if_ready()

    assert not result.committed and "índice git" in result.reason.lower()
    staged = subprocess.run(["git", "diff", "--staged", "--name-only"], cwd=repository, check=True, capture_output=True, text=True).stdout
    assert staged.strip() == "README.md"


def test_auto_commit_blocks_sensitive_paths(tmp_path: Path):
    repository = _repository(tmp_path)
    (repository / ".env.local").write_text("TOKEN=not-for-commit\n", encoding="utf-8")

    result = AutoCommitAgent(repository, _config(repository), tests=FakeTests()).commit_if_ready()

    assert not result.committed and "sensíveis" in result.reason
    assert result.warnings == [".env.local"]

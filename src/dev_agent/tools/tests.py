"""Abstração de execução do framework de testes configurado."""

from __future__ import annotations

import re
import shlex

from pydantic import BaseModel

from dev_agent.tools.terminal import TerminalTool


class TestResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: int | None = None
    failed: int | None = None


class TestTool:
    def __init__(self, terminal: TerminalTool, command: str) -> None:
        self.terminal = terminal
        self.command = command

    def run(self) -> TestResult:
        result = self.terminal.run(shlex.split(self.command, posix=False))
        output = f"{result.stdout}\n{result.stderr}"
        passed = _result_count(output, "passed")
        failed = _result_count(output, "failed")
        return TestResult(command=self.command, exit_code=result.exit_code, stdout=result.stdout, stderr=result.stderr, passed=passed, failed=failed)


def _result_count(output: str, label: str) -> int | None:
    match = re.search(r"(\d+)\s+" + label, output)
    return int(match.group(1)) if match else None


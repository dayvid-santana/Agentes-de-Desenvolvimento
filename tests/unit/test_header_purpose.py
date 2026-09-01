# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Validar a geração de propósitos específicos para cabeçalhos.
from pathlib import Path

import pytest

from dev_agent.errors import DevAgentError
from dev_agent.headers.purpose_service import HeaderPurposeService


class FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.write_access = True

    def available(self) -> bool:
        return True

    def run(self, prompt, project_root, *, write_access=False, timeout_seconds=600):
        self.write_access = write_access
        return self.response


def test_generates_a_purpose_per_file_without_write_access(tmp_path: Path):
    provider = FakeProvider('{"src/service.py": "Centraliza a validação das faturas recebidas."}')

    purposes = HeaderPurposeService(provider).gerarPropositos({"src/service.py": "def validate(): pass"}, tmp_path)

    assert purposes == {"src/service.py": "Centraliza a validação das faturas recebidas."}
    assert not provider.write_access


def test_rejects_the_generic_batch_purpose(tmp_path: Path):
    provider = FakeProvider('{"src/service.py": "Adicionar cabeçalho padrão."}')

    with pytest.raises(DevAgentError, match="inválido"):
        HeaderPurposeService(provider).gerarPropositos({"src/service.py": "def validate(): pass"}, tmp_path)

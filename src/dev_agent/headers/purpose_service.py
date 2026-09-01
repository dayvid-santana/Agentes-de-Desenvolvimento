# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Gerar propósitos curtos e específicos para cabeçalhos de arquivos.
"""Geração somente leitura de propósitos para cabeçalhos."""

from __future__ import annotations

import json
from pathlib import Path

from dev_agent.errors import DevAgentError
from dev_agent.providers.base import LLMProvider
from dev_agent.security.redaction import SensitiveDataRedactor


class HeaderPurposeService:
    _max_files_per_batch = 12
    _max_chars_per_file = 4_000
    _generic_purpose = "adicionar cabeçalho padrão"

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def gerarPropositos(self, conteudos: dict[str, str], project_root: Path) -> dict[str, str]:
        propositos: dict[str, str] = {}
        itens = list(conteudos.items())
        for inicio in range(0, len(itens), self._max_files_per_batch):
            lote = dict(itens[inicio : inicio + self._max_files_per_batch])
            propositos.update(self._gerarLote(lote, project_root))
        return propositos

    def _gerarLote(self, conteudos: dict[str, str], project_root: Path) -> dict[str, str]:
        contexto = "\n\n".join(
            f"### {nome}\n{self._conteudoParaAnalise(conteudo)}" for nome, conteudo in conteudos.items()
        )
        resposta = self.provider.run(
            f"""Você gera o campo Objetivo de cabeçalhos de arquivos. Para cada arquivo abaixo, produza uma frase
curta, específica e em português que descreva sua responsabilidade no projeto. Não descreva a ação de criar ou
documentar o arquivo, não use frases genéricas, não inclua 'Objetivo:' e não invente fatos fora do conteúdo.

Responda SOMENTE um objeto JSON. Cada chave deve ser exatamente o caminho de um arquivo e cada valor deve ser
o respectivo propósito, com no máximo 120 caracteres.

Arquivos:
{contexto}""",
            project_root,
            write_access=False,
        )
        try:
            dados = json.loads(resposta.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError as exc:
            raise DevAgentError("Não foi possível gerar propósitos válidos para os cabeçalhos.") from exc
        if not isinstance(dados, dict):
            raise DevAgentError("A geração de propósitos retornou um formato inválido.")
        propositos: dict[str, str] = {}
        for nome in conteudos:
            proposito = dados.get(nome)
            if not isinstance(proposito, str):
                raise DevAgentError(f"Não foi gerado um propósito para {nome}.")
            propositos[nome] = self._validarProposito(proposito, nome)
        return propositos

    def _conteudoParaAnalise(self, conteudo: str) -> str:
        return (SensitiveDataRedactor.redact(conteudo) or "")[: self._max_chars_per_file]

    def _validarProposito(self, proposito: str, nome: str) -> str:
        normalizado = " ".join(proposito.removeprefix("Objetivo:").strip().split())
        if (
            not normalizado
            or len(normalizado) > 120
            or normalizado.lower().rstrip(".") == self._generic_purpose
        ):
            raise DevAgentError(f"O propósito gerado para {nome} é inválido.")
        return normalizado

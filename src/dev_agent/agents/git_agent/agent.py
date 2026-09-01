"""Análise Git e plano de Conventional Commits sem criar um commit."""
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Aumentar a acurácia das sugestões (diff staged, tipo livre, escopo e estilo do projeto).
from __future__ import annotations
from pathlib import Path
from dev_agent.core.models import CommitSuggestion
from dev_agent.errors import DevAgentError
from dev_agent.providers.base import LLMProvider
from dev_agent.tools.filesystem import FileSystem
from dev_agent.tools.git import GitTool

_MAX_DIFF_CHARS = 12000
_MAX_NEW_FILE_CHARS = 4000
_TIPOS_VALIDOS = "feat, fix, refactor, test, docs, chore, build, ci, perf, style"


class GitAgent:
    def __init__(self, root: Path, provider: LLMProvider | None = None) -> None:
        self.root = root
        self.git = GitTool(root)
        self.files = FileSystem(root)
        self.provider = provider

    def commit_plan(self) -> list[CommitSuggestion]:
        entries = self._status_entries()
        if not entries:
            return []
        tests = [item for item in entries if item[1].startswith("tests/") or "test_" in item[1]]
        docs = [item for item in entries if item[1].lower().endswith((".md", ".rst"))]
        used = {item[1] for item in (*tests, *docs)}
        code = [item for item in entries if item[1] not in used]
        result: list[CommitSuggestion] = []
        if code:
            result.append(self._sugerir(code, "feat", "Arquivos de implementação devem formar um commit coeso."))
        if tests:
            result.append(self._sugerir(tests, "test", "Testes foram separados para facilitar revisão; podem ser unidos ao commit funcional se forem inseparáveis."))
        if docs:
            result.append(self._sugerir(docs, "docs", "Documentação é semanticamente distinta."))
        return result

    def _status_entries(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in self.git.status().splitlines():
            if line.startswith("##") or len(line) <= 3:
                continue
            entries.append((line[:2], line[3:].strip()))
        return entries

    def _sugerir(self, entries: list[tuple[str, str]], tipoPadrao: str, justificativaPadrao: str) -> CommitSuggestion:
        arquivos = [path for _, path in entries]
        padrao = CommitSuggestion(message=f"{tipoPadrao}(scope): descreve a alteração principal", files=arquivos, rationale=justificativaPadrao)
        contextoDiff = self._contextoDiff(entries)
        if not self.provider or not contextoDiff.strip():
            return padrao
        dicaEscopo = self._dicaEscopo(arquivos)
        estiloRecente = self._estiloRecente()
        try:
            response = self.provider.run(
            f"""
Você é o GitAgent do DevAgent, especializado em analisar alterações de código e sugerir commits de alta qualidade.

Sua tarefa é analisar SOMENTE o diff real fornecido abaixo e gerar a melhor sugestão possível de commit seguindo rigorosamente o padrão Conventional Commits.

Não use conhecimento externo sobre o projeto.
Não presuma intenções que não possam ser inferidas pelo diff.
Não invente funcionalidades, bugs, regras de negócio, nomes de componentes ou motivos para a alteração.

Antes de gerar a resposta, analise internamente:

1. QUAL foi a principal mudança realizada.
2. QUAL comportamento, regra, estrutura ou configuração foi afetada.
3. SE a mudança altera comportamento observável ou apenas implementação interna.
4. QUAL tipo de Conventional Commit representa melhor a mudança.
5. QUAL é o menor escopo significativo que representa corretamente a alteração.
6. SE os arquivos formam realmente uma alteração coesa.
7. QUAL descrição comunica a mudança de forma mais específica possível.

Use essas etapas apenas para raciocinar. NÃO as exiba na resposta.

## FORMATO OBRIGATÓRIO

Responda EXATAMENTE neste formato e sem nenhum texto adicional:

MENSAGEM: <tipo>(<escopo>): <descrição curta, específica e objetiva>

JUSTIFICATIVA: <1-2 frases explicando por que o tipo, o escopo e os arquivos representam uma alteração coesa>

Se nenhum escopo fizer sentido, use:

MENSAGEM: <tipo>: <descrição curta, específica e objetiva>

## ESCOLHA DO TIPO

Escolha livremente entre:

{_TIPOS_VALIDOS}

Determine o tipo pelo efeito REAL observado no diff:

- feat: adiciona comportamento ou capacidade nova ao sistema.
- fix: corrige comportamento incorreto, bug ou regressão.
- refactor: altera implementação ou estrutura interna sem mudar o comportamento esperado.
- perf: melhora desempenho sem alterar a funcionalidade esperada.
- test: adiciona, remove ou modifica somente testes.
- docs: altera somente documentação.
- style: altera somente formatação, espaços, organização visual ou estilo de código sem impacto comportamental.
- build: altera sistema de build, empacotamento ou dependências diretamente relacionadas ao build.
- ci: altera pipelines, automações ou configuração de integração/entrega contínua.
- chore: altera manutenção, configuração ou tarefas auxiliares que não se encaixam melhor em outro tipo.

IMPORTANTE:
Não escolha `feat` apenas porque existe código novo.
Não escolha `fix` apenas porque o código anterior foi substituído.
Não escolha `refactor` se houver mudança observável de comportamento.
Não escolha `chore` como categoria genérica quando outro tipo for mais preciso.

Os arquivos foram previamente agrupados pela heurística:

"{tipoPadrao}"

Essa classificação foi feita SOMENTE com base nos caminhos dos arquivos e deve ser considerada uma pista fraca.

O conteúdo do diff possui prioridade absoluta.

Se o diff contradizer `{tipoPadrao}`, escolha o tipo indicado pelo diff.

## ESCOLHA DO ESCOPO

Escopo inicialmente sugerido pelos caminhos:

{dicaEscopo}

Use esse escopo somente se ele representar corretamente a responsabilidade modificada.

Prefira escopos:

- curtos;
- estáveis;
- semanticamente relevantes;
- relacionados ao módulo, domínio, componente ou responsabilidade alterada.

Evite usar:

- nomes de arquivos como escopo quando existir um conceito melhor;
- diretórios genéricos como `src`, `app`, `utils` ou `components`;
- escopos excessivamente específicos;
- escopos inventados que não aparecem ou não podem ser inferidos pelo diff.

Omita o escopo se nenhum escopo claro puder ser determinado.

## DESCRIÇÃO DO COMMIT

A descrição deve:

- dizer exatamente O QUE mudou;
- destacar a principal intenção observável da alteração;
- mencionar função, regra, comportamento, componente ou responsabilidade quando isso puder ser identificado;
- ser curta e informativa;
- funcionar sem precisar ler a justificativa;
- evitar ponto final;
- evitar informações redundantes com o tipo e o escopo.

Prefira descrições como:

"corrige cálculo do total das parcelas"
"adiciona validação de e-mail no cadastro"
"extrai criação do token para serviço de autenticação"
"atualiza configuração do pipeline de deploy"

Evite descrições vagas como:

"faz ajustes"
"realiza melhorias"
"atualiza código"
"corrige problemas"
"diversas alterações"
"refatora arquivos"
"melhora implementação"

Não descreva apenas operações mecânicas como:

"altera arquivo X"
"modifica função Y"

quando for possível identificar a consequência ou intenção concreta da alteração.

## COESÃO

Arquivos deste grupo:

{", ".join(arquivos)}

Considere os arquivos como parte do mesmo commit SOMENTE se o diff indicar que eles participam da mesma alteração lógica.

Na JUSTIFICATIVA:

- explique a relação entre as mudanças;
- explique brevemente por que o tipo escolhido é adequado;
- não repita simplesmente a mensagem do commit;
- não invente contexto ausente no diff.

Se houver mudanças secundárias necessárias para suportar a alteração principal, considere-as parte do mesmo commit.

Se o diff contiver mudanças diferentes, dê prioridade à intenção principal que explica o conjunto de alterações da forma mais coesa possível.

## HISTÓRICO DE ESTILO

{estiloRecente}

O histórico acima serve SOMENTE como referência de estilo e nomenclatura.

Nunca copie um tipo, escopo ou descrição de commits anteriores se eles não forem sustentados pelo diff atual.

A precisão semântica do commit atual tem prioridade sobre consistência estilística.

## DIFF REAL

{contextoDiff}
""",

                self.root,
                write_access=False,
            )
        except DevAgentError:
            return padrao
        mensagem, justificativa = self._analisarResposta(response)
        return CommitSuggestion(message=mensagem or padrao.message, files=arquivos, rationale=justificativa or padrao.rationale)

    def _contextoDiff(self, entries: list[tuple[str, str]]) -> str:
        rastreados = [path for code, path in entries if code.strip() != "??"]
        partes: list[str] = []
        if rastreados:
            diff = self.git.diff_paths(rastreados)
            if diff.strip():
                partes.append(diff)
        for code, path in entries:
            if code.strip() != "??":
                continue
            try:
                conteudo = self.files.read_text(path, max_chars=_MAX_NEW_FILE_CHARS).content
            except (OSError, UnicodeDecodeError):
                partes.append(f"### novo arquivo (binário ou ilegível): {path}")
            else:
                partes.append(f"### novo arquivo: {path}\n{conteudo}")
        return self._limitarPorLinha(partes, _MAX_DIFF_CHARS)

    @staticmethod
    def _limitarPorLinha(partes: list[str], orcamento: int) -> str:
        """Junta partes até o orçamento sem cortar no meio de uma linha/hunk do diff."""
        incluidas: list[str] = []
        restante = orcamento
        for parte in partes:
            if len(parte) <= restante:
                incluidas.append(parte)
                restante -= len(parte)
                continue
            linhas: list[str] = []
            usado = 0
            for linha in parte.splitlines():
                if usado + len(linha) + 1 > restante:
                    break
                linhas.append(linha)
                usado += len(linha) + 1
            if linhas:
                incluidas.append("\n".join(linhas) + "\n... [diff truncado; restante omitido por limite de tamanho]")
            break
        return "\n\n".join(incluidas)

    def _dicaEscopo(self, arquivos: list[str]) -> str:
        candidatos = {self._componentePrincipal(item) for item in arquivos}
        candidatos.discard(None)
        if len(candidatos) == 1:
            return next(iter(candidatos))
        if candidatos:
            return ", ".join(sorted(candidatos)) + " (arquivos tocam mais de um módulo; escolha o mais relevante ou use um escopo mais amplo)"
        return "sem pista clara pelos caminhos; escolha um escopo curto e específico, ou omita"

    @staticmethod
    def _componentePrincipal(caminho: str) -> str | None:
        partes = Path(caminho.replace("\\", "/")).parts
        for pasta in ("agents", "tools", "skills"):
            if pasta in partes:
                indice = partes.index(pasta)
                if indice + 1 < len(partes):
                    proximo = partes[indice + 1]
                    nome = Path(proximo).stem if proximo.endswith(".py") else proximo
                    return nome.replace("_", "-")
        return partes[0].replace("_", "-") if partes else None

    def _estiloRecente(self) -> str:
        recentes = self.git.log(5)
        mensagens = [linha.split(" ", 1)[1] for linha in recentes.splitlines() if " " in linha]
        if not mensagens:
            return ""
        exemplos = "\n".join(f"- {mensagem}" for mensagem in mensagens[:5])
        return f"Estilo de commits recentes deste projeto (mantenha tom e formato semelhantes, mas descreva ESTE diff, não os exemplos):\n{exemplos}\n"

    @staticmethod
    def _analisarResposta(response: str) -> tuple[str, str]:
        message, rationale = "", ""
        for line in response.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("MENSAGEM:"):
                message = stripped.split(":", 1)[1].strip()
            elif stripped.upper().startswith("JUSTIFICATIVA:"):
                rationale = stripped.split(":", 1)[1].strip()
        return message, rationale

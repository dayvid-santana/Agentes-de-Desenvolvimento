<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# DevAgent

DevAgent é uma ferramenta local para coordenar tarefas de desenvolvimento assistidas por IA em projetos que possuem um `dev-agent.yaml`. Ela oferece uma CLI, uma API HTTP local, contexto limitado por projeto, agentes especializados e execução de escrita em worktrees Git isolados.

O projeto é um pacote Python `0.1.0`, compatível com Python 3.11 ou superior. A integração de produção com o modelo é feita exclusivamente pela CLI Codex instalada na máquina; os testes usam fakes e não chamam o Codex real.

## Começo rápido no Windows

Pré-requisitos:

- Python 3.11+;
- Git;
- Codex CLI no `PATH` e autenticado (verifique com `codex --version` e conclua `codex login`, quando necessário).

Na raiz deste repositório:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

O executável `dev-agent` fica disponível enquanto o ambiente virtual estiver ativo. Para instalar em um ambiente isolado global, o README apenas prevê `pipx install .`; a configuração do `pipx` não é automatizada pelo projeto.

Para usar o DevAgent em outro repositório, vá até ele e crie a configuração inicial:

```powershell
cd C:\Projetos\MeuProjeto
dev-agent init
dev-agent doctor
dev-agent context
dev-agent ask "Explique a arquitetura atual"
```

`init` não sobrescreve um `dev-agent.yaml` existente. Os demais comandos descobrem esse arquivo subindo a partir do diretório atual.

## Fluxo de uma tarefa que escreve

```text
task -> plano sem escrita -> revisão/decisão arquitetural -> run --confirm
     -> branch + worktree isolados -> pipeline -> testes/revisão -> job
```

Exemplo:

```powershell
dev-agent task "Adicionar validação de CPF"
dev-agent run <id-do-plano> --confirm
dev-agent job <id-do-plano>
```

O plano pode avisar que o repositório não está limpo ou não é Git. A execução só começa após confirmação explícita, requer um repositório Git limpo e cria a branch `dev-agent/<id>` em um worktree irmão do checkout principal. A tarefa é executada em segundo plano. Use `cancel` para solicitar cancelamento cooperativo, `resume` para um job bloqueado com checkpoint utilizável e `cleanup <id> --confirm` para remover um worktree finalizado.

Uma solicitação com termos estruturais, como autenticação, migração de banco ou contrato público, exige uma decisão arquitetural registrada antes da execução. Veja [a orquestração](docs/orchestration.md) e [a segurança](docs/security.md).

## Comandos principais

| Comando | Efeito atual |
|---|---|
| `init` | Cria `dev-agent.yaml` no diretório atual. |
| `doctor` | Verifica Python, Git, Codex, FastAPI, API local e configuração descoberta. |
| `start`, `stop`, `status` | Controlam a API local padrão em `127.0.0.1:8765`. |
| `context [objetivo]` | Mostra o pacote de contexto selecionado. |
| `ask <pergunta>` | Consulta o provider em modo somente leitura. |
| `task <objetivo>` / `run <id> --confirm` | Cria plano e inicia escrita isolada. |
| `document <caminho>` | Cria um plano para documentação de código. |
| `document-project` | Cria um plano com objetivo de documentação abrangente. |
| `job`, `cancel`, `resume`, `cleanup` | Consultam e controlam jobs assíncronos. |
| `review [--staged]`, `test`, `debug <mensagem>` | Revisam diff, executam testes configurados ou investigam uma falha. |
| `commit` | Sugere agrupamentos de Conventional Commits; não cria commit nem faz push. |
| `agents [list|show|graph|doctor]` | Consulta o catálogo declarativo. |
| `session [clear]` | Consulta ou remove a sessão local ativa. |

Execute `dev-agent commands` ou `dev-agent <comando> --help` para a ajuda exposta pela CLI.

## Arquitetura

```text
CLI (cliente HTTP) ─┐
                    ├─> API FastAPI local ─> Orchestrator
Assistente externa ─┘                         ├─> ContextAgent / AgentRegistry
                                               ├─> tools (filesystem, Git, terminal, testes, busca)
                                               └─> provider Codex
```

- `cli/` não importa agentes: atua como cliente da API local.
- `api/` valida HTTP e encaminha ao `Orchestrator` ou ao gerenciador de jobs.
- `core/` contém contratos Pydantic, orquestração, máquina de estados, gateway externo e jobs.
- `agents/` contém agentes de uma única etapa; o catálogo em `agents/catalog.yaml` é a fonte única de seus metadados e entrypoints.
- `tools/` centraliza operações de arquivo, Git, terminal, busca e testes. O `FileSystem` resolve caminhos dentro da raiz ativa.
- `providers/` expõe o protocolo de LLM; `providers/codex/` encapsula os argumentos específicos do Codex.

O `Orchestrator` serializa as fases que podem escrever por meio de um lock de processo. Agentes recebem `ContextPacket` e retornam `SubAgentResult`, em vez de trocar histórico bruto. A visão completa está em [docs/orchestration.md](docs/orchestration.md) e o catálogo está em [docs/agent-inventory.md](docs/agent-inventory.md).

## Mapa da documentação

- [Visão geral e estrutura de diretórios](docs/overview.md)
- [Configuração por projeto](docs/configuration.md)
- [Orquestração, jobs e retomada](docs/orchestration.md)
- [Inventário e registro de agentes](docs/agent-inventory.md)
- [API local e integração com assistentes](docs/assistant-backend.md)
- [Segurança e limites operacionais](docs/security.md)
- [Desenvolvimento e testes](docs/testing.md)

## Configuração

`dev-agent.yaml` define o projeto, limites de contexto, comando de testes, Git, cabeçalhos e políticas de segurança. O arquivo usado neste repositório é um exemplo funcional. Os campos, valores padrão e limites estão em [docs/configuration.md](docs/configuration.md).

## API local e Docker

O processo iniciado por `python -m dev_agent.api.app` escuta por padrão em `127.0.0.1:8765`. A API não implementa autenticação nem isolamento multiusuário; não deve ser exposta à rede. O contrato HTTP, modelos de entrada e ciclo de jobs estão em [docs/assistant-backend.md](docs/assistant-backend.md).

Para desenvolvimento com Docker Desktop:

```powershell
docker compose up --build api
docker compose --profile test run --rm tests
```

O Compose publica o contêiner em `127.0.0.1:8766` no host. Esse contêiner é destinado à API e à suíte de testes; o fluxo que depende do Codex autenticado continua previsto para a instalação local do usuário.

## Desenvolvimento e testes

```powershell
pytest
python -m compileall -q src
python -m dev_agent.api.app
```

`pytest` procura testes em `tests/`, usa `src` no `pythonpath` e recebe `-q` por padrão. A cobertura exercita configuração, filesystem, políticas, redator, cabeçalhos, catálogo, agentes, orquestração, checkpoints, jobs e API/CLI. Detalhes e limitações de teste estão em [docs/testing.md](docs/testing.md).

## Limitações conhecidas

- Não há autenticação, autorização, TLS ou isolamento multiusuário na API local.
- Planos, jobs e sessão são persistidos localmente sem criptografia. Os objetivos inseridos pelo usuário podem ser gravados sem redação; não informe segredos em argumentos de CLI, objetivos ou decisões arquiteturais.
- O log estruturado atual registra a linha de comando do `TerminalTool`. Como o prompt é passado como argumento para `codex exec`, ele pode aparecer no log; trate os logs locais como potencialmente sensíveis.
- A documentação não identifica um mecanismo de release/publicação, CI, licença, política de suporte ou política de privacidade no repositório.
- A máquina de estados declara fases adicionais (`DOCUMENTING`, `PREPARING_GIT` e `ROLLED_BACK`), mas o pipeline atual não as executa automaticamente.
- A retomada é limitada a três tentativas por job e só é possível após um checkpoint, enquanto o worktree estiver registrado e não marcado como removido; o recuperador não confirma a existência do caminho no disco.

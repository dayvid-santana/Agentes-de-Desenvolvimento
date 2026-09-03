# DevAgent — Documento de Contexto Completo

> Este documento reúne tudo que é necessário para entender o projeto DevAgent: propósito, arquitetura, agentes, fluxo de execução, configuração, API, segurança, testes e limitações conhecidas. Serve como fonte única para gerar conteúdo de site, apresentações ou qualquer material derivado sobre o projeto.

---

## 1. O que é o DevAgent

DevAgent é uma ferramenta local (não um serviço em nuvem) que coordena tarefas de desenvolvimento de software assistidas por IA, dentro de projetos que possuem um arquivo `dev-agent.yaml` na raiz.

Em vez de enviar um único prompt genérico para um modelo e esperar que ele resolva tudo de uma vez — entender o código, implementar, testar, documentar e revisar — o DevAgent divide esse trabalho entre **26 agentes especializados**, cada um com uma única responsabilidade, orquestrados em um pipeline previsível e auditável.

Autor: **Dayvid Santana**. Projeto pessoal, em Python, código aberto para uso próprio (sem licença/CI/release publicados até o momento).

### Problema que resolve

Assistentes de IA genéricos aplicados a tarefas de código real tendem a:
- alterar mais do que o necessário;
- esquecer de atualizar testes ou documentação junto da mudança;
- misturar análise, implementação e decisão de commit num único contexto poluído;
- commitar ou aplicar mudanças sem uma etapa clara de revisão humana.

O DevAgent resolve isso com **separação de responsabilidades entre agentes**, **execução isolada em branch/worktree Git** e **confirmação explícita obrigatória** antes de qualquer escrita.

### Integração com modelo de IA

A execução em produção depende da **Codex CLI** instalada e autenticada na máquina do usuário (`codex --version`, `codex login`). Não há chamada HTTP direta a um provedor de modelo embutida no código — o `CodexProvider` invoca `codex exec` como subprocesso, com sandbox `read-only` para análises e `workspace-write` apenas para agentes que escrevem código.

---

## 2. Arquitetura

```text
CLI (cliente HTTP) ─┐
                    ├─> API FastAPI local (127.0.0.1:8765) ─> Orchestrator
Assistente externa ─┘                                          ├─> ContextAgent / AgentRegistry
                                                                 ├─> tools (filesystem, Git, terminal, testes, busca)
                                                                 └─> provider Codex (subprocess)
```

| Camada | Caminho | Responsabilidade |
|---|---|---|
| CLI | `src/dev_agent/cli/` | Comandos Typer; consome a API local via HTTP, não instancia agentes diretamente. |
| API | `src/dev_agent/api/` | Aplicação FastAPI: rotas de operações locais, planos e jobs. |
| Core | `src/dev_agent/core/` | Contratos Pydantic, orquestração, máquina de estados, gateway de assistente, jobs assíncronos. |
| Agentes | `src/dev_agent/agents/` | Os 26 agentes especializados; registrados via `agents/catalog.yaml`. |
| Tools | `src/dev_agent/tools/` | Operações encapsuladas: arquivos, Git, terminal, busca, testes. |
| Providers | `src/dev_agent/providers/` | Protocolo independente de provedor + adaptador da Codex CLI. |
| Segurança | `src/dev_agent/security/` | Heurística de decisão arquitetural, política de comandos destrutivos, redação de dados sensíveis. |
| Memória | `src/dev_agent/memory/` | Persistência local de sessão, planos e jobs. |
| Cabeçalhos | `src/dev_agent/headers/` | Insere cabeçalhos padronizados em arquivos alterados sem cabeçalho. |

**Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, PyYAML, Typer, Rich, HTTPX. Empacotado com Hatchling, expõe o comando `dev-agent`. Imagem Docker baseada em `python:3.11-slim` (serviços `api` e `tests` via `compose.yaml`).

**Dados locais:** sessão, planos e jobs ficam em `%LOCALAPPDATA%\DevAgent` (fallback `%TEMP%\DevAgent`). Nenhum banco de dados, fila ou servidor remoto.

---

## 3. Os 26 agentes

Cada agente é declarado em `agents/catalog.yaml` (fonte única de verdade) com módulo, classe, modo (`read`/`write`/`execute`/`guard`), ferramentas, dependências e comando de invocação. O `AgentRegistry` valida o catálogo, recusa IDs duplicados e verifica imports.

### Contexto e coordenação
| Agente | Função |
|---|---|
| `context` | Seleciona instruções, código, testes e diff relevantes para o objetivo. |
| `requirements` | Define critérios de aceite, escopo e ambiguidades. |
| `architecture_guard` | Detecta pedidos estruturalmente sensíveis (auth, banco de dados, contrato público, fila, deploy) e exige decisão humana registrada antes de executar. |

### Escrita de tarefa
| Agente | Função |
|---|---|
| `implementation` | Implementa a tarefa aprovada. |
| `documentation_writer` | Atualiza documentação quando a alteração exigir. |
| `project_documentation` | Atualiza a documentação abrangente do projeto (acionado por objetivos que começam com "documentar o projeto"). |
| `code_documentation` | Documenta código alterado sem sobrescrever cabeçalhos existentes. |
| `test_author` | Cria testes de regressão para a alteração feita. |

### Teste e diagnóstico
| Agente | Função |
|---|---|
| `test` | Executa a suíte de testes configurada (`testing.command`). |
| `bug_reproduction` | Produz passos verificáveis para reproduzir uma falha relatada. |
| `review` | Revisa o diff em busca de regressões e riscos. |
| `debug` | Diagnostica falhas cruzando testes, diff e contexto. |

### Análises especializadas (somente leitura)
`code_modeling`, `security`, `database`, `api_contract`, `quality`, `dependency`, `design_patterns`, `performance`, `frontend`, `observability`, `release`, `refactor` — cada um analisa o contexto selecionado sob uma ótica específica (modelagem de código, segurança, persistência, contratos de API, cobertura de teste, dependências, padrões de projeto, performance, front-end, observabilidade, prontidão de release, refatoração), sem alterar arquivos.

### Documentação e Git
| Agente | Função |
|---|---|
| `documentation` | Avalia impactos de documentação. |
| `git` | Sugere agrupamentos de commit em Conventional Commits — **nunca cria commit**. |

---

## 4. Pipeline de uma tarefa que escreve código

```text
task "<objetivo>"
  -> plano sem escrita (TaskPlan, arquivos relevantes, avisos)
  -> decisão arquitetural registrada, se exigida pela heurística
  -> run --confirm (confirmed_write=true)
  -> branch dev-agent/<id> + worktree Git isolado (irmão do checkout principal)
  -> pipeline de fases:
       DISCOVERING  : context
       PLANNING     : requirements                                  (checkpoint 1)
       EXECUTING    : implementation, code_documentation,
                      test_author, documentation_writer              (checkpoint 2)
       TESTING      : test, bug_reproduction                         (checkpoint 3)
       REVIEWING    : review, documentation + especialistas          (checkpoint 4)
  -> COMPLETED | PARTIALLY_COMPLETED
```

Pontos-chave:
- O checkout principal **nunca** é alterado diretamente; toda escrita acontece no worktree isolado.
- `GitTool.create_worktree()` exige repositório Git limpo antes de começar.
- Cada checkpoint persiste fase concluída, agentes executados e arquivos alterados — permitindo **retomar** (`resume`) um job interrompido, até 3 tentativas.
- `cancel` é cooperativo (encerra o processo em execução); `cleanup --confirm` remove o worktree com `git worktree remove --force` (descarta não commitados).
- Resultado `PARTIALLY_COMPLETED` quando os testes emitem avisos — revisão e especialistas ainda rodam mesmo assim.
- Nada é commitado, enviado (push) ou revertido automaticamente.

---

## 5. Uso via CLI

```powershell
dev-agent init                       # cria dev-agent.yaml
dev-agent doctor                     # verifica Python, Git, Codex, API
dev-agent context                    # mostra o pacote de contexto selecionado
dev-agent ask "Explique a arquitetura atual"

dev-agent task "Adicionar validação de CPF"
dev-agent run <id-do-plano> --confirm
dev-agent job <id-do-plano>

dev-agent document <caminho>         # documenta código selecionado
dev-agent document-project           # documentação abrangente do projeto
dev-agent headers --check|--plan|--apply --confirm

dev-agent patterns "<objetivo>"      # análise de padrões de projeto, sob demanda
dev-agent model "<objetivo>"         # modelagem de código autocontida

dev-agent review [--staged]
dev-agent test
dev-agent debug "<mensagem>"
dev-agent commit                     # sugere agrupamento de commits, não commita

dev-agent agents [list|show|graph|doctor]
```

---

## 6. API local (para integrações/assistentes externas)

Aplicação FastAPI `DevAgent` v0.1.0, escuta em `127.0.0.1:8765`. **Sem autenticação, TLS ou isolamento multiusuário** — projetada para uso estritamente local.

Principais rotas:
- `GET /health`, `GET /health/codex` — status da API e prontidão da Codex CLI (cache de 60s).
- `GET /agents`, `/agents/catalog`, `/agents/graph`, `/agents/doctor` — introspecção do catálogo.
- `POST /agent/context`, `/agent/ask`, `/agent/review`, `/agent/test`, `/agent/debug` — invocações de leitura.
- `POST /git/commit-plan` — sugestão de commits.
- `POST /headers` — listagem/aplicação de cabeçalhos.
- `POST /assistant/invocations` — invocação direta de um agente por nome (`ask`, `context`, `review`, `test`, `debug`, `git`, `documentation`, `bug_reproduction` + os 12 especialistas).
- `POST /assistant/task-plans` → `/{id}/architecture-approval` → `/{id}/start` — fluxo completo de plano e início de job em segundo plano.
- `GET /assistant/jobs/{id}`, `/cancel`, `/resume`, `/cleanup` — ciclo de vida do job.

`POST /agent/task` está marcado obsoleto e sempre recusa execução direta — o fluxo correto é sempre plano → aprovação (se exigida) → start.

---

## 7. Configuração (`dev-agent.yaml`)

```yaml
project:
  name: MeuProjeto
  author: Nome do autor

context:
  include: [src/**, tests/**, docs/**, AGENTS.md, README.md]
  exclude: [.git/**, .venv/**, node_modules/**, dist/**, build/**, ...]
  max_files: 12
  max_file_chars: 16000
  max_total_chars: 80000
  dependency_depth: 1

testing:
  command: pytest

git:
  conventional_commits: true

headers:
  enabled: true
  author: Nome do autor
  date_format: "%d/%m/%Y"

security:
  require_architecture_approval: true
  require_destructive_command_approval: true
```

O DevAgent descobre a raiz do projeto subindo os diretórios a partir do atual, procurando `dev-agent.yaml`. A seleção de contexto (`ContextAgent`) sempre prioriza `AGENTS.md`, segue imports locais em Python até `dependency_depth`, respeita os limites de tamanho e redige conteúdo sensível antes de montar o pacote enviado ao provider.

---

## 8. Segurança e limites operacionais

- **Isolamento de caminho:** toda operação de arquivo passa por `FileSystem.resolve()`, que impede sair da raiz do projeto.
- **Comandos destrutivos bloqueados por padrão:** `git reset --hard`, `git clean -f`, `git push --force`, `git branch -D`, `rm -rf`/equivalentes — exigem confirmação explícita.
- **Redação de segredos:** `SensitiveDataRedactor` remove chaves de API, tokens, senhas, chaves PEM e credenciais em URLs de contexto, diffs, resultados e sessão. Exceção conhecida: `TaskPlan.objective` e campos de sessão não passam por essa redação — objetivos e prompts não devem conter segredos.
- **Decisão arquitetural obrigatória:** heurística por palavras-chave (autenticação, banco de dados, contrato público, fila, deploy) força registro de uma decisão humana de 10–1000 caracteres antes de executar.
- **Escrita sempre isolada:** branch + worktree próprios, nunca o checkout principal; nenhum commit, push ou rollback automático.
- **Servidor local apenas:** sem autenticação/TLS — não deve ser exposto à rede.

---

## 9. Testes

Suíte com **84 testes em 13 arquivos** (`pytest`), cobrindo configuração, isolamento de filesystem, políticas destrutivas, redação de segredos, cabeçalhos, catálogo/registry, agentes, orquestrador, Git, máquina de estados, checkpoints, jobs, cancelamento/retomada e rotas de API/CLI. Providers são fakes/monkeypatch — a suíte não exige Codex instalado nem rede.

```powershell
pytest
python -m compileall -q src
```

Sem lint, type checker, cobertura mínima ou CI configurados no repositório até o momento.

---

## 10. Limitações conhecidas (estado atual, com transparência)

- Sem autenticação, autorização, TLS ou multiusuário na API local.
- Sem licença, CI, pipeline de release, política de suporte ou privacidade publicadas.
- Dependências entre agentes são declarativas no catálogo, mas o único fluxo real é a sequência fixa do `Orchestrator` — não há agendador genérico baseado em grafo.
- Integração com Codex real não é testada automaticamente (apenas fakes).
- Retomada de job limitada a 3 tentativas e depende de checkpoint + worktree ainda registrado.
- Estados declarados `DOCUMENTING`, `PREPARING_GIT` e `ROLLED_BACK` existem no modelo mas não são executados automaticamente hoje.

---

## 11. O que torna o projeto diferente

- **Multiagente especializado**, não um prompt único fazendo tudo.
- **Execução isolada e auditável**: branch + worktree próprios, checkpoints, confirmação explícita em cada etapa de escrita.
- **100% local**: roda na máquina do usuário, sem enviar código para um serviço de terceiros além da própria Codex CLI já instalada e autenticada localmente.
- **Catálogo declarativo**: adicionar/alterar um agente é uma entrada de YAML validada por um registry, não código espalhado pelo orquestrador.
- **Documentação separada por público**: `README.md`/`docs/` para pessoas; `AGENTS.md`/`agent-context/` como contexto técnico dedicado para as próprias IAs que trabalham no repositório.

<!--
DevAgent
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar os agentes especialistas disponíveis.
-->
<!--
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar a seleção de contexto orientada a código.
DevAgent-Task: context-code-selection-20260828
-->
<!--
Autor: Dayvid Santana
Data: 28/08/2026
Objetivo: Documentar os agentes de documentação, testes e reprodução.
-->

# DevAgent

DevAgent é uma CLI global para desenvolvimento assistido por IA em projetos locais. A instalação contém agentes, ferramentas, API e provider; cada projeto atendido contém somente seu `dev-agent.yaml`, código e documentação.

## Windows 11: instalação

Pré-requisitos: Python 3.11+, Git e uma instalação autenticada do Codex CLI (`codex --version`). No diretório deste repositório, crie um ambiente isolado e instale a CLI:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

O comando `dev-agent` passa a estar disponível enquanto o ambiente estiver ativo. Para uma instalação global isolada, prefira `pipx install .` (com `pipx` instalado) no diretório deste projeto.

Se a instalação `--user` informar que a pasta Scripts não está no `PATH`, acrescente-a uma vez ao PATH de usuário e abra um novo PowerShell:

```powershell
$scripts = "$env:APPDATA\Python\Python311\Scripts"
[Environment]::SetEnvironmentVariable("Path", ([Environment]::GetEnvironmentVariable("Path", "User") + ";" + $scripts), "User")
```

O provider não recebe token nem credencial pelo DevAgent: autentique o Codex normalmente com `codex login` antes de usar `ask`, `task` ou a revisão enriquecida.

## Dependências e Docker

Para instalar todas as dependências de desenvolvimento no Windows, a partir da raiz deste repositório:

```powershell
python -m pip install -e ".[dev]"
```

Para preparar e iniciar a API no Docker Desktop:

```powershell
docker compose up --build api
```

A API Docker ficará disponível somente em `http://127.0.0.1:8766` (a CLI do host preserva `127.0.0.1:8765`). Para rodar a suíte de testes em contêiner:

```powershell
docker compose --profile test run --rm tests
```

O contêiner é um ambiente de desenvolvimento/testes para a API. O provider Codex continua sendo executado na instalação Windows autenticada do usuário; por isso, use a CLI global no host para `ask`, `task` e revisão com Codex.

## Uso em qualquer projeto

```powershell
cd C:\Projetos\GestorPay
dev-agent init
dev-agent doctor
dev-agent context
dev-agent ask "Explique o fluxo de cadastro de usuários"
dev-agent task "Adicione normalização de CPF"
dev-agent test
dev-agent review
git add .
dev-agent review --staged
dev-agent commit
```

`init` nunca sobrescreve uma configuração existente. Todos os demais comandos procuram `dev-agent.yaml` subindo a partir do diretório atual. A API é iniciada automaticamente quando necessário e fica restrita a `127.0.0.1:8765`; `start`, `stop` e `status` também podem controlá-la explicitamente.

## Configuração por projeto

```yaml
project:
  name: GestorPay
  author: Dayvid Santana
testing:
  command: pytest
headers:
  enabled: true
security:
  require_architecture_approval: true
```

O arquivo completo criado por `init` inclui prioridades de documentação, limites de contexto, exclusões, Git, cabeçalhos e segurança. YAML inválido resulta em erro claro na CLI.

O `ContextAgent` sempre inclui instruções de `AGENTS.md`, aplica `context.include` e `context.exclude` à busca, aceita caminhos relativos citados no pedido e prioriza arquivos alterados, código e testes. Para código Python, ele também segue imports locais e testes correspondentes até `context.dependency_depth`, sempre respeitando os limites de arquivos e caracteres.

## Comportamento de segurança

O DevAgent limita arquivos, buscas e escrita à raiz ativa, redige o contexto de padrões sensíveis configurados e não executa `git reset --hard`, `git clean -fd`, `git push --force`, `git branch -D` ou remoções recursivas sem confirmação explícita. `commit` apenas sugere um plano de Conventional Commits; não cria commits e nunca faz push.

Uma tarefa que indique mudança estrutural (framework, banco, autenticação, microserviço ou contrato público) é interrompida com uma decisão arquitetural formatada para o usuário.

## Agentes especializados

Além de contexto, implementação, testes, revisão, documentação, depuração e Git, `dev-agent task` coordena agentes de requisitos, segurança, banco de dados, contratos de API, qualidade, dependências, desempenho, frontend, observabilidade, release e refatoração. Eles recebem apenas o contexto e o diff selecionados, fazem análises somente de leitura e retornam riscos ou próximos passos. O `DocumentationWriterAgent` pode atualizar `README.md`, `docs/` ou documentação de API quando a implementação tornar isso necessário; ele não altera código nem dependências.

O fluxo também inclui `CodeDocumentationAgent`, que adiciona documentação útil ao código e preserva cabeçalhos existentes; `TestAuthorAgent`, que cria testes de regressão relacionados à alteração; e `BugReproductionAgent`, que transforma relatos de falha em passos verificáveis sem editar arquivos.

## Desenvolvimento

```powershell
pytest
python -m compileall -q src
python -m dev_agent.api.app
```

Os testes usam provider fake; jamais consomem Codex real. A integração de produção com Codex fica exclusivamente em `providers/codex/provider.py` e usa a interface verificada `codex exec`.

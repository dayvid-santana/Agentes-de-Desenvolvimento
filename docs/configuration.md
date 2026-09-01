<!--
dev-agent
Autor: Dayvid Santana
Data: 31/08/2026
Objetivo: Documentar o projeto atual de forma abrangente.
-->
<!--
DevAgent-Task: 4826528013919681285
-->


# Configuração por projeto

O DevAgent descobre a raiz procurando `dev-agent.yaml` a partir do diretório atual e subindo seus ancestrais. YAML inválido, documento que não seja objeto e campos incompatíveis resultam em `InvalidProjectConfigError`.

`dev-agent init` cria este formato inicial:

```yaml
project:
  name: MeuProjeto
  author: Dayvid Santana

documentation:
  priority: [AGENTS.md, docs/**, README.md]

context:
  include: [src/**, tests/**, docs/**, AGENTS.md, README.md]
  exclude: [.git/**, .venv/**, venv/**, node_modules/**, dist/**, build/**, coverage/**, __pycache__/**, "*.pyc", "*.log"]
  max_files: 12
  max_file_chars: 16000
  max_total_chars: 80000
  dependency_depth: 1

testing:
  command: pytest

git:
  conventional_commits: true
  review_staged: true
  suggest_commit_split: true

headers:
  enabled: true
  author: Dayvid Santana
  date_format: "%d/%m/%Y"
  history: true

security:
  require_architecture_approval: true
  require_destructive_command_approval: true
```

## Campos e limites validados

| Seção | Campos | Comportamento atual |
|---|---|---|
| `project` | `name` obrigatório; `author` | Identifica o projeto. `author` não alimenta automaticamente `headers.author` quando a configuração é carregada: ambos têm seus próprios valores padrão. O arquivo gerado por `init` os preenche com o mesmo autor. |
| `documentation` | `priority` | É preservado na configuração, mas a seleção de contexto atual usa ordem própria de `AGENTS.md`, caminhos, mudanças e documentação; não há evidência de que esse campo altere a ordenação. |
| `context` | `include`, `exclude`, `max_files`, `max_file_chars`, `max_total_chars`, `dependency_depth` | Controla busca e tamanho do pacote. `max_files`: 1–100; `max_file_chars`: mínimo 1.000; `max_total_chars`: mínimo 5.000; profundidade: 0–5. |
| `testing` | `command` | Comando passado ao `TestTool`; ele é separado com `shlex.split` e executado sem shell. |
| `git` | `conventional_commits`, `review_staged`, `suggest_commit_split` | Declarados e têm os padrões acima. O plano de commit atual sempre aplica a heurística fixa de código/testes/docs; não há evidência de leitura desses três flags nesse fluxo. |
| `headers` | `enabled`, `author`, `date_format`, `history` | `HeaderService` só acrescenta cabeçalho a arquivos suportados sem cabeçalho. `dev-agent headers --check` lista os candidatos do escopo de contexto; `--plan` propõe um propósito específico por arquivo; `--apply --confirm` insere ou corrige cabeçalhos genéricos criados pelo comando anterior. `history` existe no modelo, mas o serviço atual não usa esse campo. |
| `security` | `require_architecture_approval`, `require_destructive_command_approval`, `sensitive_patterns` | `sensitive_patterns` também é adicionada às exclusões de busca. O `Orchestrator.task()` consulta `require_architecture_approval`, mas o fluxo normal de plano/job exige aprovação sempre que `TaskJobManager` detectar uma palavra-chave estrutural; portanto, desativar o flag não elimina essa exigência no fluxo HTTP/CLI atual. `require_destructive_command_approval` é declarado, mas `TerminalTool` chama a política de comando diretamente; não há evidência de que o flag a desative. |

O modelo fornece padrões para todas as seções, exceto `project`. `security.sensitive_patterns` assume `.env`, `.env.*`, `credentials*`, `secrets*`, `*.pem` e `*.key` quando não for informado.

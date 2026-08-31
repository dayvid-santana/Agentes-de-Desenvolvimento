# Desenvolvimento e testes

## Executar a suíte

```powershell
python -m pip install -e ".[dev]"
pytest
python -m compileall -q src
```

`pyproject.toml` configura `pytest` para procurar `tests/`, adicionar `src` ao `pythonpath` e usar `-q`. As dependências de desenvolvimento declaradas são `pytest` e `pytest-asyncio`; os testes atuais são principalmente síncronos e também usam `fastapi.testclient` e `typer.testing` fornecidos pelas dependências principais.

O Compose oferece a alternativa:

```powershell
docker compose --profile test run --rm tests
```

## Escopo atual

Na coleta atual, a suíte contém 84 testes em 13 arquivos. Ela cobre:

- configuração e descoberta do projeto;
- isolamento de caminhos, busca e seleção de contexto;
- políticas destrutivas, redação de segredos, sessão e persistência;
- cabeçalhos;
- catálogo/registry e adaptador legado;
- agentes, gateway externo e contratos de resultado;
- orquestrador, Git, state machine, checkpoints, jobs, cancelamento e retomada;
- rotas principais da API e a CLI com `TestClient`/`CliRunner`.

Os providers de teste são fakes ou são simulados por monkeypatch. A suíte não exige Codex instalado, rede, login real ou um repositório externo.

## Verificações úteis durante desenvolvimento

```powershell
dev-agent agents doctor
dev-agent doctor
dev-agent test
```

`dev-agent doctor` consulta a prontidão do Codex, que pode fazer uma sonda local de leitura. `dev-agent test` roda o comando definido em `testing.command` no projeto ativo.

## Lacunas de verificação observáveis

- Não há meta de cobertura, relatório de cobertura, lint, formatador, type checker ou configuração de CI no repositório.
- Não há teste de integração contra Codex real; a prontidão é simulada nos testes unitários.
- Não há evidência de testes de concorrência entre processos, segurança de rede, TLS, carga ou persistência em sistemas de arquivos reais além dos cenários unitários.

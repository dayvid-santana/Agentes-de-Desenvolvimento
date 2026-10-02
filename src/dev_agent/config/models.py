"""Modelos Pydantic para dev-agent.yaml."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


def _origemHttp(valor: str) -> str:
    partes = urlsplit(valor)
    if partes.scheme not in {"http", "https"} or not partes.hostname or partes.username or partes.password:
        raise ValueError("Use uma origem HTTP(S) sem credenciais.")
    porta = partes.port or (443 if partes.scheme == "https" else 80)
    host = partes.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"{partes.scheme.lower()}://{host}:{porta}"


class ViewportAplicacao(BaseModel):
    nome: str = Field(min_length=1, max_length=40)
    largura: int = Field(ge=240, le=4096)
    altura: int = Field(ge=320, le=4096)


class PassoJornadaAplicacao(BaseModel):
    acao: str
    alvo: str = ""
    valor: str | None = None
    alteraEstado: bool = False

    @model_validator(mode="after")
    def validarPasso(self):
        acoes = {"ir", "clicar", "preencher", "selecionar", "marcar", "ver_texto", "ver_url", "ver_visivel", "ver_oculto"}
        if self.acao not in acoes:
            raise ValueError(f"Ação de jornada desconhecida: {self.acao}.")
        if self.acao not in {"ir", "ver_url"} and not self.alvo:
            raise ValueError(f"A ação {self.acao} exige um alvo acessível.")
        if self.acao in {"ir", "preencher", "selecionar", "ver_url"} and self.valor is None:
            raise ValueError(f"A ação {self.acao} exige valor.")
        return self


class JornadaAplicacao(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    objetivo: str = Field(min_length=1, max_length=500)
    passos: list[PassoJornadaAplicacao] = Field(min_length=1, max_length=40)


class ConfiguracaoTesteAplicacao(BaseModel):
    """Limites e configuração para exploração automatizada de aplicações web."""

    urlBase: str | None = None
    comandoInicial: list[str] = Field(default_factory=list, max_length=20)
    origensPermitidas: list[str] = Field(default_factory=list, max_length=20)
    arquivoEstadoSessao: str | None = None
    capturarTelas: bool = False
    permitirMutacoes: bool = False
    ambienteDeTesteConfirmado: bool = False
    comandoReset: list[str] = Field(default_factory=list, max_length=20)
    paginasMaximas: int = Field(default=24, ge=1, le=200)
    acoesMaximas: int = Field(default=120, ge=1, le=1000)
    tempoLimiteSegundos: int = Field(default=180, ge=5, le=3600)
    inicializacaoLimiteSegundos: int = Field(default=30, ge=1, le=300)
    limiteAcaoMs: int = Field(default=4000, ge=250, le=60000)
    pastaArtefatos: str = ".dev-agent/usabilidade"
    motor: str = "chromium"
    viewports: list[ViewportAplicacao] = Field(default_factory=lambda: [
        ViewportAplicacao(nome="desktop", largura=1365, altura=900),
        ViewportAplicacao(nome="mobile", largura=390, altura=844),
    ], max_length=8)
    jornadas: list[JornadaAplicacao] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validarConfiguracao(self):
        if self.motor not in {"chromium", "firefox", "webkit"}:
            raise ValueError("motor deve ser chromium, firefox ou webkit.")
        origens = {_origemHttp(item) for item in self.origensPermitidas}
        if self.urlBase:
            origemBase = _origemHttp(self.urlBase)
            partesBase = urlsplit(self.urlBase)
            if partesBase.query or partesBase.fragment:
                raise ValueError("urlBase não pode conter query string ou fragmento.")
            host = urlsplit(self.urlBase).hostname or ""
            local = host.lower() in {"localhost", "127.0.0.1", "::1"}
            if not local and origemBase not in origens:
                raise ValueError("Aplicações fora de loopback exigem a origem exata em origensPermitidas.")
            if not local and not self.ambienteDeTesteConfirmado:
                raise ValueError("Aplicações fora de loopback exigem ambienteDeTesteConfirmado: true.")
            if origens and origemBase not in origens:
                raise ValueError("urlBase precisa constar em origensPermitidas.")
        if self.comandoInicial and not self.urlBase:
            raise ValueError("urlBase é obrigatória quando comandoInicial está configurado.")
        for origem in self.origensPermitidas:
            partes = urlsplit(origem)
            if partes.path not in {"", "/"} or partes.query or partes.fragment:
                raise ValueError("Cada item de origensPermitidas deve conter somente uma origem.")
            if (partes.hostname or "").lower() not in {"localhost", "127.0.0.1", "::1"} and not self.ambienteDeTesteConfirmado:
                raise ValueError("Origens fora de loopback exigem ambienteDeTesteConfirmado: true.")
        for caminho in (self.arquivoEstadoSessao, self.pastaArtefatos):
            if caminho:
                item = Path(caminho)
                if item.is_absolute() or ".." in item.parts:
                    raise ValueError("Caminhos de sessão e artefatos devem permanecer relativos ao projeto.")
        jornadasMutaveis = any(passo.alteraEstado for jornada in self.jornadas for passo in jornada.passos)
        if jornadasMutaveis and not self.permitirMutacoes:
            raise ValueError("Jornadas mutáveis exigem permitirMutacoes: true.")
        if self.permitirMutacoes or jornadasMutaveis:
            if not self.ambienteDeTesteConfirmado or not self.comandoReset:
                raise ValueError("Mutações exigem ambienteDeTesteConfirmado: true e comandoReset configurado.")
        if self.capturarTelas and not self.ambienteDeTesteConfirmado:
            raise ValueError("capturarTelas exige ambienteDeTesteConfirmado: true para evitar persistir dados reais.")
        if not self.viewports:
            raise ValueError("Configure ao menos uma viewport.")
        return self


class ProjectSettings(BaseModel):
    name: str
    author: str = "Dayvid Santana"


class DocumentationSettings(BaseModel):
    priority: list[str] = Field(default_factory=lambda: ["AGENTS.md", "docs/**", "README.md"])


class ContextSettings(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["src/**", "tests/**", "docs/**", "AGENTS.md", "README.md"])
    exclude: list[str] = Field(default_factory=lambda: [".git/**", ".venv/**", "venv/**", "node_modules/**", "dist/**", "build/**", "coverage/**", "__pycache__/**", "*.pyc", "*.log"])
    contextosAgentes: list[str] = Field(default_factory=lambda: ["agent-context/**"])
    max_files: int = Field(default=12, ge=1, le=100)
    max_file_chars: int = Field(default=16_000, ge=1_000)
    max_total_chars: int = Field(default=80_000, ge=5_000)
    dependency_depth: int = Field(default=1, ge=0, le=5)


class TestingSettings(BaseModel):
    command: str = "pytest"


class GitSettings(BaseModel):
    conventional_commits: bool = True
    review_staged: bool = True
    suggest_commit_split: bool = True


class AutoCommitSettings(BaseModel):
    """Limites explícitos para o serviço local de checkpoints Git."""

    enabled: bool = False
    inactivity_seconds: int = Field(default=300, ge=5, le=86_400)
    polling_seconds: int = Field(default=5, ge=1, le=300)
    run_tests: bool = True


class HeaderSettings(BaseModel):
    enabled: bool = True
    author: str = "Dayvid Santana"
    date_format: str = "%d/%m/%Y"
    history: bool = True


class SecuritySettings(BaseModel):
    require_architecture_approval: bool = True
    require_destructive_command_approval: bool = True
    sensitive_patterns: list[str] = Field(default_factory=lambda: [".env", ".env.*", "credentials*", "secrets*", "*.pem", "*.key"])


class DevAgentConfig(BaseModel):
    project: ProjectSettings
    documentation: DocumentationSettings = Field(default_factory=DocumentationSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    testing: TestingSettings = Field(default_factory=TestingSettings)
    testeAplicacao: ConfiguracaoTesteAplicacao = Field(default_factory=ConfiguracaoTesteAplicacao)
    git: GitSettings = Field(default_factory=GitSettings)
    autocommit: AutoCommitSettings = Field(default_factory=AutoCommitSettings)
    headers: HeaderSettings = Field(default_factory=HeaderSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

"""Heurística deliberadamente conservadora para mudanças estruturais."""
from pydantic import BaseModel

class ArchitectureAssessment(BaseModel):
    required: bool
    reason: str | None = None

class ArchitectureGuard:
    keywords = (
        "microserviço", "microservice", "trocar framework", "substituir banco", "nova tecnologia",
        "autenticação", "autorização", "contrato público", "api pública", "login", "oauth", "sso",
        "migração de banco", "schema", "modelo de dados", "fila", "mensageria", "webhook",
        "integração externa", "gateway de pagamento", "deploy", "kubernetes", "multi-tenant",
    )
    def assess(self, objective: str) -> ArchitectureAssessment:
        matched = next((item for item in self.keywords if item in objective.lower()), None)
        return ArchitectureAssessment(required=matched is not None, reason=f"A tarefa menciona decisão estrutural: {matched}." if matched else None)

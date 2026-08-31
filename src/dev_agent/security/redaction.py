"""Redação conservadora de segredos antes de contexto, logs e persistência."""
from __future__ import annotations

# dev-agent
# Autor: Dayvid Santana
# Data: 31/08/2026
# Objetivo: Redigir segredos antes de enviar ou persistir contexto.
# DevAgent-Task: resolve-audit-gaps-20260831

import re


class SensitiveDataRedactor:
    """Remove valores secretos comuns sem alterar a estrutura útil do texto."""

    _patterns = (
        re.compile(r"(?im)(\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd)\b\s*[:=]\s*[\"']?)([^\s\"'`,;]+)"),
        re.compile(r"(?i)(\bBearer\s+)([A-Za-z0-9._~+/-]{12,})"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
        re.compile(r"(?i)(https?://[^\s:/]+:)([^@\s/]+)(@)"),
    )

    @classmethod
    def redact(cls, text: str | None) -> str | None:
        if text is None:
            return None
        redacted = cls._patterns[0].sub(r"\1[REDACTED]", text)
        redacted = cls._patterns[1].sub(r"\1[REDACTED]", redacted)
        redacted = cls._patterns[2].sub("[REDACTED]", redacted)
        return cls._patterns[3].sub(r"\1[REDACTED]\3", redacted)

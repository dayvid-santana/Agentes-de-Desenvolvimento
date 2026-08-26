"""Logging estruturado, sem incluir prompt, output ou segredos."""
from __future__ import annotations
import json
import logging
import sys
from typing import Any

_logger = logging.getLogger("dev_agent")
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)

def event(name: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if not any(word in key.lower() for word in ("secret", "token", "password", "content", "prompt"))}
    _logger.info(json.dumps({"event": name, **safe}, ensure_ascii=False, default=str))

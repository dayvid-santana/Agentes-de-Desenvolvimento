# DevAgent
# Autor: Dayvid Santana
# Data: 26/08/2026
# Objetivo: Disponibilizar ambiente Docker de desenvolvimento e API local

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[dev]"

EXPOSE 8765

CMD ["uvicorn", "dev_agent.api.app:app", "--host", "0.0.0.0", "--port", "8765"]

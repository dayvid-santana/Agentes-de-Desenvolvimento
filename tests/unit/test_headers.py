# DevAgent
# Autor: Dayvid Santana
# Data: 28/08/2026
# Objetivo: Garantir que cabeçalhos existentes não sejam alterados.
# DevAgent
# Autor: Dayvid Santana
# Data: 01/09/2026
# Objetivo: Corrigir propósitos genéricos inseridos pelo comando de cabeçalhos.
from pathlib import Path
from dev_agent.config.models import DevAgentConfig
from dev_agent.headers.service import HeaderService

def service() -> HeaderService:
    return HeaderService(DevAgentConfig.model_validate({"project": {"name": "Demo", "author": "Dayvid Santana"}}))

def test_creation_header_for_python():
    content = service().apply(Path("feature.py"), "def run(): pass\n", "Criar fluxo", "task-1")
    assert content.startswith("# Demo\n# Autor: Dayvid Santana")
    assert "# Objetivo: Criar fluxo" in content

def test_existing_header_is_not_edited():
    initial = service().apply(Path("feature.py"), "x = 1\n", "Criar fluxo", "task-1")
    edited = service().apply(Path("feature.py"), initial + "y = 2\n", "Expandir fluxo", "task-2", existing=initial)
    repeated = service().apply(Path("feature.py"), edited + "z = 3\n", "Expandir fluxo", "task-2", existing=edited)
    assert edited.count("Objetivo:") == 1
    assert repeated.count("Objetivo:") == 1

def test_custom_header_is_preserved():
    content = "# Arquivo legado\n# Copyright Example\n\ndef run(): pass\n"
    assert service().apply(Path("feature.py"), content, "Criar fluxo", "task-1") == content

def test_generic_batch_header_is_repaired_with_file_purpose():
    initial = service().apply(Path("feature.py"), "def run(): pass\n", "Adicionar cabeçalho padrão.", "headers")
    repaired = service().apply(Path("feature.py"), initial, "Executa o fluxo principal da funcionalidade.", "headers", existing=initial)
    assert "Objetivo: Adicionar cabeçalho padrão." not in repaired
    assert "Objetivo: Executa o fluxo principal da funcionalidade." in repaired

def test_json_is_not_modified():
    assert service().apply(Path("package.json"), "{}", "Teste", "task") == "{}"

def test_shebang_remains_first_line():
    content = service().apply(Path("tool.py"), "#!/usr/bin/env python\nprint('x')\n", "Criar ferramenta", "task")
    assert content.startswith("#!/usr/bin/env python\n# Demo")

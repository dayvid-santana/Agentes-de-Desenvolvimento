from pathlib import Path
from dev_agent.config.models import DevAgentConfig
from dev_agent.headers.service import HeaderService

def service() -> HeaderService:
    return HeaderService(DevAgentConfig.model_validate({"project": {"name": "Demo", "author": "Dayvid Santana"}}))

def test_creation_header_for_python():
    content = service().apply(Path("feature.py"), "def run(): pass\n", "Criar fluxo", "task-1")
    assert content.startswith("# Demo\n# Autor: Dayvid Santana")
    assert "# Objetivo: Criar fluxo" in content

def test_edit_history_is_added_once_per_task():
    initial = service().apply(Path("feature.py"), "x = 1\n", "Criar fluxo", "task-1")
    edited = service().apply(Path("feature.py"), initial + "y = 2\n", "Expandir fluxo", "task-2", existing=initial)
    repeated = service().apply(Path("feature.py"), edited + "z = 3\n", "Expandir fluxo", "task-2", existing=edited)
    assert edited.count("Objetivo:") == 2
    assert repeated.count("Objetivo:") == 2

def test_json_is_not_modified():
    assert service().apply(Path("package.json"), "{}", "Teste", "task") == "{}"

def test_shebang_remains_first_line():
    content = service().apply(Path("tool.py"), "#!/usr/bin/env python\nprint('x')\n", "Criar ferramenta", "task")
    assert content.startswith("#!/usr/bin/env python\n# Demo")

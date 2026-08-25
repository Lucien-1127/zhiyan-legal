import ast
from pathlib import Path


DOMAIN_DIR = Path(__file__).parents[2] / "src" / "zhiyan_legal" / "domain"
FORBIDDEN_IMPORT_ROOTS = {
    "fastapi",
    "httpx",
    "requests",
    "openai",
    "google",
    "hermes",
    "codex",
    "agy",
    "sqlalchemy",
    "dotenv",
}


def test_domain_has_no_external_framework_provider_or_io_imports() -> None:
    violations: list[str] = []
    for path in DOMAIN_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{path.name}:{node.lineno}: import {name}")

    assert violations == []


def test_domain_does_not_read_environment_or_send_http() -> None:
    violations: list[str] = []
    forbidden_calls = {
        ("os", "getenv"),
        ("os", "environ"),
        ("httpx", "*"),
        ("requests", "*"),
    }
    for path in DOMAIN_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
                continue
            if (node.value.id, node.attr) in forbidden_calls:
                violations.append(f"{path.name}:{node.lineno}: {node.value.id}.{node.attr}")

    assert violations == []

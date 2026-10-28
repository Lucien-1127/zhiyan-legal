from __future__ import annotations

import re
from pathlib import Path


def _dependency_names(text: str, group: str) -> set[str]:
    match = re.search(
        rf"(?ms)^{re.escape(group)}\s*=\s*\[(?P<body>.*?)^\]",
        text,
    )
    assert match is not None, f"missing optional dependency group: {group}"
    return set(re.findall(r'"([A-Za-z0-9_.-]+)', match.group("body")))


def test_api_runtime_dependencies_are_declared_in_installable_extras() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")

    required = {"fastapi", "slowapi", "uvicorn"}
    assert required <= _dependency_names(project, "api")
    assert required <= _dependency_names(project, "all")

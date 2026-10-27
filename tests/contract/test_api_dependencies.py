from __future__ import annotations

import tomllib
from pathlib import Path


def _dependency_names(group: list[str]) -> set[str]:
    return {
        requirement.split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].strip()
        for requirement in group
    }


def test_api_runtime_dependencies_are_declared_in_installable_extras() -> None:
    project = tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    optional = project["optional-dependencies"]

    required = {"fastapi", "slowapi", "uvicorn"}
    assert required <= _dependency_names(optional["api"])
    assert required <= _dependency_names(optional["all"])

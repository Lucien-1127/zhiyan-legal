"""Repository-wide AST guards for the domain architecture.

These tests deliberately inspect source rather than importing modules.  That
keeps the guard effective even when a forbidden dependency is optional or has
import-time side effects.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
DOMAIN_ROOT = SRC_ROOT / "zhiyan_legal" / "domain"

CANONICAL_TYPES = frozenset(
    {
        "ExecutionContext",
        "Evidence",
        "Claim",
        "Citation",
        "AnswerMeta",
        "Decision",
        "EvidenceLevel",
        "ExecutionStatus",
        "GateResult",
    }
)

# These are framework/provider or application-layer roots.  Standard-library
# imports and pydantic (the domain's declarative validation mechanism) remain
# permitted.
FORBIDDEN_DOMAIN_IMPORTS = frozenset(
    {
        "fastapi",
        "httpx",
        "requests",
        "openai",
        "google",
        "hermes",
        "codex",
        "agy",
        "backend",
        "frontend",
        "committee",
    }
)

SKIPPED_TREE_PARTS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache"})


@dataclass(frozen=True)
class ParsedModule:
    path: Path
    tree: ast.AST | None
    parse_error: str | None = None


def _python_files() -> list[Path]:
    """Return repository Python sources, excluding tooling environments."""
    return sorted(
        path
        for path in PROJECT_ROOT.rglob("*.py")
        if not any(part in SKIPPED_TREE_PARTS for part in path.relative_to(PROJECT_ROOT).parts)
    )


def _parse_modules() -> list[ParsedModule]:
    modules: list[ParsedModule] = []
    for path in _python_files():
        try:
            modules.append(
                ParsedModule(
                    path=path,
                    tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
                )
            )
        except (OSError, SyntaxError) as exc:
            modules.append(ParsedModule(path=path, tree=None, parse_error=str(exc)))
    return modules


def _location(path: Path, lineno: int = 1) -> str:
    return f"{path.relative_to(PROJECT_ROOT)}:{lineno}"


def _is_domain_file(path: Path) -> bool:
    try:
        path.relative_to(DOMAIN_ROOT)
    except ValueError:
        return False
    return True


def _import_names(node: ast.AST) -> list[str]:
    """Return the import targets represented by one import statement."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if node.level:
            return ["." * node.level + (module or alias.name) for alias in node.names]
        return [module or alias.name for alias in node.names]
    return []


def _module_name(path: Path) -> str | None:
    """Translate a source path under src/ into its importable module name."""
    try:
        relative = path.relative_to(SRC_ROOT).with_suffix("")
    except ValueError:
        return None
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolved_from_import(path: Path, node: ast.ImportFrom, alias: str) -> str:
    """Resolve an absolute or relative ``from`` import to a module prefix."""
    if not node.level:
        return f"{node.module}.{alias}" if node.module else alias

    current = _module_name(path)
    if current is None:
        return "." * node.level + (node.module or alias)
    package_parts = current.split(".")
    # A module imports relative to its containing package; __init__ already
    # resolves to the package itself in _module_name().
    if path.name != "__init__.py":
        package_parts.pop()
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base_parts.extend(node.module.split("."))
    base_parts.append(alias)
    return ".".join(base_parts)


def _parse_errors(modules: list[ParsedModule]) -> list[str]:
    return [
        f"{_location(module.path)}: unable to parse Python source: {module.parse_error}"
        for module in modules
        if module.parse_error is not None
    ]


def test_repository_python_sources_are_parseable() -> None:
    violations = _parse_errors(_parse_modules())
    assert violations == [], "\n".join(violations)


def test_canonical_types_have_one_writable_definition_in_domain() -> None:
    """Only domain may contain the concrete class/enum declarations."""
    violations: list[str] = []
    definitions: dict[str, list[str]] = {name: [] for name in CANONICAL_TYPES}

    for module in _parse_modules():
        if module.tree is None:
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ClassDef) or node.name not in CANONICAL_TYPES:
                continue
            location = _location(module.path, node.lineno)
            definitions[node.name].append(location)
            if not _is_domain_file(module.path):
                violations.append(
                    f"Rule A: {location} declares canonical type {node.name}; "
                    "concrete definitions must live in src/zhiyan_legal/domain/"
                )

    for name, locations in definitions.items():
        # Some historical names are reserved by the contract (for example,
        # Decision) but are not materialised by this package.  The guard is
        # concerned with duplicate writable definitions, not with requiring
        # every reserved name to exist.
        if len(locations) > 1:
            rendered = ", ".join(locations) if locations else "<missing>"
            violations.append(
                f"Rule A: canonical type {name} has {len(locations)} writable "
                f"definitions ({rendered}); expected at most one in domain"
            )

    assert violations == [], "\n".join(violations)


def test_domain_has_no_external_or_high_level_imports() -> None:
    violations: list[str] = []
    for module in _parse_modules():
        if module.tree is None or not _is_domain_file(module.path):
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported in _import_names(node):
                root = imported.lstrip(".").split(".", 1)[0]
                if root in FORBIDDEN_DOMAIN_IMPORTS:
                    violations.append(
                        f"Rule B: {_location(module.path, node.lineno)} imports {imported}"
                    )

    assert violations == [], "\n".join(violations)


def test_dependency_direction_is_one_way() -> None:
    violations: list[str] = []

    for module in _parse_modules():
        if module.tree is None:
            continue

        if _is_domain_file(module.path):
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Import):
                    targets = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    targets = [
                        _resolved_from_import(module.path, node, alias.name)
                        for alias in node.names
                    ]
                else:
                    continue
                for target in targets:
                    if target.startswith("zhiyan_legal.") and not target.startswith(
                        "zhiyan_legal.domain"
                    ):
                        violations.append(
                            f"Rule C: {_location(module.path, node.lineno)} domain imports "
                            f"non-domain module {target}"
                        )

        # ``src`` and a possible legacy ``core`` tree are the inward-facing
        # application layers.  They must never acquire a dependency on the
        # compatibility/backend layer.
        in_core_or_src = module.path.is_relative_to(SRC_ROOT) or module.path.is_relative_to(
            PROJECT_ROOT / "core"
        )
        if in_core_or_src:
            for node in ast.walk(module.tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for imported in _import_names(node):
                    target = imported.lstrip(".")
                    if target == "backend" or target.startswith("backend."):
                        violations.append(
                            f"Rule C: {_location(module.path, node.lineno)} imports {imported}"
                        )

    assert violations == [], "\n".join(violations)

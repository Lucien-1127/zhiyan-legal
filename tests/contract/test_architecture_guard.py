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
ZHIYAN_ROOT = SRC_ROOT / "zhiyan_legal"
PIPELINE_ROOT = ZHIYAN_ROOT / "pipeline"
TOOLS_ROOT = ZHIYAN_ROOT / "tools"
VERIFICATION_ROOT = ZHIYAN_ROOT / "verification"
APPLICATION_ROOT = ZHIYAN_ROOT / "application"
PROVIDERS_ROOT = ZHIYAN_ROOT / "providers"
INTERFACES_ROOT = ZHIYAN_ROOT / "interfaces"
COMMITTEE_ROOT = ZHIYAN_ROOT / "committee"
LEGACY_COMMITTEE_ROOT = PROJECT_ROOT / "committee"
LEGACY_COMMITTEE_ADAPTER = LEGACY_COMMITTEE_ROOT / "api" / "adapter.py"

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

# Phase 2 is a lower-layer boundary.  The two provider modules are explicit
# adapter boundaries used by the existing tool implementations; the adapter
# may call them, but no other Phase 2 layer may depend on an application
# module.  Keeping this exception named makes any future provider coupling
# visible in this contract rather than silently widening the allow-list.
TOOL_PROVIDER_BOUNDARIES = frozenset(
    {
        "zhiyan_legal.judicial_api",
        "zhiyan_legal.regulation_tracker",
    }
)
PHASE2_LAYER_ROOTS = {
    "domain": DOMAIN_ROOT,
    "pipeline": PIPELINE_ROOT,
    "tools": TOOLS_ROOT,
    "verification": VERIFICATION_ROOT,
}
PHASE3_LAYER_ROOTS = {
    "application": APPLICATION_ROOT,
    "providers": PROVIDERS_ROOT,
    "interfaces": INTERFACES_ROOT,
}
# ``interfaces/http_regulation.py`` is a pre-existing transport compatibility
# surface.  Its tracker/diff imports are not model execution dependencies and
# remain explicitly named until that legacy monitoring API is migrated behind
# an application service.  New interfaces have no such exception.
LEGACY_INTERFACE_SUPPORT = frozenset(
    {
        "zhiyan_legal.regulation_diff",
        "zhiyan_legal.regulation_tracker",
    }
)
FORBIDDEN_APPLICATION_ROOTS = frozenset(
    {
        "backend",
        "frontend",
        "committee",
        "agents",
        "deployment",
        "docker",
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


def _is_committee_file(path: Path) -> bool:
    """Return whether a source file belongs to the canonical vNext committee."""
    try:
        path.relative_to(COMMITTEE_ROOT)
    except ValueError:
        return False
    return True


def _phase2_layer(path: Path) -> str | None:
    for layer, root in PHASE2_LAYER_ROOTS.items():
        try:
            path.relative_to(root)
        except ValueError:
            continue
        return layer
    return None


def _phase3_layer(path: Path) -> str | None:
    for layer, root in PHASE3_LAYER_ROOTS.items():
        try:
            path.relative_to(root)
        except ValueError:
            continue
        return layer
    return None


def _allowed_phase3_target(layer: str, target: str, path: Path) -> bool:
    """Return whether one Phase 3 import stays within its dependency cone."""
    if not target.startswith("zhiyan_legal."):
        return True

    allowed = {
        "application": ("domain", "pipeline", "providers", "tools", "verification", "application"),
        "providers": ("domain", "providers"),
        "interfaces": ("application", "domain", "pipeline", "interfaces"),
    }[layer]
    if any(
        target == f"zhiyan_legal.{prefix}"
        or target.startswith(f"zhiyan_legal.{prefix}.")
        for prefix in allowed
    ):
        return True
    return path.is_relative_to(INTERFACES_ROOT) and any(
        target == boundary or target.startswith(f"{boundary}.")
        for boundary in LEGACY_INTERFACE_SUPPORT
    )


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


def _resolved_targets(path: Path, node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [
            _resolved_from_import(path, node, alias.name)
            for alias in node.names
        ]
    return []


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


def test_phase2_layers_only_use_domain_and_their_own_layer() -> None:
    """Pipeline, tools, and verification cannot acquire sibling app imports."""

    violations: list[str] = []
    for module in _parse_modules():
        layer = _phase2_layer(module.path)
        if module.tree is None or layer is None:
            continue

        own_prefix = f"zhiyan_legal.{layer}"
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_targets(module.path, node):
                if not target.startswith("zhiyan_legal"):
                    continue
                if (
                    target.startswith("zhiyan_legal.domain")
                    or target.startswith(own_prefix)
                    or any(
                        target == boundary or target.startswith(f"{boundary}.")
                        for boundary in TOOL_PROVIDER_BOUNDARIES
                    )
                ):
                    continue
                violations.append(
                    f"Rule D: {_location(module.path, node.lineno)} {layer} imports {target}; "
                    "Phase 2 layers may depend only on domain, themselves, and named provider boundaries"
                )

    assert violations == [], "\n".join(violations)


def test_phase3_layers_have_explicit_one_way_dependency_cones() -> None:
    """Application, provider, and interface imports cannot cross layers."""

    violations: list[str] = []
    for module in _parse_modules():
        layer = _phase3_layer(module.path)
        if module.tree is None or layer is None:
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_targets(module.path, node):
                if not _allowed_phase3_target(layer, target, module.path):
                    violations.append(
                        f"Rule D: {_location(module.path, node.lineno)} {layer} imports {target}; "
                        "allowed dependencies are application: domain/pipeline/providers/tools/verification, "
                        "providers: domain, interfaces: application/domain/pipeline"
                    )

    assert violations == [], "\n".join(violations)


def test_committee_layer_has_only_canonical_dependency_cones() -> None:
    """Committee code may compare candidates, but cannot reach orchestration.

    Relative imports are resolved through the same AST resolver used by the
    other architecture rules.  The committee package itself is allowed as an
    internal dependency; its outward dependency cone is exactly domain and
    providers.
    """

    violations: list[str] = []
    allowed_prefixes = (
        "zhiyan_legal.committee",
        "zhiyan_legal.domain",
        "zhiyan_legal.providers",
    )

    for module in _parse_modules():
        if module.tree is None or not _is_committee_file(module.path):
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_targets(module.path, node):
                if target.startswith("zhiyan_legal.") and not target.startswith(
                    allowed_prefixes
                ):
                    violations.append(
                        f"Rule F: {_location(module.path, node.lineno)} committee imports "
                        f"{target}; allowed dependencies are committee/domain/providers"
                    )

    assert violations == [], "\n".join(violations)


def test_legacy_committee_entrypoint_uses_the_canonical_adapter() -> None:
    """The historical HTTP entrypoint must delegate to Committee vNext."""

    parsed = next(
        module
        for module in _parse_modules()
        if module.path == LEGACY_COMMITTEE_ADAPTER
    )
    assert parsed.tree is not None, "legacy committee adapter must be parseable"

    imported_targets = {
        target
        for node in ast.walk(parsed.tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for target in _resolved_targets(parsed.path, node)
    }
    assert any(
        target == "zhiyan_legal.committee"
        or target.startswith("zhiyan_legal.committee.")
        for target in imported_targets
    )

    committee_constructor_lines = [
        node.lineno
        for node in ast.walk(parsed.tree)
        if isinstance(node, ast.Name) and node.id == "CommitteeEngine"
    ]
    committee_run_lines = [
        node.lineno
        for node in ast.walk(parsed.tree)
        if isinstance(node, ast.Attribute) and node.attr == "run"
    ]
    assert committee_constructor_lines
    assert committee_run_lines


def test_phase2_and_phase3_non_application_layers_cannot_execute_committee() -> None:
    """No lower or transport layer may bypass the application boundary.

    The historical adapter is checked separately above.  Within ``src/``,
    only the application package may import or invoke the canonical committee;
    phase 2 and phase 3 layers must remain below that decision boundary.
    """

    violations: list[str] = []
    for module in _parse_modules():
        if module.tree is None:
            continue
        layer = _phase2_layer(module.path) or _phase3_layer(module.path)
        if layer is None or layer == "application":
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_targets(module.path, node):
                if target == "zhiyan_legal.committee" or target.startswith(
                    "zhiyan_legal.committee."
                ):
                    violations.append(
                        f"Rule G: {_location(module.path, node.lineno)} {layer} imports "
                        f"{target}; committee execution belongs to application"
                    )

    assert violations == [], "\n".join(violations)


def test_high_level_or_forbidden_application_modules_cannot_enter_phase2_layers() -> None:
    """No application/compatibility layer may become a Phase 2 dependency."""

    violations: list[str] = []
    for module in _parse_modules():
        source_layer = _phase2_layer(module.path)
        if module.tree is None or not module.path.is_relative_to(SRC_ROOT):
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_targets(module.path, node):
                root = target.split(".", 1)[0]
                if root in FORBIDDEN_APPLICATION_ROOTS:
                    violations.append(
                        f"Rule E: {_location(module.path, node.lineno)} "
                        f"{source_layer or 'high-level'} imports {target}"
                    )
                    continue

                # Root application modules may consume canonical domain data,
                # but they must not pull execution into a Phase 2 lower layer.
                if (
                    target.startswith("zhiyan_legal.pipeline")
                    or target.startswith("zhiyan_legal.tools")
                    or target.startswith("zhiyan_legal.verification")
                ) and source_layer is None and not module.path.is_relative_to(APPLICATION_ROOT):
                    violations.append(
                        f"Rule E: {_location(module.path, node.lineno)} high-level module imports {target}"
                    )

    assert violations == [], "\n".join(violations)

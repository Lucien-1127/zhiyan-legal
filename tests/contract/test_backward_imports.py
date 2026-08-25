"""Contract tests for the registered compatibility boundary."""

from __future__ import annotations

import importlib
import warnings

import pytest


DEPRECATED_IMPORTS = {
    "zhiyan_legal.runner": (
        "zhiyan_legal.engine",
        ("run_llm",),
    ),
    "backend.engine": (
        "zhiyan_legal.engine",
        (
            "ZhiyanEngine",
            "EngineConfig",
            "QueryResult",
            "EngineError",
            "LLMConnectionError",
            "LLMTimeoutError",
            "LLMRateLimitError",
            "LLMResponseError",
            "validate_output",
            "discover_api_key",
        ),
    ),
    "committee_core": (
        None,
        (
            "GovernanceContract",
            "GovernanceViolationError",
            "PolicyViolation",
            "DebateEngine",
            "JudicialScraper",
        ),
    ),
    "committee_core.policies": (
        "committee.policies",
        ("GovernanceContract", "GovernanceViolationError", "PolicyViolation"),
    ),
    "committee_core.reasoning": (
        "committee.reasoning",
        ("DebateEngine", "JudicialScraper"),
    ),
}


REMOVED_IMPORTS = (
    "committee_core.policies.governance_contract",
    "committee_core.reasoning.debate_engine",
    "committee_core.reasoning.scraping_engine",
)


@pytest.mark.parametrize("legacy_path", DEPRECATED_IMPORTS)
def test_deprecated_import_reexports_canonical_symbols(legacy_path: str):
    """Every registered legacy import is an identity-preserving re-export."""
    canonical_path, symbols = DEPRECATED_IMPORTS[legacy_path]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        legacy = importlib.import_module(legacy_path)

    assert any(item.category is DeprecationWarning for item in caught)
    canonical = (
        importlib.import_module(canonical_path)
        if canonical_path is not None
        else None
    )
    for symbol in symbols:
        assert hasattr(legacy, symbol), f"{legacy_path}.{symbol} is missing"
        if canonical is not None:
            assert getattr(legacy, symbol) is getattr(canonical, symbol)


def test_committee_root_reexports_its_canonical_submodules():
    legacy = importlib.import_module("committee_core")
    policies = importlib.import_module("committee.policies")
    reasoning = importlib.import_module("committee.reasoning")

    for symbol in ("GovernanceContract", "GovernanceViolationError", "PolicyViolation"):
        assert getattr(legacy, symbol) is getattr(policies, symbol)
    for symbol in ("DebateEngine", "JudicialScraper"):
        assert getattr(legacy, symbol) is getattr(reasoning, symbol)


@pytest.mark.parametrize("removed_path", REMOVED_IMPORTS)
def test_removed_duplicate_modules_are_not_importable(removed_path: str):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(removed_path)


def test_compatibility_imports_do_not_write_to_stdout(capsys):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module("zhiyan_legal.runner")
        importlib.import_module("backend.engine")
        importlib.import_module("committee_core")

    assert capsys.readouterr().out == ""

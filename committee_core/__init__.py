"""Deprecated compatibility imports for the former ``committee_core`` API."""
import warnings

warnings.warn(
    "committee_core 已棄用，請改用 committee.policies / committee.reasoning",
    DeprecationWarning,
    stacklevel=2,
)

from committee.policies.governance_contract import (  # noqa: F401
    GovernanceContract,
    GovernanceViolationError,
    PolicyViolation,
)
from committee.reasoning.debate_engine import DebateEngine  # noqa: F401
from committee.reasoning.scraping_engine import JudicialScraper  # noqa: F401

__all__ = [
    "GovernanceContract",
    "GovernanceViolationError",
    "PolicyViolation",
    "DebateEngine",
    "JudicialScraper",
]

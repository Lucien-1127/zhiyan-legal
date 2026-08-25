"""Deprecated compatibility imports for the former ``committee_core`` API."""
import warnings

warnings.warn(
    "committee_core 已棄用，請改用 committee.policies / committee.reasoning",
    DeprecationWarning,
    stacklevel=2,
)

from committee.policies import (  # noqa: F401
    GovernanceContract,
    GovernanceViolationError,
    PolicyViolation,
)
from committee.reasoning import (  # noqa: F401
    DebateEngine,
    JudicialScraper,
)

__all__ = [
    "GovernanceContract",
    "GovernanceViolationError",
    "PolicyViolation",
    "DebateEngine",
    "JudicialScraper",
]

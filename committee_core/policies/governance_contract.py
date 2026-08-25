"""Deprecated compatibility imports for the governance contract."""
import warnings

warnings.warn(
    "committee_core.policies.governance_contract 已棄用，請改用 "
    "committee.policies.governance_contract",
    DeprecationWarning,
    stacklevel=2,
)

from committee.policies.governance_contract import (  # noqa: E402, F401
    GovernanceContract,
    GovernanceViolationError,
    PolicyViolation,
)

__all__ = ["GovernanceContract", "GovernanceViolationError", "PolicyViolation"]

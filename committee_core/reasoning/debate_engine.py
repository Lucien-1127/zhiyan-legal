"""Deprecated compatibility import for the debate engine."""
import warnings

warnings.warn(
    "committee_core.reasoning.debate_engine 已棄用，請改用 "
    "committee.reasoning.debate_engine",
    DeprecationWarning,
    stacklevel=2,
)

from committee.reasoning.debate_engine import DebateEngine  # noqa: E402, F401

__all__ = ["DebateEngine"]

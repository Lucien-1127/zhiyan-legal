"""Deprecated compatibility imports for :mod:`committee.reasoning`."""
import warnings

warnings.warn(
    "committee_core.reasoning 已棄用，請改用 committee.reasoning",
    DeprecationWarning,
    stacklevel=2,
)

from committee.reasoning import *  # noqa: F401, F403
from committee.reasoning import __all__

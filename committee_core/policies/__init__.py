"""Deprecated compatibility imports for :mod:`committee.policies`."""
import warnings

warnings.warn(
    "committee_core.policies 已棄用，請改用 committee.policies",
    DeprecationWarning,
    stacklevel=2,
)

from committee.policies import *  # noqa: F401, F403
from committee.policies import __all__

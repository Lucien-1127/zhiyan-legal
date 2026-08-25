"""Compatibility re-export for the canonical judgment schema.

The implementation intentionally lives under ``src/zhiyan_legal``.  Keep
this module importable for consumers that still use the pre-migration path.
Deprecated as an implementation location since v3.9.4.
"""

from src.zhiyan_legal.schemas.judgment import *  # noqa: F401,F403
from src.zhiyan_legal.schemas.judgment import __all__

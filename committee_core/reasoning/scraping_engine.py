"""Deprecated compatibility import for the judicial scraper."""
import warnings

warnings.warn(
    "committee_core.reasoning.scraping_engine 已棄用，請改用 "
    "committee.reasoning.scraping_engine",
    DeprecationWarning,
    stacklevel=2,
)

from committee.reasoning.scraping_engine import JudicialScraper  # noqa: E402, F401

__all__ = ["JudicialScraper"]

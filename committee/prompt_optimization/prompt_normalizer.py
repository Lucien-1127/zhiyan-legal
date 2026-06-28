"""
prompt_normalizer — Convert each model's free-form review into structured PromptClaim list.

Each reviewer receives the same system prompt (templates/prompts/reviewer_system.txt)
that tells them to output JSON. This normalizer parses that JSON and validates
against the PromptClaim schema.
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Optional

from .prompt_quality import PromptClaim, PromptDimension, Severity, ReviewerModel

logger = logging.getLogger("prompt_normalizer")

# ── Reviewer system prompt template dir ────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


# ── JSON extraction helpers ─────────────────────────────


def _extract_json(raw: str) -> list[dict]:
    """Extract the issues array from model output.

    Handles:
      - Plain JSON
      - JSON wrapped in ```json ... ``` code blocks
      - Free-form text with JSON embedded
    """
    # Try code block first
    if "```json" in raw:
        blocks = re.findall(r"```json\s*\n?(.*?)\n?```", raw, re.DOTALL)
        for block in reversed(blocks):
            try:
                data = json.loads(block.strip())
                if isinstance(data, dict) and "issues" in data:
                    return data["issues"]
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue

    # Try direct parse
    try:
        data = json.loads(raw.strip())
        if isinstance(data, list):
            return data
        if "issues" in data:
            return data["issues"]
        return [data]
    except json.JSONDecodeError:
        pass

    # Last resort: find JSON-like array in text
    array_match = re.search(r'\[\s*\{.*?\}\s*\]', raw, re.DOTALL)
    if array_match:
        try:
            data = json.loads(array_match.group())
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            pass

    logger.warning("Cannot extract JSON from model output (len=%d)", len(raw))
    return []


def _safe_dimension(val: str) -> PromptDimension:
    """Map string → PromptDimension with fallback."""
    for d in PromptDimension:
        if d.value == val or d.name.lower() == val.lower():
            return d
    logger.debug("Unknown dimension '%s', defaulting to STRUCTURE", val)
    return PromptDimension.STRUCTURE


def _safe_severity(val: str) -> Severity:
    """Map string → Severity with fallback."""
    for s in Severity:
        if s.value == val or s.name.lower() == val.lower():
            return s
    return Severity.MINOR


def _parse_confidence(val: object) -> float:
    """Parse confidence from various formats."""
    if isinstance(val, (int, float)):
        return max(0.0, min(1.0, float(val)))
    if isinstance(val, str):
        try:
            return max(0.0, min(1.0, float(val.replace("%", "")) / 100))
        except (ValueError, AttributeError):
            pass
    return 0.8  # default


# ── Normalizer ──────────────────────────────────────────


class PromptNormalizer:
    """Convert model output to list[PromptClaim]."""

    def normalize(self, raw: str, reviewer: ReviewerModel) -> list[PromptClaim]:
        """Parse raw model output → validated PromptClaim list."""
        items = _extract_json(raw)
        claims: list[PromptClaim] = []

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if not item.get("issue"):
                continue

            try:
                claim = PromptClaim(
                    dimension   = _safe_dimension(item.get("dimension", "structure")),
                    severity    = _safe_severity(item.get("severity", "minor")),
                    reviewer    = reviewer,
                    location    = str(item.get("location", f"item_{i}")),
                    issue       = str(item["issue"]),
                    suggestion  = str(item.get("suggestion", "")),
                    confidence  = _parse_confidence(item.get("confidence", 0.8)),
                    evidence    = str(item["evidence"]) if item.get("evidence") else None,
                    tags        = item.get("tags", []),
                )
                claims.append(claim)
            except (ValueError, TypeError) as e:
                logger.warning("Skipping invalid claim at index %d: %s", i, e)

        logger.info(
            "Normalized %s → %d claims (%.1f%% parsed rate)",
            reviewer.value, len(claims),
            len(claims) / max(len(items), 1) * 100,
        )
        return claims

    def load_reviewer_prompt(self, reviewer: ReviewerModel) -> str:
        """Load the system prompt template for a given reviewer model."""
        template_path = _TEMPLATE_DIR / f"{reviewer.value}.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        # Fallback to generic
        generic = _TEMPLATE_DIR / "generic.md"
        if generic.exists():
            return generic.read_text(encoding="utf-8")
        return "Review the following prompt and output issues as JSON."


# ── Semantic equivalence (simplified for prompt domain) ─


def are_claims_equivalent(a: PromptClaim, b: PromptClaim) -> bool:
    """Check if two claims from different reviewers refer to the same issue.

    Heuristic: same dimension + similar issue text.
    """
    if a.dimension != b.dimension:
        return False

    # Normalize and compare issue text
    a_words = set(a.issue.lower().replace(" ", "").replace("，", "").replace("。", "")[:40])
    b_words = set(b.issue.lower().replace(" ", "").replace("，", "").replace("。", "")[:40])

    if not a_words or not b_words:
        return False

    overlap = len(a_words & b_words)
    union = len(a_words | b_words)
    return (overlap / union) > 0.35  # 35% character overlap → likely same issue

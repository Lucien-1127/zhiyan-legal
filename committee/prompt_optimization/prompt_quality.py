"""
prompt_quality — PromptClaim schema for prompt optimization committee

Compatible with existing committee ConsensusLabel taxonomy while adding
prompt-specific dimensions and severity levels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ── Enums ───────────────────────────────────────────────

class PromptDimension(Enum):
    """Which aspect of the prompt is being reviewed."""
    STRUCTURE       = "structure"         # Role/Task/Output/Constraints sections
    COMPLETENESS    = "completeness"      # Required parameters present?
    PRECISION       = "precision"         # Ambiguous vs unambiguous instructions
    READABILITY     = "readability"       # AI-taste, audience calibration, natural flow
    EDGE_CASES      = "edge_cases"        # Boundary conditions, failure modes
    MISSING_PARAMS  = "missing_params"    # Parameters the prompt forgot to define


class Severity(Enum):
    """How serious is this issue for the final output."""
    CRITICAL = "critical"   # Affects output correctness
    MAJOR    = "major"      # Lowers output quality
    MINOR    = "minor"      # Style / readability improvement


class ReviewerModel(Enum):
    """Which model produced the review."""
    DEEPSEEK = "deepseek_v4_flash"
    GEMINI   = "gemini_3_5_flash"
    CLAUDE   = "claude"


# Re-export existing committee ConsensusLabel for cross-reference
from committee.core import ConsensusLabel  # noqa: F401


# ── Data Classes ────────────────────────────────────────

@dataclass
class PromptClaim:
    """A single structured claim about a prompt quality issue."""
    dimension:   PromptDimension
    severity:    Severity
    reviewer:    ReviewerModel
    location:    str                # e.g. "CONSTRAINTS section", "line 3"
    issue:       str                # Problem description (Chinese preferred)
    suggestion:  str                # Fix suggestion
    confidence:  float              # 0.0–1.0
    evidence:    Optional[str] = None  # Excerpt from the source prompt
    tags:        list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimension"] = self.dimension.value
        d["severity"] = self.severity.value
        d["reviewer"] = self.reviewer.value
        return d


@dataclass
class PromptReviewReport:
    """A single model's review of the prompt — parallel to ModelVerdict."""
    reviewer: ReviewerModel
    prompt_slug: str              # Short ID for the prompt under review
    claims: list[PromptClaim]     # All issues found
    summary: str = ""             # Free-form summary
    raw_response: str = ""        # Full raw output (for audit)
    elapsed_s: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reviewer": self.reviewer.value,
            "prompt_slug": self.prompt_slug,
            "claims": [c.to_dict() for c in self.claims],
            "summary": self.summary[:200],
            "elapsed_s": round(self.elapsed_s, 2),
            "error": self.error,
        }


# ── Clustering (simplified for prompt domain) ──────────

@dataclass
class ClaimCluster:
    """Cross-model cluster of the same prompt issue."""
    canonical_key: str               # e.g. "precision:role_boundary"
    dimension: PromptDimension
    models: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    severities: list[Severity] = field(default_factory=list)
    label: ConsensusLabel = ConsensusLabel.CONSENSUS
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "canonical_key": self.canonical_key,
            "dimension": self.dimension.value,
            "models": self.models,
            "label": self.label.value,
            "detail": self.detail,
            "severities": [s.value for s in self.severities],
        }


# ── Prompt committee report ─────────────────────────────

@dataclass
class PromptCommitteeReport:
    """Final report — what to fix, who found it, how urgent."""
    prompt_slug: str
    prompt_vN: str                    # Original version
    reports: list[PromptReviewReport]
    clusters: list[ClaimCluster]      # After consensus mapping
    consensus_count: int = 0
    disagreement_count: int = 0
    blind_spot_count: int = 0
    unique_insight_count: int = 0

    def to_dict(self) -> dict:
        return {
            "prompt_slug": self.prompt_slug,
            "consensus": self.consensus_count,
            "disagreement": self.disagreement_count,
            "blind_spot": self.blind_spot_count,
            "unique_insight": self.unique_insight_count,
            "clusters": [c.to_dict() for c in self.clusters],
        }

    def print_summary(self) -> str:
        lines = [
            f"📋 Prompt Committee: {self.prompt_slug}",
            f"   ✅ 共識: {self.consensus_count}",
            f"   ⚠️  分歧: {self.disagreement_count}",
            f"   ❌ 盲區: {self.blind_spot_count}",
            f"   🔍 獨特發現: {self.unique_insight_count}",
        ]
        return "\n".join(lines)

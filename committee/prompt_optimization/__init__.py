"""
prompt_optimization — Multi-model committee for prompt quality optimization.

Modules:
  - prompt_quality.py  → PromptClaim schema + data classes
  - prompt_normalizer.py → Normalize model outputs to claims
  - dispatch.py        → Consensus → subagent routing
  - quality_gate.py    → G1–G5 validation layer
  - consensus.py       → Consensus mapper (prompt-aware clustering)

Usage:
    from committee.prompt_optimization.pipeline import run_prompt_review
    report = await run_prompt_review(prompt_text)
"""

from .prompt_quality import (
    PromptClaim, PromptDimension, Severity, ReviewerModel, ConsensusLabel,
    ClaimCluster, PromptReviewReport, PromptCommitteeReport,
)
from .prompt_normalizer import PromptNormalizer, are_claims_equivalent
from .dispatch import ConsensusDispatcher, DispatchAction, ActionType
from .quality_gate import run_all as run_quality_gates, format_report, GateResult

__all__ = [
    "PromptClaim", "PromptDimension", "Severity", "ReviewerModel", "ConsensusLabel",
    "ClaimCluster", "PromptReviewReport", "PromptCommitteeReport",
    "PromptNormalizer", "are_claims_equivalent",
    "ConsensusDispatcher", "DispatchAction", "ActionType",
    "run_quality_gates", "format_report", "GateResult",
]

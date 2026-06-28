"""
pipeline — Entry point for the full prompt review pipeline.

Usage:
    from committee.prompt_optimization import pipeline
    report, actions, gates = await pipeline.run_prompt_review(prompt_text, slug="v4.0")

Flow:
  1. Normalizer loads reviewer prompts
  2. Each reviewer model (DeepSeek/Gemini/Agnes) runs in parallel
  3. Normalizer parses each response → PromptClaim list
  4. Consensus clusters claims across reviewers
  5. Dispatcher routes clusters → actions
  6. Quality gates run on original prompt
  7. All results returned as a dict
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .prompt_quality import (
    ReviewerModel, ConsensusLabel,
    PromptReviewReport, PromptCommitteeReport,
)
from .prompt_normalizer import PromptNormalizer
from .consensus import generate_report
from .dispatch import ConsensusDispatcher, ActionType
from .quality_gate import run_all as run_quality_gates, format_report

logger = logging.getLogger("pipeline")

# Default reviewers
DEFAULT_REVIEWERS = [
    ReviewerModel.DEEPSEEK,
    ReviewerModel.GEMINI,
    ReviewerModel.AGNES,
]


@dataclass
class PipelineResult:
    """Full pipeline output."""
    report: PromptCommitteeReport
    actions: list
    quality_gates: dict
    prompt_vN: str
    prompt_vN1: Optional[str] = None  # Optimized version (if applied)

    def print_summary(self) -> str:
        lines = [
            self.report.print_summary(),
            "",
            "📋 Dispatch Actions:",
        ]
        for a in self.actions:
            lines.append(f"  {a.action_type.value:16s} P{a.priority} [{a.cluster.dimension.value}] {a.cluster.canonical_key[:40]}")

        lines.append("")
        lines.append(format_report(self.quality_gates))
        return "\n".join(lines)


# ── Async API call simulator ────────────────────────────


async def _call_reviewer(
    reviewer: ReviewerModel,
    prompt_text: str,
    normalizer: PromptNormalizer,
) -> PromptReviewReport:
    """Call a reviewer model and normalize its output.

    In production, this calls the actual LLM API.
    For now, returns a structured error to signal "not yet wired".
    """
    slug = f"prompt_{hash(prompt_text) % 10000:04x}"

    # Load reviewer prompt
    system_prompt = normalizer.load_reviewer_prompt(reviewer)

    # TODO: wire actual API call here
    # For now, return a placeholder indicating this needs API integration
    return PromptReviewReport(
        reviewer=reviewer,
        prompt_slug=slug,
        claims=[],
        summary=f"Pipeline scaffolding — API call to {reviewer.value} not yet wired",
        raw_response="",
        elapsed_s=0.0,
        error="API_CALL_NOT_WIRED — implement in pipeline._call_reviewer()",
    )


# ── Sync quality gates ──────────────────────────────────


def _run_gates(prompt: str) -> dict:
    """Run G1–G5 on the prompt."""
    return run_quality_gates(prompt)


# ── Main pipeline ───────────────────────────────────────


async def run_prompt_review(
    prompt_text: str,
    slug: str = "prompt",
    reviewers: Optional[list[ReviewerModel]] = None,
) -> PipelineResult:
    """Run the full prompt optimization pipeline.

    Parameters
    ----------
    prompt_text : str
        The writer system prompt to review.
    slug : str
        Short identifier for the prompt version.
    reviewers : list[ReviewerModel], optional
        Which models to use. Defaults to DeepSeek + Gemini + Agnes.

    Returns
    -------
    PipelineResult with report, actions, and quality gate results.
    """
    if reviewers is None:
        reviewers = DEFAULT_REVIEWERS

    normalizer = PromptNormalizer()

    # Phase 1: Parallel review
    logger.info("Phase 1: Reviewing prompt with %d models", len(reviewers))
    start = time.perf_counter()

    tasks = [_call_reviewer(r, prompt_text, normalizer) for r in reviewers]
    reports = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions
    valid_reports: list[PromptReviewReport] = []
    for i, result in enumerate(reports):
        if isinstance(result, BaseException):
            logger.error("Reviewer %s failed: %s", reviewers[i].value, result)
            valid_reports.append(PromptReviewReport(
                reviewer=reviewers[i],
                prompt_slug=slug,
                claims=[],
                summary="API call failed",
                error=str(result),
            ))
        else:
            valid_reports.append(result)

    elapsed = time.perf_counter() - start
    logger.info("Phase 1 done: %.1fs (%d/%d reviews successful)",
                elapsed, sum(1 for r in valid_reports if not r.error), len(valid_reports))

    # Phase 2: Consensus mapping
    logger.info("Phase 2: Consensus mapping")
    report = generate_report(valid_reports)
    report.prompt_vN = prompt_text

    # Phase 3: Dispatch
    logger.info("Phase 3: Dispatch")
    dispatcher = ConsensusDispatcher()
    actions = dispatcher.dispatch(report)

    # Phase 4: Quality gates
    logger.info("Phase 4: Quality gates")
    gates = _run_gates(prompt_text)

    logger.info("Pipeline complete: %d clusters, %d actions, %d gates",
                len(report.clusters), len(actions), len(gates))

    return PipelineResult(
        report=report,
        actions=actions,
        quality_gates=gates,
        prompt_vN=prompt_text,
    )

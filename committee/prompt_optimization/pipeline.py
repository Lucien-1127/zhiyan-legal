"""
pipeline — Entry point for the full prompt review pipeline.

Usage:
    from committee.prompt_optimization import pipeline
    result = await pipeline.run_prompt_review(prompt_text, slug="v4.0")
    print(result.print_summary())

Flow:
  1. ReviewerClient calls 3 models in parallel (with retry+timeout)
  2. Normalizer parses each response → PromptClaim list
  3. Consensus clusters claims across reviewers (CONSENSUS/DISAGREEMENT/UNIQUE_INSIGHT/BLIND_SPOT)
  4. Dispatcher routes clusters → actionable DispatchAction items
  5. Quality gates (G1–G5) run on original prompt
  6. All results bundled in PipelineResult
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .prompt_quality import ReviewerModel, PromptReviewReport, PromptCommitteeReport
from .prompt_normalizer import PromptNormalizer
from .consensus import generate_report
from .dispatch import ConsensusDispatcher
from .reviewer_client import ReviewerClient
from .quality_gate import run_all as run_quality_gates, format_report

logger = logging.getLogger("pipeline")

DEFAULT_REVIEWERS = [
    ReviewerModel.DEEPSEEK,
    ReviewerModel.GEMINI,
    ReviewerModel.CLAUDE,
]


@dataclass
class PipelineResult:
    """Full pipeline output."""
    report: PromptCommitteeReport
    actions: list
    quality_gates: dict
    prompt_vN: str
    prompt_vN1: Optional[str] = None

    def print_summary(self) -> str:
        lines = [
            self.report.print_summary(),
            "",
            "📋 Dispatch Actions:",
        ]
        for a in self.actions:
            lines.append(
                f"  {a.action_type.value:16s} P{a.priority} "
                f"[{a.cluster.dimension.value}] {a.cluster.canonical_key[:40]}"
            )
        lines.append("")
        lines.append(format_report(self.quality_gates))
        return "\n".join(lines)


# ── Pipeline ───────────────────────────────────────────


async def run_prompt_review(
    prompt_text: str,
    slug: str = "prompt",
    reviewers: Optional[list[ReviewerModel]] = None,
    client: Optional[ReviewerClient] = None,
) -> PipelineResult:
    """Run the full prompt optimization pipeline.

    Parameters
    ----------
    prompt_text : str
        The writer system prompt to review.
    slug : str
        Short identifier for this prompt version.
    reviewers : list[ReviewerModel], optional
        Which reviewer models to use. Default: DeepSeek + Gemini + Agnes.
    client : ReviewerClient, optional
        Reusable API client (created fresh if omitted).

    Returns
    -------
    PipelineResult containing report, dispatch actions, and quality gates.
    """
    if reviewers is None:
        reviewers = DEFAULT_REVIEWERS

    own_client = client is None
    if client is None:
        client = ReviewerClient()

    try:
        # ── Phase 1: Parallel API calls ────────────────
        logger.info("Phase 1: Reviewing prompt with %d models", len(reviewers))
        start = time.perf_counter()

        tasks = [client.call(r, prompt_text, slug) for r in reviewers]
        reports: list[PromptReviewReport | BaseException] = await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[assignment]

        # Flatten exceptions into error reports
        valid_reports: list[PromptReviewReport] = []
        for i, result in enumerate(reports):
            if isinstance(result, BaseException):
                logger.error("Reviewer %s fatal: %s", reviewers[i].value, result)
                valid_reports.append(PromptReviewReport(
                    reviewer=reviewers[i],
                    prompt_slug=slug, claims=[],
                    summary="Fatal error", error=str(result),
                ))
            else:
                valid_reports.append(result)

        elapsed = time.perf_counter() - start
        ok = sum(1 for r in valid_reports if not r.error)
        logger.info("Phase 1 done: %.1fs (%d/%d ok)", elapsed, ok, len(valid_reports))

        # ── Phase 2: Consensus mapping ────────────────
        logger.info("Phase 2: Consensus mapping")
        report = generate_report(valid_reports)
        report.prompt_vN = prompt_text

        # ── Phase 3: Dispatch ─────────────────────────
        logger.info("Phase 3: Dispatch")
        dispatcher = ConsensusDispatcher()
        actions = dispatcher.dispatch(report)

        # ── Phase 4: Quality gates ────────────────────
        logger.info("Phase 4: Quality gates")
        gates = run_quality_gates(prompt_text)

        logger.info(
            "Pipeline complete: %d clusters, %d actions, %d gates",
            len(report.clusters), len(actions), len(gates),
        )

        return PipelineResult(
            report=report, actions=actions,
            quality_gates=gates, prompt_vN=prompt_text,
        )

    finally:
        if own_client and client:
            await client.shutdown()

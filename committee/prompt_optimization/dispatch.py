"""
dispatch — Consensus → subagent routing.

Takes the ConsensusMapper output and decides WHAT to do with each cluster:
  - CONSENSUS      → auto-fix via subagent
  - DISAGREEMENT   → present options for user to choose
  - BLIND_SPOT     → escalate for human review (highest priority)
  - UNIQUE_INSIGHT → verify then apply via subagent

Output: ordered list of DispatchAction that the pipeline executor can process.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .prompt_quality import (
    PromptClaim, ClaimCluster, PromptCommitteeReport,
    PromptDimension, Severity, ConsensusLabel,
)

logger = logging.getLogger("dispatch")


# ── Dispatch actions ────────────────────────────────────


class ActionType(Enum):
    AUTO_FIX      = "auto_fix"       # ✅ Subagent applies fix directly
    USER_CHOICE   = "user_choice"    # ⚠️  Present options, user picks
    HUMAN_REVIEW  = "human_review"   # ❌  Escalate — can't auto-resolve
    VERIFY_APPLY  = "verify_apply"   # 🔍  Validate unique insight, then fix


@dataclass
class DispatchAction:
    """What to do with a consensus cluster."""
    action_type: ActionType
    priority: int                     # 0=highest (BLIND_SPOT), 3=lowest (DISAGREEMENT)
    cluster: ClaimCluster
    claims: list[PromptClaim]
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "action": self.action_type.value,
            "priority": self.priority,
            "dimension": self.cluster.dimension.value,
            "canonical_key": self.cluster.canonical_key,
            "reasoning": self.reasoning,
            "n_claims": len(self.claims),
            "severities": [s.value for s in self.cluster.severities],
        }


# ── Dispatcher ──────────────────────────────────────────


class ConsensusDispatcher:
    """Route each cluster to the correct action handler."""

    def dispatch(
        self,
        report: PromptCommitteeReport,
    ) -> list[DispatchAction]:
        """Produce ordered actions from a committee report."""
        actions: list[DispatchAction] = []

        for cluster in report.clusters:
            # Collect all claims in this cluster
            cluster_claims = self._collect_claims(report, cluster)

            # Route by label
            if cluster.label == ConsensusLabel.CONSENSUS:
                actions.append(self._route_consensus(cluster, cluster_claims))

            elif cluster.label == ConsensusLabel.BLIND_SPOT:
                actions.append(self._route_blind_spot(cluster, cluster_claims))

            elif cluster.label == ConsensusLabel.UNIQUE_INSIGHT:
                actions.append(self._route_unique(cluster, cluster_claims))

            elif cluster.label == ConsensusLabel.DISAGREEMENT:
                actions.append(self._route_disagreement(cluster, cluster_claims))

        # Sort: BLIND_SPOT (0) > CONSENSUS (1) > VERIFY (2) > DISAGREEMENT (3)
        actions.sort(key=lambda a: a.priority)
        return actions

    # ── Routing logic ─────────────────────────────────

    def _route_consensus(
        self, cluster: ClaimCluster, claims: list[PromptClaim]
    ) -> DispatchAction:
        return DispatchAction(
            action_type=ActionType.AUTO_FIX,
            priority=1,
            cluster=cluster,
            claims=claims,
            reasoning=(
                f"✅ 所有reviewer一致認為「{cluster.canonical_key}」有問題。"
                f"共{len(claims)}條claim，最高嚴重度 "
                f"{max((s.value for s in cluster.severities), key=lambda x: {'critical':2,'major':1,'minor':0}.get(x,0))}。"
            ),
        )

    def _route_blind_spot(
        self, cluster: ClaimCluster, claims: list[PromptClaim]
    ) -> DispatchAction:
        return DispatchAction(
            action_type=ActionType.HUMAN_REVIEW,
            priority=0,
            cluster=cluster,
            claims=claims,
            reasoning=(
                f"❌ 盲區：所有模型都忽略了「{cluster.canonical_key}」"
                f"或都給出錯誤判斷。需人工判斷是否有未考慮的維度。"
            ),
        )

    def _route_unique(
        self, cluster: ClaimCluster, claims: list[PromptClaim]
    ) -> DispatchAction:
        return DispatchAction(
            action_type=ActionType.VERIFY_APPLY,
            priority=2,
            cluster=cluster,
            claims=claims,
            reasoning=(
                f"🔍 獨特發現：僅{claims[0].reviewer.value}提出"
                f"「{cluster.canonical_key}」。需驗證後套用。"
            ),
        )

    def _route_disagreement(
        self, cluster: ClaimCluster, claims: list[PromptClaim]
    ) -> DispatchAction:
        return DispatchAction(
            action_type=ActionType.USER_CHOICE,
            priority=3,
            cluster=cluster,
            claims=claims,
            reasoning=(
                f"⚠️ 分歧：reviewer對「{cluster.canonical_key}」看法不同。"
                f"需使用者決定採用哪條修復建議。"
            ),
        )

    # ── Helpers ───────────────────────────────────────

    def _collect_claims(
        self, report: PromptCommitteeReport, cluster: ClaimCluster
    ) -> list[PromptClaim]:
        """Get all PromptClaim objects belonging to this cluster.

        Matches by: dimension matches AND reviewer is in cluster's model list.
        """
        results: list[PromptClaim] = []
        for r in report.reports:
            if r.reviewer.value not in cluster.models:
                continue
            for c in r.claims:
                if c.dimension.value == cluster.dimension.value:
                    results.append(c)
        return results

    def summary_table(self, actions: list[DispatchAction]) -> str:
        """Human-readable summary of dispatch results."""
        rows = []
        for a in actions:
            emoji = {
                ActionType.AUTO_FIX: "✅",
                ActionType.HUMAN_REVIEW: "❌",
                ActionType.VERIFY_APPLY: "🔍",
                ActionType.USER_CHOICE: "⚠️",
            }.get(a.action_type, "❓")
            rows.append(
                f"{emoji} P{a.priority} [{a.cluster.dimension.value}] "
                f"{a.cluster.canonical_key} → {a.action_type.value}"
            )
        return "\n".join(rows)

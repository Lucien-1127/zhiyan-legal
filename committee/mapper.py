"""合議庭標示器 — Consensus Mapper

輸入：N 個模型對同一查詢的正規化輸出
輸出：合議庭報告 (共識/分歧/盲區/獨特發現)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from .core import (
    LegalClaim, ModelVerdict, ClaimCluster, ClaimStatus, ClaimType,
    CommitteeReport, Disagreement, ConsensusLabel, Verdict,
)
from .normalizer import normalize_response, are_semantically_equivalent


def _cluster_claims(all_claims: Dict[str, List[LegalClaim]]) -> List[ClaimCluster]:
    """將所有模型的主張進行分群。

    Parameters
    ----------
    all_claims : dict
        {model_name: [LegalClaim, ...]}

    Returns
    -------
    list[ClaimCluster]
        分群後的跨模型主張。
    """
    # 依 article_ref 初步分群
    ref_clusters: Dict[str, Dict[str, List[LegalClaim]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for model_name, claims in all_claims.items():
        for c in claims:
            ref_clusters[c.article_ref][model_name].append(c)

    clusters: List[ClaimCluster] = []
    for ref, model_claims in ref_clusters.items():
        models = list(model_claims.keys())
        statuses = []
        for clist in model_claims.values():
            for c in clist:
                if c.status:
                    statuses.append(c.status)

        # 判斷共識/分歧
        unique_statuses = list(set(statuses))
        if len(unique_statuses) <= 1:
            label = ConsensusLabel.CONSENSUS
            detail = f"所有模型一致: {unique_statuses[0].value if unique_statuses else 'unknown'}"
        else:
            label = ConsensusLabel.DISAGREEMENT
            detail = f"分歧: {' vs '.join(s.value for s in unique_statuses)}"

        clusters.append(ClaimCluster(
            canonical_ref=ref,
            claim_type=model_claims[models[0]][0].claim_type if models else ClaimType.FACT_STATEMENT,
            models=models,
            statuses=unique_statuses,
            label=label,
            detail=detail,
        ))

    return clusters


def _find_disagreements(
    clusters: List[ClaimCluster],
    all_claims: Dict[str, List[LegalClaim]],
) -> List[Disagreement]:
    """從分群中找出具體的分歧記錄。"""
    disagreements: List[Disagreement] = []
    for i, cluster in enumerate(clusters):
        if cluster.label != ConsensusLabel.DISAGREEMENT:
            continue

        # 收集每個模型的 status
        model_positions: Dict[str, str] = {}
        for model_name, claims in all_claims.items():
            for c in claims:
                if c.article_ref == cluster.canonical_ref and c.status:
                    model_positions[model_name] = c.status.value

        if len(model_positions) >= 2:
            models_list = list(model_positions.keys())
            for j in range(len(models_list)):
                for k in range(j + 1, len(models_list)):
                    ma, mb = models_list[j], models_list[k]
                    if model_positions[ma] != model_positions[mb]:
                        disagreements.append(Disagreement(
                            cluster_id=f"dis_{i}_{j}_{k}",
                            canonical_ref=cluster.canonical_ref,
                            description=f"{ma} 說「{model_positions[ma]}」, {mb} 說「{model_positions[mb]}」",
                            model_a=ma,
                            position_a=model_positions[ma],
                            model_b=mb,
                            position_b=model_positions[mb],
                        ))
    return disagreements


def _estimate_blind_spots(
    model_verdicts: List[ModelVerdict],
    clusters: List[ClaimCluster],
) -> int:
    """估算集體盲區：所有模型都 FAIL 但方向不同。"""
    all_fail = sum(1 for v in model_verdicts if v.verdict == Verdict.FAIL)
    if all_fail < 2:
        return 0
    # 如果超過一個模型 fail，檢查它們是否在同一個條號上失敗
    fail_refs: Dict[str, int] = defaultdict(int)
    for v in model_verdicts:
        if v.verdict == Verdict.FAIL:
            for c in v.claims:
                if c.status in (ClaimStatus.NONEXISTENT, ClaimStatus.DELETED):
                    fail_refs[c.article_ref] += 1
    # 如果同一個條號被多個模型都判定錯誤 → 盲區
    blind = sum(1 for ref, count in fail_refs.items() if count >= 2)
    return blind


def generate_report(
    model_verdicts: List[ModelVerdict],
) -> CommitteeReport:
    """對單一查詢產生合議庭報告。

    Parameters
    ----------
    model_verdicts : list[ModelVerdict]
        所有模型對同一個查詢的判定結果。

    Returns
    -------
    CommitteeReport

    Notes
    -----
    - ERROR 狀態的模型（API 失敗）會被排除在共識計算外
    - SAFETY_UNKNOWN 狀態僅記錄，不參與分歧計數
    """
    if not model_verdicts:
        raise ValueError("至少需要一個模型的判定結果")

    query_id = model_verdicts[0].query_id
    query_text = model_verdicts[0].query_text
    category = model_verdicts[0].category

    # 1. 正規化每個模型的輸出（排除 ERROR）
    all_claims: Dict[str, List[LegalClaim]] = {}
    active_models = 0
    for v in model_verdicts:
        claims = normalize_response(v.raw_response, v.model_name)
        all_claims[v.model_name] = claims

        # 檢查是否為 ERROR
        is_error = any(c.status == ClaimStatus.ERROR for c in claims)
        if not is_error:
            active_models += 1

    # 2. 分群（只包含非 ERROR 的主張）
    clusters = _cluster_claims(all_claims)

    # 3. 找分歧（排除 ERROR 模型的參與）
    disagreements = _find_disagreements(clusters, all_claims)

    # 4. 統計（只計 active models）
    n_disagreements = len(disagreements)
    n_consensus = sum(1 for c in clusters if c.label == ConsensusLabel.CONSENSUS)
    n_blind = _estimate_blind_spots(model_verdicts, clusters)
    n_unique = sum(1 for c in clusters if c.label == ConsensusLabel.UNIQUE_INSIGHT)

    return CommitteeReport(
        query_id=query_id,
        query_text=query_text,
        category=category,
        model_verdicts=model_verdicts,
        clusters=clusters,
        disagreements=disagreements,
        total_models=active_models,
        consensus_count=n_consensus,
        disagreement_count=n_disagreements,
        blind_spot_count=n_blind,
        unique_insight_count=n_unique,
    )

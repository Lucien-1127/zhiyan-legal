"""Test committee core data structures and mapper logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from committee.core import (
    LegalClaim, ClaimCluster, CommitteeReport, Disagreement,
    ClaimType, ClaimStatus, ConsensusLabel, Verdict, ModelVerdict,
)
from committee.normalizer import (
    normalize_citation, normalize_response, _match_status,
    are_semantically_equivalent,
)
from committee.mapper import generate_report, _cluster_claims


def test_normalize_citation():
    """測試條號正規化"""
    assert "民法第987條" in normalize_citation("§987"), "§987 failed"
    assert "釋字第812號" in normalize_citation("釋字812號"), "釋字 failed"
    assert "民法第1條" in normalize_citation("第1條"), "第X條 failed"
    print("✅ test_normalize_citation")


def test_match_status():
    """測試用語正規化"""
    assert _match_status("§987 已刪除") == ClaimStatus.DELETED
    assert _match_status("查無此條號 §9999") == ClaimStatus.NONEXISTENT
    assert _match_status("該條文已於2007年刪除") == ClaimStatus.DELETED
    assert _match_status("§1 規定...") is None  # normal
    assert _match_status("") == ClaimStatus.ERROR  # empty
    assert _match_status("API 呼叫失敗：429 Too Many Requests") == ClaimStatus.ERROR  # API error
    assert _match_status("抱歉，我無法回答這個問題") == ClaimStatus.SAFETY_UNKNOWN  # safety
    print("✅ test_match_status")


def test_semantic_equivalence():
    """測試語意等價"""
    assert are_semantically_equivalent("§987 已刪除", "第987條已廢止")
    assert are_semantically_equivalent("§9999 不存在", "第9999條不存在")
    assert not are_semantically_equivalent("§987 仍在施行", "§987 已於2007年刪除")
    print("✅ test_semantic_equivalence")


def test_generate_report():
    """測試合議庭報告"""
    v1 = ModelVerdict(
        model_name="model-a", query_id="Q001", query_text="test",
        category="test", verdict=Verdict.FAIL,
        raw_response="§987 已刪除，§9999 不存在",
    )
    v2 = ModelVerdict(
        model_name="model-b", query_id="Q001", query_text="test",
        category="test", verdict=Verdict.FAIL,
        raw_response="第987條已廢止，第9999條查無",
    )
    v3 = ModelVerdict(
        model_name="model-c", query_id="Q001", query_text="test",
        category="test", verdict=Verdict.PASS,
        raw_response="§987 已刪除",
    )

    report = generate_report([v1, v2, v3])
    assert report.query_id == "Q001"
    assert report.total_models == 3
    print(f"  Disagreements: {report.disagreement_count}")
    print(f"  Consensus: {report.consensus_count}")
    print("✅ test_generate_report")


if __name__ == "__main__":
    test_normalize_citation()
    test_match_status()
    test_semantic_equivalence()
    test_generate_report()
    print("\n🎉 All tests passed!")

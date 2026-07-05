"""治理契約實作 — 將 GOVERNANCE.md + INVARIANTS.md 的規則編碼為可執行檢查。
從 committee_core/policies/governance_contract.py 搬入（v3.9.5）

覆蓋準則：
  I001 — 高風險訊息強制指引
  I002 — 引用必須可驗證
  I003 — Capability Registry 唯讀（禁止執行時動態新增能力）
  I004 — 選擇輸出方式前必須完成干預分析
  I005 — PII 不得直接輸出
  I006 — 法律結論必須附引用（防幻覺）
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_HIGH_RISK_DOMAINS = frozenset([
    "憲法", "刑事", "家事", "殺人", "強盜",
    "詐欺", "洗錢", "性自殺", "家暴",
])

_CITATION_PATTERN = re.compile(
    r"\[T1\]|\[\d+\]|待查|推論"
)

_PII_PATTERN = re.compile(
    r"(?:"
    r"\d{7,10}"
    r"|[A-Z]\d{9}"
    r"|\d{2,4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|[\w.+-]+@[\w-]+\.[\w.]+"
    r"|0\d{1,2}[-\s]\d{6,8}"
    r")"
)


@dataclass
class PolicyViolation:
    invariant: str
    detail: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"


class GovernanceContract:
    """核心治理契約，定義所有模型必須遵守的邏輯約束。

    使用方式：
        contract = GovernanceContract()
        violations = contract.enforce(claim="...", policy_id="I001")
        if violations:
            raise GovernanceViolationError(violations)
    """

    def enforce(self, claim: Any, policy_id: str) -> list[PolicyViolation]:
        handler = {
            "I001": self._enforce_i001_high_risk,
            "I002": self._enforce_i002_citation,
            "I003": self._enforce_i003_capability_registry,
            "I004": self._enforce_i004_intervention_analysis,
            "I005": self._enforce_i005_pii,
            "I006": self._enforce_i006_anti_hallucination,
        }.get(policy_id)
        if handler is None:
            return [PolicyViolation(invariant=policy_id, detail=f"未知 policy_id: {policy_id}", severity="MEDIUM")]
        return handler(str(claim))

    def enforce_all(self, claim: Any) -> list[PolicyViolation]:
        violations: list[PolicyViolation] = []
        for pid in ("I001", "I002", "I003", "I004", "I005", "I006"):
            violations.extend(self.enforce(claim, pid))
        return violations

    def _enforce_i001_high_risk(self, text: str) -> list[PolicyViolation]:
        triggered = [kw for kw in _HIGH_RISK_DOMAINS if kw in text]
        if not triggered:
            return []
        guidance_markers = ("請諞詢專業律師", "免責聲明", "專業建議", "1925", "113")
        if not any(m in text for m in guidance_markers):
            return [PolicyViolation(
                invariant="I001",
                detail=f"高風險關鍵詞 {triggered} 已觸發，但輸出缺少強制指引提示",
                severity="CRITICAL",
            )]
        return []

    def _enforce_i002_citation(self, text: str) -> list[PolicyViolation]:
        legal_markers = ("依具", "根據", "第", "條", "規定", "判決", "法院")
        if not any(m in text for m in legal_markers):
            return []
        if _CITATION_PATTERN.search(text):
            return []
        return [PolicyViolation(
            invariant="I002",
            detail="包含法律主張但缺少引用標記 [T1]/[1]/[2]/[3] 或「待查」/「推論」",
            severity="HIGH",
        )]

    def _enforce_i003_capability_registry(self, text: str) -> list[PolicyViolation]:
        forbidden = [re.compile(p, re.IGNORECASE) for p in [
            r"add_capability", r"register_skill", r"install_plugin",
            r"\bnew\s+capability\b", r"enable_module",
        ]]
        triggered = [p.pattern for p in forbidden if p.search(text)]
        if triggered:
            return [PolicyViolation(
                invariant="I003",
                detail=f"偵測到動態新增能力指令: {triggered}",
                severity="CRITICAL",
            )]
        return []

    def _enforce_i004_intervention_analysis(self, text: str) -> list[PolicyViolation]:
        choice_markers = ("建議選擇", "建議誱詟", "最佳方案", "應該選", "應該採用")
        if not any(m in text for m in choice_markers):
            return []
        analysis_markers = ("因為", "理由", "分析", "接著", "第一", "首先", "然而")
        if any(m in text for m in analysis_markers):
            return []
        return [PolicyViolation(
            invariant="I004",
            detail="包含輸出選擇建議但缺少干預分析依據",
            severity="MEDIUM",
        )]

    def _enforce_i005_pii(self, text: str) -> list[PolicyViolation]:
        matches = _PII_PATTERN.findall(text)
        if matches:
            redacted = [m[:3] + "***" for m in matches]
            return [PolicyViolation(
                invariant="I005",
                detail=f"偵測到可能的 PII 資料: {redacted}，請脅敏處理",
                severity="HIGH",
            )]
        return []

    def _enforce_i006_anti_hallucination(self, text: str) -> list[PolicyViolation]:
        conclusion_markers = ("因此", "結論", "於法律上", "權利", "義務", "構成要件", "歸責")
        if not any(m in text for m in conclusion_markers):
            return []
        if _CITATION_PATTERN.search(text):
            return []
        return [PolicyViolation(
            invariant="I006",
            detail="包含法律結論但缺少引用，可能為幻覺性主張",
            severity="HIGH",
        )]


class GovernanceViolationError(Exception):
    """治理契約違規時拋出。"""
    def __init__(self, violations: list[PolicyViolation]):
        self.violations = violations
        details = "; ".join(f"{v.invariant}({v.severity}): {v.detail}" for v in violations)
        super().__init__(f"[GovernanceViolation] {details}")

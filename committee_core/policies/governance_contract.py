"""治理契約實作 — 將 GOVERNANCE.md + INVARIANTS.md 的規則編碼為可執行檢查。

覆蓋準則：
  I001 — 高風險訊息強制指引
  I002 — 引用必須可驗證
  I003 — Capability Registry 唯讀（禁止執行時動態新增能力）
  I004 — 選擇輸出方式前必須完成干預分析
  I005 — PII 不得直接輸出（隱私守護）
  I006 — 法律結論必須附引用（防幻覺）
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ───────────────────────────────────────────────────────────────────
# 常數定義
# ───────────────────────────────────────────────────────────────────

# I001: 高風險法域關鍵詞（觸發強制指引的場景）
_HIGH_RISK_DOMAINS = frozenset([
    "憲法", "刑事", "家事", "殺人", "強盜",
    "誐詐", "洗錢", "每櫌", "自殺", "家暴",
])

# I002: 引用標記殣測 pattern
_CITATION_PATTERN = re.compile(
    r"\[T1\]|\[\d+\]|\u5f85查|\u63a8論"
)

# I005: PII 殣測 pattern
_PII_PATTERN = re.compile(
    r"(?:"
    r"\d{7,10}"           # 身分證號碼
    r"|[A-Z]\d{9}"        # 臺灣身分證
    r"|\d{2,4}[-/]\d{1,2}[-/]\d{1,2}"  # 生日期
    r"|[\w.+-]+@[\w-]+\.[\w.]+"  # Email
    r"|0\d{1,2}[-\s]\d{6,8}"   # 電話
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
        """\u57f7\u884c\u6307\u5b9a invariant \u7684\u6aa2\u67e5\u3002

        Parameters
        ----------
        claim : Any
            \u8981\u6aa2\u67e5\u7684\u5167\u5bb9\uff08\u5b57\u4e32\u6216 dict\uff09\u3002
        policy_id : str
            Invariant \u7de8\u865f\uff0c\u5982 'I001'\u3001'I002'\u3001...

        Returns
        -------
        list[PolicyViolation]
            \u9055\u898f\u6e05\u55ae\uff08\u7a7a\u8868\u793a\u901a\u904e\uff09\u3002
        """
        handler = {
            "I001": self._enforce_i001_high_risk,
            "I002": self._enforce_i002_citation,
            "I003": self._enforce_i003_capability_registry,
            "I004": self._enforce_i004_intervention_analysis,
            "I005": self._enforce_i005_pii,
            "I006": self._enforce_i006_anti_hallucination,
        }.get(policy_id)

        if handler is None:
            return [PolicyViolation(
                invariant=policy_id,
                detail=f"\u672a\u77e5 policy_id: {policy_id}",
                severity="MEDIUM",
            )]
        return handler(str(claim))

    def enforce_all(self, claim: Any) -> list[PolicyViolation]:
        """\u57f7\u884c\u6240\u6709 I001\u2013I006 \u6aa2\u67e5\u3002"""
        violations: list[PolicyViolation] = []
        for pid in ("I001", "I002", "I003", "I004", "I005", "I006"):
            violations.extend(self.enforce(claim, pid))
        return violations

    # ───────────────────────────────────────────────────────────────
    # 內部各 Invariant 檢查函數
    # ───────────────────────────────────────────────────────────────

    def _enforce_i001_high_risk(self, text: str) -> list[PolicyViolation]:
        """I001: \u9ad8\u98a8\u96aa\u8a0a\u606f\u5fc5\u9808\u5305\u542b\u5f37\u5236\u6307\u5f15\u63d0\u793a\u3002"""
        triggered = [kw for kw in _HIGH_RISK_DOMAINS if kw in text]
        if not triggered:
            return []
        # 檢查是否包含指引提示（高風險輸出必須帶免責聃明或專業建議）
        guidance_markers = ("\u8acb\u8ade\u8a62\u5c08\u696d\u5f8b\u5e2b", "\u514d\u8cac\u8043\u660e", "\u5c08\u696d\u5efa\u8b70", "\u9999\u6e2f\u6cd5\u5f8b\u63f4\u52a9", "1925", "113")
        if not any(m in text for m in guidance_markers):
            return [PolicyViolation(
                invariant="I001",
                detail=(
                    f"\u9ad8\u98a8\u96aa\u95dc\u9375\u8a5e {triggered} \u5df2\u89f8\u767c\uff0c"
                    "\u4f46\u8f38\u51fa\u7f3a\u5c11\u5f37\u5236\u6307\u5f15\u63d0\u793a"
                    "\uff08\u8acb\u8ade\u8a62\u5c08\u696d\u5f8b\u5e2b / \u514d\u8cac\u8043\u660e / \u7dca\u6025\u8cc7\u6e90\uff09"
                ),
                severity="CRITICAL",
            )]
        return []

    def _enforce_i002_citation(self, text: str) -> list[PolicyViolation]:
        """I002: \u6cd5\u5f8b\u4e3b\u5f35\u5fc5\u9808\u5305\u542b\u53ef\u9a57\u8b49\u5f15\u7528\u6a19\u8a18\u3002"""
        legal_claim_markers = ("\u4f9d\u5177", "\u6839\u64da", "\u7b2c", "\u689d", "\u898f\u5b9a", "\u5224\u6c7a", "\u6cd5\u9662")
        has_legal_claim = any(m in text for m in legal_claim_markers)
        if not has_legal_claim:
            return []  # \u975e\u6cd5\u5f8b\u4e3b\u5f35\uff0c\u4e0d\u9700\u8981引\u7528
        if _CITATION_PATTERN.search(text):
            return []  # \u5df2\u6709\u5f15\u7528
        return [PolicyViolation(
            invariant="I002",
            detail="\u5305\u542b\u6cd5\u5f8b\u4e3b\u5f35\u4f46\u7f3a\u5c11\u5f15\u7528\u6a19\u8a18 [T1]/[1]/[2]/[3] \u6216\u300c\u5f85\u67e5\u300d/\u300c\u63a8\u8ad6\u300d",
            severity="HIGH",
        )]

    def _enforce_i003_capability_registry(self, text: str) -> list[PolicyViolation]:
        """I003: Capability Registry \u552f\u8b80\u2014\u7981\u6b62\u8f38\u51fa\u5167\u5bb9\u5305\u542b\u52d5\u614b\u65b0\u589e\u80fd\u529b\u7684\u6307\u4ee4\u3002"""
        forbidden_patterns = [
            re.compile(p, re.IGNORECASE) for p in [
                r"add_capability", r"register_skill", r"install_plugin",
                r"\bnew\s+capability\b", r"enable_module",
            ]
        ]
        triggered = [p.pattern for p in forbidden_patterns if p.search(text)]
        if triggered:
            return [PolicyViolation(
                invariant="I003",
                detail=f"\u5075\u6e2c\u5230\u52d5\u614b\u65b0\u589e\u80fd\u529b\u6307\u4ee4: {triggered}",
                severity="CRITICAL",
            )]
        return []

    def _enforce_i004_intervention_analysis(self, text: str) -> list[PolicyViolation]:
        """I004: \u9078\u64c7\u8f38\u51fa\u65b9\u5f0f\u524d\u5fc5\u9808\u5b8c\u6210\u5e72\u9810\u5206\u6790\u3002

        \u7b80\u5316\u5224\u65b7\uff1a\u5982\u679c\u8f38\u51fa\u5305\u542b\u9078\u64c7\u5efa\u8b70\u624d\u691c\u67e5\u662f\u5426\u6709\u5206\u6790\u4f9d\u64da\u3002
        """
        choice_markers = ("\u5efa\u8b70\u9078\u64c7", "\u5efa\u8b70\u8ab1\u8a5f", "\u6700\u4f73\u65b9\u6848", "\u61c9\u8a72\u9078", "\u61c9\u8a72\u63a1\u7528")
        has_choice = any(m in text for m in choice_markers)
        if not has_choice:
            return []
        analysis_markers = ("\u56e0\u70ba", "\u7406\u7531", "\u5206\u6790", "\u63a5\u7740", "\u7b2c\u4e00", "\u9996\u5148", "\u7136\u800c")
        if any(m in text for m in analysis_markers):
            return []
        return [PolicyViolation(
            invariant="I004",
            detail="\u5305\u542b\u8f38\u51fa\u9078\u64c7\u5efa\u8b70\u4f46\u7f3a\u5c11\u5e72\u9810\u5206\u6790\u4f9d\u64da",
            severity="MEDIUM",
        )]

    def _enforce_i005_pii(self, text: str) -> list[PolicyViolation]:
        """I005: \u500b\u4eba\u8b58\u5225\u8cc7\u8a0a\uff08PII\uff09\u4e0d\u5f97\u76f4\u63a5\u8f38\u51fa\u3002"""
        matches = _PII_PATTERN.findall(text)
        if matches:
            redacted = [m[:3] + "***" for m in matches]
            return [PolicyViolation(
                invariant="I005",
                detail=f"\u5075\u6e2c\u5230\u53ef\u80fd\u7684 PII \u8cc7\u6599: {redacted}\uff0c\u8acb\u8105\u654f\u8655\u7406",
                severity="HIGH",
            )]
        return []

    def _enforce_i006_anti_hallucination(self, text: str) -> list[PolicyViolation]:
        """I006: \u6cd5\u5f8b\u7d50\u8ad6\u5fc5\u9808\u9644\u5f15\u7528\uff0c\u7981\u6b62\u865f\u7a31\u51fa\u81ea\u5c0d\u61c9\u77e5\u8b58\u5eab\u7684\u7d50\u8ad6\u3002"""
        conclusion_markers = ("\u56e0\u6b64", "\u7d50\u8ad6", "\u65bc\u6cd5\u5f8b\u4e0a", "\u6b0a\u5229", "\u7fa9\u52d9", "\u69cb\u6210\u8981\u4ef6", "\u6b78\u8cac")
        has_conclusion = any(m in text for m in conclusion_markers)
        if not has_conclusion:
            return []
        if _CITATION_PATTERN.search(text):
            return []
        return [PolicyViolation(
            invariant="I006",
            detail="\u5305\u542b\u6cd5\u5f8b\u7d50\u8ad6\u4f46\u7f3a\u5c11\u5f15\u7528\uff0c\u53ef\u80fd\u70ba\u5e7b\u89ba\u6027\u4e3b\u5f35",
            severity="HIGH",
        )]


class GovernanceViolationError(Exception):
    """\u6cbb\u7406\u5951\u7d04\u9055\u898f\u6642\u62cb\u51fa\u3002"""
    def __init__(self, violations: list[PolicyViolation]):
        self.violations = violations
        details = "; ".join(f"{v.invariant}({v.severity}): {v.detail}" for v in violations)
        super().__init__(f"[GovernanceViolation] {details}")

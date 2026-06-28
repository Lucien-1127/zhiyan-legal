"""
quality_gate — G1–G5 validation layer (v4.0 spec).

Each gate is a pure function that returns (pass: bool, detail: str).
The `run_all()` function runs all gates and returns a dict.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger("quality_gate")


# ── Gate results ────────────────────────────────────────


@dataclass
class GateResult:
    """Single gate result."""
    name: str
    passed: bool
    detail: str = ""

    def __bool__(self) -> bool:
        return self.passed

    def emoji(self) -> str:
        return "✅" if self.passed else "⚠️"

    def __str__(self) -> str:
        return f"{self.emoji()} {self.name}: {self.detail}"


# ── Gate functions ──────────────────────────────────────
# Each takes the prompt text as input, returns (bool, str).


def g1_structure(prompt: str) -> GateResult:
    """G1: Required sections present (ROLE, TASK, OUTPUT, CONSTRAINTS)."""
    required = ["role", "task", "output", "constraint"]
    prompt_lower = prompt.lower()
    found = [s for s in required if s in prompt_lower]
    missing = [s for s in required if s not in prompt_lower]

    if not missing:
        return GateResult("G1 結構完整性", True, f"所有必要區塊齊全 ({', '.join(found)})")
    else:
        return GateResult(
            "G1 結構完整性", False,
            f"缺少區塊: {', '.join(missing)}. 已存在: {', '.join(found) if found else '無'}",
        )


def g2_minimum_density(prompt: str) -> GateResult:
    """G2: Minimum word count for a useful prompt."""
    words = len(prompt.split())
    threshold = 50  # Minimum viable prompt ~50 words
    if words >= threshold:
        return GateResult("G2 最低密度", True, f"{words} 字詞 (門檻: {threshold})")
    else:
        return GateResult(
            "G2 最低密度", False,
            f"僅 {words} 字詞，建議至少 {threshold} 字詞才能有效約束模型行為",
        )


def g3_ai_taste(prompt: str) -> GateResult:
    """G3: Check for common AI-taste indicators (mechanical sequences, overused patterns)."""
    # Patterns that signal AI-generated prompt writing
    ai_patterns = [
        (r"\b首先\b.*\b其次\b", "機械序列詞「首先…其次」"),
        (r"\b總而言之\b", "機械總結「總而言之」"),
        (r"\b值得注意的是\b", "模板句「值得注意的是」"),
        (r"\b讓我們來\b", "引導句「讓我們來」"),
        (r"\b在這篇文章中，我們將\b", "過度正式開場"),
        (r"\b最後，\b.*\b總之\b", "機械收尾序列"),
    ]

    hits = []
    for pattern, desc in ai_patterns:
        if re.search(pattern, prompt):
            hits.append(desc)

    # Count per 1000 words
    words = len(prompt.split()) or 1
    rate = len(hits) / (words / 1000)

    if rate <= 1.0:
        return GateResult(
            "G3 AI味偵測", True,
            f"每千字 {rate:.1f} 次機械模式 (門檻: ≤1.0)",
        )
    else:
        return GateResult(
            "G3 AI味偵測", False,
            f"每千字 {rate:.1f} 次機械模式，命中: {'; '.join(hits)}",
        )


def g4_has_examples(prompt: str) -> GateResult:
    """G4: Contains at least one example or placeholder."""
    has_example = "例如" in prompt or "example" in prompt.lower()
    has_placeholder = "{{" in prompt or "{" in prompt
    has_code_block = "```" in prompt

    details = []
    if has_example:
        details.append("含「例如」")
    if has_placeholder:
        details.append("含變數佔位符")
    if has_code_block:
        details.append("含程式碼區塊")

    passed = has_example or has_placeholder or has_code_block
    return GateResult(
        "G4 包含示例", passed,
        "、".join(details) if details else "無示例、佔位符或程式碼區塊",
    )


def g5_placeholder_balance(prompt: str) -> GateResult:
    """G5: Check variable placeholder balance (opening == closing count)."""
    # Count {{ }} pairs and { } pairs
    double_open = prompt.count("{{")
    double_close = prompt.count("}}")
    single_open = prompt.count("{") - double_open * 2
    single_close = prompt.count("}") - double_close * 2

    issues = []
    if double_open != double_close:
        issues.append(f"{{{{...}}}} 不平衡 ({double_open} open vs {double_close} close)")
    if single_open != single_close:
        issues.append(f"{{...}} 不平衡 ({single_open} open vs {single_close} close)")

    if not issues:
        return GateResult("G5 佔位符平衡", True, f"所有 {double_open + single_open} 個佔位符均平衡")
    else:
        return GateResult("G5 佔位符平衡", False, "; ".join(issues))


# ── Registry ────────────────────────────────────────────

GATES: dict[str, callable] = {  # type: ignore[type-arg]
    "G1": g1_structure,
    "G2": g2_minimum_density,
    "G3": g3_ai_taste,
    "G4": g4_has_examples,
    "G5": g5_placeholder_balance,
}


# ── Runner ──────────────────────────────────────────────


def run_all(prompt: str) -> dict[str, GateResult]:
    """Run all 5 gates and return results dict."""
    results: dict[str, GateResult] = {}
    for name, gate_fn in GATES.items():
        try:
            results[name] = gate_fn(prompt)
        except Exception as e:
            logger.warning("Gate %s crashed: %s", name, e)
            results[name] = GateResult(name, False, f"執行錯誤: {e}")
    return results


def format_report(results: dict[str, GateResult]) -> str:
    """Format quality gates as a human-readable string."""
    lines = ["## 品質閘門報告"]
    all_passed = all(r.passed for r in results.values())
    for name in ["G1", "G2", "G3", "G4", "G5"]:
        if name in results:
            lines.append(f"  {results[name]}")
    lines.append(f"  → {'✅ 全部通過' if all_passed else '⚠️ 部分閘門未通過'}")
    return "\n".join(lines)

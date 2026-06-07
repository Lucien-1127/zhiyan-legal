"""
Document load order and task routing map.

Mirrors the architecture defined in docs/ so the runtime knows
which files to compose per task type.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DOCS_DIR = os.path.join(ROOT, "docs")
# Fallback: user's project root can be overridden via env var
DOCS_DIR_ALT = os.environ.get("ZHIYAN_DOCS_DIR", "")


@dataclass
class Layer:
    """A document layer in the architecture."""

    name: str
    path: str
    files: List[str] = field(default_factory=list)
    always_load: bool = True


# ── Core layers (always loaded in fixed order) ──────────────────────
CORE_LAYERS = [
    Layer("System Prompt",         "10_核心控制層", ["09_AGENT_SYSTEM_PROMPT_v1.0.0.md"]),
    Layer("Master Persona",        "10_核心控制層", ["10_主人格_MASTER_v2.0.0.md"]),
    Layer("Space Core",            "10_核心控制層", ["13_空間核心規格_PPL_SPACE_CORE_v3.0.0.md"]),
    Layer("Boot Process",          "10_核心控制層", ["11_啟動流程_BOOT_v2.40.0.md"]),
    Layer("Core Gate",             "10_核心控制層", ["12_核心閘門_CORE_GATE_v1.1.0.md"]),
    Layer("Runbook",               "10_核心控制層", ["14_智研AI代理運行流程_RUNBOOK_v1.0.0.md"]),
    Layer("Task Router",           "10_核心控制層", ["15_任務路由表_TASK_ROUTER_v1.0.0.md"]),
    Layer("Citation Policy",       "20_模式與引用層", ["30_引用政策_CITATION_POLICY_v2.0.0.md"]),
]

# ── Task layers (loaded based on routed task) ───────────────────────
TASK_LAYERS: Dict[str, List[Layer]] = {
    "QC": [
        Layer("QC Mode",           "20_模式與引用層", ["22_模式_QC_查核_v2.0.1.md"]),
    ],
    "RESEARCH": [
        Layer("Research Mode",     "20_模式與引用層", ["21_模式_RESEARCH_研究_v2.0.0.md"]),
    ],
    "REPORT": [
        Layer("Report Mode",       "20_模式與引用層", ["20_模式_REPORT_報告_v2.0.0.md"]),
    ],
    "CONSULTANT": [
        Layer("Consultant Persona", "40_模組與人格層", ["50_人格_顧問_v1.1.0.md"]),
    ],
    "TA": [
        Layer("TA Persona",        "40_模組與人格層", ["51_人格_助教批改_v1.1.0.md"]),
    ],
    "TUTOR": [
        Layer("Tutor Persona",     "40_模組與人格層", ["52_人格_教學_v1.1.0.md"]),
    ],
    "LEGAL_WRITER": [
        Layer("Legal Writer",      "40_模組與人格層", ["40_模組_訴訟策略_v2.2.0.md"]),
    ],
    "LITIGATION": [
        Layer("Litigation Module", "40_模組與人格層", ["40_模組_訴訟策略_v2.2.0.md"]),
    ],
    "SAFETY": [
        Layer("Safety Module",     "40_模組與人格層", ["41_模組_安全風險對話處理_v1.0.0.md"]),
    ],
}

# ── Exclusion rules (files NEVER loaded into the live prompt) ───────
EXCLUDED_DIRS = {"80_封存參考", "90_維運治理"}
EXCLUDED_FILES = {
    "目錄索引_INDEX.md",
    "60_概念詞條_INDEX_v1.0.0.md",
}


def resolve_doc(subdir: str, filename: str) -> str:
    """Return the full path to a doc file, checking multiple locations."""
    # Primary: docs/ directory
    path = os.path.join(DOCS_DIR, subdir, filename)
    if os.path.exists(path):
        return path

    # Fallback: user-specified docs dir
    if DOCS_DIR_ALT:
        path = os.path.join(DOCS_DIR_ALT, subdir, filename)
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"Cannot find {filename} in docs/{subdir}/ — "
        "make sure docs/ is present or set ZHIYAN_DOCS_DIR env var."
    )


def get_load_order(task: str = "QC") -> List[str]:
    """
    Return the ordered list of file paths to compose into the system prompt.

    Parameters
    ----------
    task : str
        The routed task label (QC, RESEARCH, REPORT, CONSULTANT, etc.)
    """
    paths = []
    seen = set()

    # 1. Core layers (always)
    for layer in CORE_LAYERS:
        for fname in layer.files:
            fp = resolve_doc(layer.path, fname)
            if fp not in seen:
                paths.append(fp)
                seen.add(fp)

    # 2. Task layers (if applicable)
    if task in TASK_LAYERS:
        for layer in TASK_LAYERS[task]:
            for fname in layer.files:
                fp = resolve_doc(layer.path, fname)
                if fp not in seen:
                    paths.append(fp)
                    seen.add(fp)

    return paths

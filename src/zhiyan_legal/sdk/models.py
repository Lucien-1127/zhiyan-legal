"""
zhiyan_legal.sdk.models — SDK 資料模型
用 dataclass 定義所有公開 API 的請求/回應結構。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal


TaskLabel = Literal[
    "QC", "RESEARCH", "REPORT", "CONSULTANT",
    "TA", "TUTOR", "LEGAL_WRITER", "LITIGATION",
    "SAFETY", "SIMULATION",
]

ProviderName = Literal["zhiyan", "agnes", "gemini", "openai", "openrouter"]


@dataclass
class ProviderInfo:
    """API 提供商平台資訊。"""
    name: ProviderName
    base_url: str
    model: str
    is_primary: bool = False


@dataclass
class QueryRequest:
    """单次查詢請求結構。"""
    message: str
    task: Optional[TaskLabel] = None          # None 表示自動路由
    model: Optional[str] = None               # None 表示使用預設
    temperature: float = 0.3
    max_tokens: int = 4096
    dry_run: bool = False


@dataclass
class QueryResponse:
    """單一模型查詢回應。"""
    content: str
    task: TaskLabel
    model: str
    provider: ProviderName
    tokens_used: int = 0
    latency_ms: float = 0.0
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_dry_run: bool = False


@dataclass
class CommitteeVote:
    """.各席投票結果。"""
    provider: ProviderName
    model: str
    content: str
    citations: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class CommitteeResponse:
    """合議庭投票結果。"""
    task: TaskLabel
    verdict: Literal["consensus", "dissensus", "blind_spot"]
    votes: list[CommitteeVote] = field(default_factory=list)
    merged_content: str = ""
    disagreements: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

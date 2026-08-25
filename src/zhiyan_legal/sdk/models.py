"""
zhiyan_legal.sdk.models — SDK 資料模型
用 dataclass 定義所有公開 API 的請求/回應結構。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Optional, Literal

if TYPE_CHECKING:
    from ..domain import AnswerMeta, ExecutionContext


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
    decision: str = "DELIVER"
    execution_id: str = ""
    answer_meta: dict = field(default_factory=dict)

    @classmethod
    def from_domain(
        cls,
        context: "ExecutionContext",
        answer_meta: "AnswerMeta",
        *,
        content: str = "",
        model: str = "canonical-domain",
        provider: ProviderName = "zhiyan",
        tokens_used: int = 0,
        latency_ms: float = 0.0,
        citations: list[str] | None = None,
        warnings: list[str] | None = None,
        is_dry_run: bool = False,
        decision: str | None = None,
    ) -> "QueryResponse":
        """Adapt canonical execution and answer metadata to the SDK response.

        Content and transport metrics belong to the SDK boundary, so callers
        may provide them while decision, task, citations, and warnings are
        derived from the canonical domain objects.
        """
        task_value = getattr(answer_meta.task_mode, "value", answer_meta.task_mode)
        task_map = {
            "CONTRACT_REVIEW": "QC",
            "LEGAL_DRAFT": "LEGAL_WRITER",
            "COURTROOM": "SIMULATION",
        }
        task = task_map.get(str(task_value), str(task_value))

        response_citations = (
            list(citations)
            if citations is not None
            else [citation.locator for citation in context.citations]
        )
        response_warnings = list(warnings or [])
        response_warnings.extend(answer_meta.conflicts)
        response_warnings.extend(answer_meta.tool_failures)
        if answer_meta.human_review_required:
            response_warnings.append("human review required")

        return cls(
            content=content,
            task=task,  # type: ignore[arg-type]
            model=model,
            provider=provider,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            citations=response_citations,
            warnings=response_warnings,
            is_dry_run=is_dry_run,
            decision=decision or answer_meta.decision.value,
            execution_id=context.execution_id,
            answer_meta=answer_meta.model_dump(mode="json"),
        )

    @classmethod
    def from_execution_context(
        cls,
        context: "ExecutionContext",
        answer_meta: "AnswerMeta",
        **kwargs,
    ) -> "QueryResponse":
        """Named compatibility alias for the domain-to-SDK adapter."""
        return cls.from_domain(context, answer_meta, **kwargs)


def query_response_from_domain(
    context: "ExecutionContext",
    answer_meta: "AnswerMeta",
    **kwargs,
) -> QueryResponse:
    """Functional form of :meth:`QueryResponse.from_domain`."""
    return QueryResponse.from_domain(context, answer_meta, **kwargs)


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
    status: str = "CONSENSUS"
    recommended_decision: str = "DELIVER"
    recommended_strictness: int = 0
    report: dict[str, Any] = field(default_factory=dict)

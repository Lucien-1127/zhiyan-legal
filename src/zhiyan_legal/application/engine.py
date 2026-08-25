"""The single application orchestration boundary.

This module deliberately owns orchestration only.  Domain models remain the
source of truth, gates make the delivery decision, and the provider registry
is the only boundary through which a model can be called.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import uuid4

from ..domain import (
    AnswerMeta,
    DeliveryDecision,
    ExecutionContext,
    ExecutionStatus,
    TaskMode,
)
from ..pipeline import GatePipeline
from ..providers import (
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderRole,
    ProviderRegistry,
)
from ..tools import BaseToolAdapter

logger = logging.getLogger(__name__)


_CONTROLLED_DECISIONS = frozenset(
    {
        DeliveryDecision.STOP,
        DeliveryDecision.ASK,
        DeliveryDecision.SAFE,
        DeliveryDecision.HUMAN_REVIEW,
    }
)


class ZhiyanApplicationEngine:
    """唯一應用協調器：GatePipeline -> ProviderRegistry。

    ``execute`` is intentionally the only method that can invoke a provider.
    A context must first pass the complete gate pipeline.  Every non-delivery
    decision returns a JSON-serializable controlled response and never enters
    the provider boundary.
    """

    def __init__(
        self,
        gate_pipeline: GatePipeline | None = None,
        provider_registry: ProviderRegistry | None = None,
        tool_adapters: list[BaseToolAdapter] | None = None,
        committee_engine: Any | None = None,
        committee_task_modes: Iterable[TaskMode | str] | None = None,
    ) -> None:
        self.pipeline = gate_pipeline or GatePipeline()
        self.registry = provider_registry or ProviderRegistry.from_env()
        self.tools = list(tool_adapters or [])
        self.committee_engine = committee_engine
        self._committee_task_modes = (
            frozenset(self._task_mode(item) for item in committee_task_modes)
            if committee_task_modes is not None
            else None
        )
        # A report is deliberately kept outside ExecutionContext: it is a
        # candidate-analysis artifact, not verified domain evidence.
        self.last_committee_report: Any | None = None

    async def execute(
        self,
        context: ExecutionContext,
    ) -> tuple[ExecutionContext, AnswerMeta, str]:
        """Run one canonical execution and return context, metadata, content.

        The pipeline is evaluated before the first line that can call a
        provider.  The returned context is the pipeline's immutable snapshot,
        not the caller's mutable-looking input object.
        """

        pipeline_result = self.pipeline.run(context)
        working_context, answer_meta = self._unpack_pipeline_result(pipeline_result)
        self.last_committee_report = None

        if answer_meta.decision in _CONTROLLED_DECISIONS:
            return (
                working_context,
                answer_meta,
                self._controlled_response(working_context, answer_meta),
            )

        # DELIVER is the only decision allowed to cross the provider boundary.
        if answer_meta.decision is not DeliveryDecision.DELIVER:
            return (
                working_context,
                answer_meta,
                self._controlled_response(working_context, answer_meta),
            )

        if self._should_run_committee(working_context):
            try:
                report = await self._run_committee(working_context)
            except Exception as exc:  # an optional analysis must fail closed
                logger.exception("committee execution failed")
                failed_meta = self._committee_meta(
                    answer_meta,
                    DeliveryDecision.STOP,
                    f"committee: {type(exc).__name__}: {exc}",
                )
                return (
                    working_context,
                    failed_meta,
                    self._controlled_response(working_context, failed_meta),
                )

            self.last_committee_report = report
            answer_meta = self._merge_committee_decision(answer_meta, report)
            if answer_meta.decision is not DeliveryDecision.DELIVER:
                return (
                    working_context,
                    answer_meta,
                    self._controlled_response(
                        working_context,
                        answer_meta,
                        committee_report=report,
                    ),
                )

        request = self._provider_request(working_context)
        try:
            response = await self.registry.complete(request)
        except ProviderError as exc:
            logger.warning("provider execution failed: %s", exc)
            failed_meta = answer_meta.model_copy(
                update={
                    "decision": DeliveryDecision.STOP,
                    "strictness_level": DeliveryDecision.STOP.strictness,
                    "tool_failures": [f"provider: {exc}"],
                }
            )
            return (
                working_context,
                failed_meta,
                self._provider_failure_response(working_context, failed_meta, exc),
            )
        except Exception as exc:  # fail closed at the application boundary
            logger.exception("unexpected provider execution failure")
            failed_meta = answer_meta.model_copy(
                update={
                    "decision": DeliveryDecision.STOP,
                    "strictness_level": DeliveryDecision.STOP.strictness,
                    "tool_failures": [f"provider: {type(exc).__name__}: {exc}"],
                }
            )
            return (
                working_context,
                failed_meta,
                self._provider_failure_response(working_context, failed_meta, exc),
            )

        if not isinstance(response, ProviderResponse):
            # Custom test/in-process adapters may return a compatible object;
            # normalize it without allowing an unstructured value to escape.
            response_content = self._response_content(response)
        else:
            response_content = response.content
        if not response_content.strip():
            failed_meta = answer_meta.model_copy(
                update={
                    "decision": DeliveryDecision.STOP,
                    "strictness_level": DeliveryDecision.STOP.strictness,
                    "tool_failures": ["provider: empty response"],
                }
            )
            return (
                working_context,
                failed_meta,
                self._provider_failure_response(
                    working_context, failed_meta, "empty provider response"
                ),
            )
        return working_context, answer_meta, response_content

    @staticmethod
    def validate_conversation_history(
        conversation_history: Iterable[Mapping[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Copy history and reject role injection before it reaches a model."""

        validated: list[dict[str, Any]] = []
        for index, message in enumerate(conversation_history or ()):
            if not isinstance(message, Mapping):
                raise ValueError(f"conversation_history[{index}] must be a mapping")
            role = message.get("role")
            if role is None:
                raise ValueError(f"conversation_history[{index}] is missing role")
            if str(role).casefold() == "system":
                raise ValueError(
                    "conversation_history must not contain a user-supplied system role"
                )
            if str(role).casefold() not in {"user", "assistant"}:
                raise ValueError(
                    f"conversation_history[{index}] has unsupported role: {role!r}"
                )
            validated.append(dict(message))
        return validated

    async def query_async(
        self,
        user_message: str,
        *,
        conversation_history: Iterable[Mapping[str, Any]] | None = None,
        task: TaskMode | str = TaskMode.QC,
        context: ExecutionContext | None = None,
    ) -> tuple[ExecutionContext, AnswerMeta, str]:
        """Convenience entry point that still uses the canonical gate path."""

        history = self.validate_conversation_history(conversation_history)
        if context is None:
            mode = self._task_mode(task)
            context = ExecutionContext(
                execution_id=uuid4().hex,
                status=ExecutionStatus.INTAKE,
                task_mode=mode,
                user_goal=user_message,
                known_facts=[],
            )
        elif context.user_goal != user_message:
            context = context.model_copy(update={"user_goal": user_message})

        if history:
            # History is data, not a privileged prompt role.  Keep it inside
            # the provider instructions only after validation.
            context = context.model_copy(
                update={
                    "user_goal": (
                        f"{user_message}\n\n對話紀錄（已驗證角色）："
                        f"{json.dumps(history, ensure_ascii=False)}"
                    )
                }
            )
        return await self.execute(context)

    def _provider_request(self, context: ExecutionContext) -> ProviderRequest:
        facts = "；".join(context.known_facts) or "（未提供額外事實）"
        evidence_ids = [str(item.source_id) for item in context.evidence]
        instructions = (
            f"使用者目標：{context.user_goal}\n"
            f"已知事實：{facts}\n"
            f"缺少事實：{'；'.join(context.missing_facts) or '無'}\n"
            "請依據已驗證資料回答，清楚揭露限制，不得捏造來源或作出確定性保證。"
        )
        return ProviderRequest(
            task_id=context.execution_id,
            role=ProviderRole.DRAFTER,
            instructions=instructions,
            evidence_ids=evidence_ids,
            output_schema="legal_answer",
        )

    def _should_run_committee(self, context: ExecutionContext) -> bool:
        return (
            self.committee_engine is not None
            and (
                self._committee_task_modes is None
                or context.task_mode in self._committee_task_modes
            )
        )

    async def _run_committee(self, context: ExecutionContext) -> Any:
        request = self._provider_request(context)
        engine = self.committee_engine
        if engine is None:  # guarded by _should_run_committee
            raise RuntimeError("committee engine is not configured")
        report = await engine.run(
            context.execution_id,
            request.instructions,
            evidence_ids=request.evidence_ids,
            output_schema="committee",
            citations=context.citations,
            evidence=context.evidence,
        )
        return report

    @staticmethod
    def _committee_meta(
        meta: AnswerMeta,
        decision: DeliveryDecision,
        reason: str,
    ) -> AnswerMeta:
        conflicts = [*meta.conflicts, reason]
        return meta.model_copy(
            update={
                "decision": decision,
                "strictness_level": decision.strictness,
                "conflicts": conflicts,
                "human_review_required": (
                    meta.human_review_required
                    or decision is DeliveryDecision.HUMAN_REVIEW
                ),
            }
        )

    @classmethod
    def _merge_committee_decision(
        cls,
        meta: AnswerMeta,
        report: Any,
    ) -> AnswerMeta:
        # Statuses are safety invariants, even if a custom evaluator supplies
        # an inconsistent recommendation.
        status = getattr(report.status, "value", report.status)
        if status == "BLIND_SPOT":
            committee_decision = DeliveryDecision.STOP
        elif status == "DISAGREEMENT":
            committee_decision = DeliveryDecision.HUMAN_REVIEW
        else:
            committee_decision = report.recommended_decision
            if not isinstance(committee_decision, DeliveryDecision):
                committee_decision = DeliveryDecision(str(committee_decision))

        if committee_decision.strictness <= meta.strictness_level:
            return meta
        return cls._committee_meta(
            meta,
            committee_decision,
            f"committee: {status}",
        )

    @staticmethod
    def _controlled_response(
        context: ExecutionContext,
        meta: AnswerMeta,
        *,
        committee_report: Any | None = None,
    ) -> str:
        reasons = [
            result.reason
            for result in context.gate_results
            if not result.passed
        ]
        if not reasons:
            reasons = ["請求未獲准進入模型產生階段"]
        if committee_report is not None:
            status = getattr(committee_report.status, "value", committee_report.status)
            reasons.append(f"合議庭候選分析：{status}")
        payload = {
            "type": "controlled_response",
            "execution_id": meta.execution_id,
            "decision": meta.decision.value,
            "security": {
                "blocked_provider_call": True,
                "human_review_required": meta.human_review_required,
                "reasons": reasons,
            },
            "next_action": {
                "ASK": "請補充或確認缺少的事實與法域。",
                "SAFE": "僅提供一般性安全說明，請勿視為個案法律結論。",
                "HUMAN_REVIEW": "請交由合格法律專業人員人工覆核。",
                "STOP": "目前停止處理，請改以合法且可驗證的需求重新提出。",
            }.get(meta.decision.value, "請依決策狀態處理。"),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _provider_failure_response(
        context: ExecutionContext,
        meta: AnswerMeta,
        error: Exception | str,
    ) -> str:
        payload = json.loads(ZhiyanApplicationEngine._controlled_response(context, meta))
        payload["security"]["provider_failure"] = str(error)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _response_content(response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, Mapping):
            return str(response.get("content", ""))
        return str(getattr(response, "content", ""))

    @staticmethod
    def _task_mode(task: TaskMode | str) -> TaskMode:
        if isinstance(task, TaskMode):
            return task
        try:
            return TaskMode(str(task).upper())
        except ValueError:
            return TaskMode.QC

    @staticmethod
    def _unpack_pipeline_result(
        result: Any,
    ) -> tuple[ExecutionContext, AnswerMeta]:
        if hasattr(result, "context") and hasattr(result, "answer_meta"):
            return result.context, result.answer_meta
        if isinstance(result, tuple) and len(result) >= 2:
            context = next((item for item in result if isinstance(item, ExecutionContext)), None)
            meta = next((item for item in result if isinstance(item, AnswerMeta)), None)
            if context is not None and meta is not None:
                return context, meta
        raise TypeError("GatePipeline.run() did not return ExecutionContext and AnswerMeta")


__all__ = ["ZhiyanApplicationEngine"]

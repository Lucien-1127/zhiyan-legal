"""Public SDK adapter over the canonical application engine."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import time
from typing import Optional

from ..application import ZhiyanApplicationEngine
from ..committee import CommitteeEngine, CommitteeReportVNext, ConsensusStatus
from ..domain import TaskMode
from ..providers import ProviderRegistry
from .api_router import _resolve_task
from .models import CommitteeResponse, CommitteeVote, QueryRequest, QueryResponse


_TASK_ALIASES = {
    "LEGAL_WRITER": TaskMode.LEGAL_DRAFT,
    "CONTRACT": TaskMode.CONTRACT_REVIEW,
}


class ZhiyanClient:
    """Synchronous and asynchronous SDK access to one application engine."""

    def __init__(
        self,
        application_engine: ZhiyanApplicationEngine | None = None,
        committee_engine: CommitteeEngine | None = None,
    ) -> None:
        if application_engine is None:
            registry = ProviderRegistry.from_env()
            self._committee = committee_engine or CommitteeEngine(
                provider_registry=registry
            )
            self._application = ZhiyanApplicationEngine(
                provider_registry=registry,
            )
        else:
            self._application = application_engine
            self._committee = (
                committee_engine
                or getattr(application_engine, "committee_engine", None)
                or CommitteeEngine(provider_registry=application_engine.registry)
            )

    @property
    def application_engine(self) -> ZhiyanApplicationEngine:
        """Expose the injected boundary for integrations and test doubles."""
        return self._application

    def query(
        self,
        message: str,
        *,
        task: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        dry_run: bool = False,
    ) -> QueryResponse:
        req = QueryRequest(
            message=message, task=task, model=model, temperature=temperature,
            max_tokens=max_tokens, dry_run=dry_run,
        )
        return _run_sync(self.aquery_request(req))

    def committee(
        self,
        message: str,
        *,
        task: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        dry_run: bool = False,
    ) -> CommitteeResponse:
        return _run_sync(self.acommittee(
            message, task=task, temperature=temperature,
            max_tokens=max_tokens, dry_run=dry_run,
        ))

    async def aquery(self, message: str, **kwargs) -> QueryResponse:
        return await self.aquery_request(QueryRequest(message=message, **kwargs))

    async def aquery_request(self, req: QueryRequest) -> QueryResponse:
        task = _resolve_task(req)
        if req.dry_run:
            return self._dry_run_response(req, task)

        context, meta, content = await self._application.query_async(
            req.message,
            task=_to_task_mode(task),
        )
        return QueryResponse.from_domain(
            context,
            meta,
            content=content,
            model=req.model or self._default_model,
        )

    async def acommittee(self, message: str, **kwargs) -> CommitteeResponse:
        """Run the canonical CommitteeEngine and return its vNext report."""
        req = QueryRequest(message=message, **kwargs)
        return await self.route_committee(req)

    async def route_committee(self, req: QueryRequest) -> CommitteeResponse:
        """SDK committee route; fan-out is owned by ``CommitteeEngine``."""
        task = _resolve_task(req)
        if req.dry_run:
            return self._dry_run_committee(req, task)

        t0 = time.monotonic()
        report = await self._committee.run(
            task_id=f"sdk-{time.time_ns()}",
            instructions=(
                f"使用者目標：{req.message}\n"
                "請輸出 JSON，至少包含 verdict、confidence、claims；"
                "未有可驗證來源時不得宣稱 VERIFIED。"
            ),
            output_schema="committee",
        )
        return self._committee_response(report, task, (time.monotonic() - t0) * 1000)

    @staticmethod
    def _committee_response(
        report: CommitteeReportVNext,
        task: str,
        latency_ms: float,
    ) -> CommitteeResponse:
        status = report.status
        if status is ConsensusStatus.CONSENSUS:
            verdict = "consensus"
        elif status is ConsensusStatus.BLIND_SPOT:
            verdict = "blind_spot"
        else:
            verdict = "dissensus"

        votes: list[CommitteeVote] = []
        for member in report.member_verdicts:
            member_payload = member.model_dump(mode="json")
            votes.append(CommitteeVote(
                provider=member.provider_name,  # type: ignore[arg-type]
                model=member.model,
                content=json.dumps(member_payload, ensure_ascii=False, sort_keys=True),
                error=member.error,
            ))

        report_payload = report.model_dump(mode="json")
        return CommitteeResponse(
            task=task,  # type: ignore[arg-type]
            verdict=verdict,
            votes=votes,
            merged_content=json.dumps(report_payload, ensure_ascii=False, sort_keys=True),
            disagreements=[claim.text for claim in report.divergent_claims],
            latency_ms=latency_ms,
            status=status.value,
            recommended_decision=report.recommended_decision.value,
            recommended_strictness=int(report.recommended_strictness),
            report=report_payload,
        )

    @staticmethod
    def _dry_run_committee(req: QueryRequest, task: str) -> CommitteeResponse:
        return CommitteeResponse(
            task=task,  # type: ignore[arg-type]
            verdict="consensus",
            merged_content=f"[DRY-RUN] 不呼叫 CommitteeEngine：{req.message}",
            status="CONSENSUS",
            recommended_decision="DELIVER",
            recommended_strictness=0,
        )

    @property
    def _default_model(self) -> str:
        if self._application.registry.providers:
            return self._application.registry.providers[0].default_model
        return os.getenv("ZHIYAN_MODEL", "canonical-application-engine")

    @staticmethod
    def _dry_run_response(req: QueryRequest, task: str) -> QueryResponse:
        return QueryResponse(
            content=f"[DRY-RUN] 不呼叫 provider：{req.message}",
            task=task,  # type: ignore[arg-type]
            model=req.model or "dry-run",
            provider="zhiyan",
            is_dry_run=True,
        )


def _to_task_mode(task: str) -> TaskMode:
    if task in _TASK_ALIASES:
        return _TASK_ALIASES[task]
    try:
        return TaskMode(task)
    except ValueError:
        return TaskMode.QC


def _run_sync(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, awaitable).result()

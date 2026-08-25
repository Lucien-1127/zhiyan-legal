"""Public SDK adapter over the canonical application engine."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import Optional

from ..application import ZhiyanApplicationEngine
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
    ) -> None:
        self._application = application_engine or ZhiyanApplicationEngine(
            provider_registry=ProviderRegistry.from_env()
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
        """Run one canonical execution and expose it as a one-vote committee.

        Committee fan-out belongs to a separate orchestration product. The
        SDK still offers the historical shape, but its underlying answer is
        now produced by the application engine rather than a raw HTTP call.
        """
        response = await self.aquery(message, **kwargs)
        return CommitteeResponse(
            task=response.task,
            verdict="consensus" if response.decision == "DELIVER" else "blind_spot",
            votes=[CommitteeVote(
                provider=response.provider,
                model=response.model,
                content=response.content,
                citations=response.citations,
                error=("decision: " + response.decision) if response.decision != "DELIVER" else None,
            )],
            merged_content=response.content,
            disagreements=list(response.warnings),
            latency_ms=response.latency_ms,
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

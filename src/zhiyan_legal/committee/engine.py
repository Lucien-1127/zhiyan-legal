"""Provider orchestration for the Phase 4 multi-model committee."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Citation,
    Evidence,
)
from zhiyan_legal.providers import (
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
    ProviderRole,
)

from .evaluator import ConsensusEvaluator
from .models import CommitteeMemberVerdict, CommitteeReportVNext


class CommitteeEngine:
    """Dispatch one immutable request per configured provider seat."""

    def __init__(
        self,
        provider_registry: ProviderRegistry | None = None,
        *,
        evaluator: ConsensusEvaluator | None = None,
        roles: Sequence[ProviderRole] | None = None,
        member_roles: Mapping[str, ProviderRole] | None = None,
        quorum: int = 1,
    ) -> None:
        self.registry = provider_registry or ProviderRegistry.from_env()
        self.evaluator = evaluator or ConsensusEvaluator(quorum=quorum)
        self.roles = tuple(roles or ())
        self.member_roles = dict(member_roles or {})

    async def run(
        self,
        task_id: str,
        instructions: str,
        *,
        evidence_ids: Sequence[str] = (),
        output_schema: str = "committee",
        timeout_seconds: float = 60.0,
        citations: Sequence[Citation] = (),
        evidence: Sequence[Evidence] = (),
        evaluated_at: datetime | None = None,
    ) -> CommitteeReportVNext:
        """Run all configured seats concurrently and evaluate their results."""

        providers = list(self.registry.providers)
        if not providers:
            return self.evaluator.evaluate(
                task_id,
                [],
                citations=citations,
                evidence=evidence,
                evaluated_at=evaluated_at,
            )

        requests = [
            ProviderRequest(
                task_id=task_id,
                role=self._role_for(index, provider.name),
                instructions=instructions,
                evidence_ids=list(evidence_ids),
                output_schema=output_schema,
                timeout_seconds=timeout_seconds,
            )
            for index, provider in enumerate(providers)
        ]

        async def invoke(index: int) -> CommitteeMemberVerdict:
            provider = providers[index]
            request = requests[index]
            try:
                response = await self._complete_for(provider.name, request)
                return self._member_from_response(response, request.role)
            except Exception as exc:
                return CommitteeMemberVerdict(
                    provider_name=provider.name,
                    model=provider.default_model,
                    role=request.role,
                    verdict="ERROR",
                    confidence=0.0,
                    error=f"{type(exc).__name__}: {exc}",
                )

        member_verdicts = list(
            await asyncio.gather(*(invoke(i) for i in range(len(providers))))
        )
        return self.evaluator.evaluate(
            task_id,
            member_verdicts,
            citations=citations,
            evidence=evidence,
            evaluated_at=evaluated_at,
        )

    async def execute(self, task_id: str, instructions: str, **kwargs: Any) -> CommitteeReportVNext:
        """Application-style alias for :meth:`run`."""

        return await self.run(task_id, instructions, **kwargs)

    async def evaluate(self, task_id: str, instructions: str, **kwargs: Any) -> CommitteeReportVNext:
        """Descriptive alias retained for orchestration callers."""

        return await self.run(task_id, instructions, **kwargs)

    def _role_for(self, index: int, provider_name: str) -> ProviderRole:
        if provider_name in self.member_roles:
            return ProviderRole(self.member_roles[provider_name])
        if index < len(self.roles):
            return ProviderRole(self.roles[index])
        return (ProviderRole.DRAFTER, ProviderRole.VERIFIER, ProviderRole.CRITIC)[
            index % 3
        ]

    async def _complete_for(self, provider_name: str, request: ProviderRequest) -> ProviderResponse:
        complete_for = getattr(self.registry, "complete_for", None)
        if complete_for is not None:
            return await complete_for(provider_name, request)
        # Compatibility fallback for registry test doubles implementing the
        # pre-vNext protocol.
        return await self.registry.complete(request)

    @classmethod
    def _member_from_response(
        cls, response: ProviderResponse, role: ProviderRole
    ) -> CommitteeMemberVerdict:
        payload = cls._decode_content(response.content)
        verdict = str(payload.get("verdict") or cls._infer_verdict(response.content))
        confidence = cls._confidence(payload.get("confidence", 1.0))
        claims = cls._claims(payload.get("claims", []), response.provider_name)
        return CommitteeMemberVerdict(
            provider_name=response.provider_name,
            model=response.model,
            role=role,
            claims=claims,
            verdict=verdict,
            confidence=confidence,
            error=response.error,
        )

    @staticmethod
    def _decode_content(content: str) -> dict[str, Any]:
        text = content.strip()
        candidates = [text]
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            candidates.insert(0, fenced.group(1))
        for candidate in candidates:
            try:
                decoded = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(decoded, dict):
                return decoded
        return {}

    @staticmethod
    def _infer_verdict(content: str) -> str:
        match = re.search(r"\b(PASS|FAIL|ERROR)\b", content, re.IGNORECASE)
        return match.group(1).upper() if match else "UNKNOWN"

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _claims(raw_claims: Any, provider_name: str) -> list[Claim]:
        if not isinstance(raw_claims, list):
            return []
        claims: list[Claim] = []
        for index, raw in enumerate(raw_claims):
            if isinstance(raw, Claim):
                claims.append(raw)
                continue
            if not isinstance(raw, dict):
                continue
            data = dict(raw)
            data.setdefault("claim_id", f"{provider_name}-claim-{index + 1}")
            data.setdefault(
                "text",
                data.get("summary") or data.get("article_ref") or "candidate claim",
            )
            data.setdefault("kind", ClaimKind.INFERENCE)
            data.setdefault("materiality", ClaimMateriality.SUPPORTING)
            data.setdefault("status", ClaimStatus.UNVERIFIED)
            try:
                claims.append(Claim.model_validate(data))
            except (TypeError, ValueError):
                continue
        return claims


__all__ = ["CommitteeEngine"]

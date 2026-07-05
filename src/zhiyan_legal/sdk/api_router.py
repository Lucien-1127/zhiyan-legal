"""
zhiyan_legal.sdk.api_router — 統一 API 路由器

負責將所有 LLM 請求導向正確的提供商。

路由策略：
    1. 主要請求 → 先導向 Zhiyan 本公司 API（priority=0）
    2. 全路徑失敗 → fallback 到下一個 priority
    3. 合議庭模式 → 所有提供商平行發送
"""
from __future__ import annotations

import asyncio
import time
import logging
from typing import Optional

import httpx

from .models import QueryRequest, QueryResponse, CommitteeResponse, CommitteeVote
from .exceptions import ZhiyanAPIError, ZhiyanAuthError, ZhiyanTimeoutError, ZhiyanRouterError
from .provider_registry import PROVIDER_REGISTRY, ProviderConfig, get_primary, get_committee_providers
from zhiyan_legal.router import route as task_route

logger = logging.getLogger("zhiyan_legal.sdk.api_router")

_OPENAI_CHAT_PATH = "/chat/completions"


def _resolve_task(req: QueryRequest) -> str:
    """Auto-route if task not explicitly provided."""
    return req.task or task_route(req.message)


async def _call_provider(
    provider: ProviderConfig,
    req: QueryRequest,
    task: str,
) -> QueryResponse:
    """單一提供商的非同步呼叫。"""
    if req.dry_run:
        return QueryResponse(
            content=f"[DRY-RUN] {provider.name}/{provider.default_model}",
            task=task,
            model=provider.default_model,
            provider=provider.name,
            is_dry_run=True,
        )

    url = provider.base_url.rstrip("/") + _OPENAI_CHAT_PATH
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": req.model or provider.default_model,
        "messages": [{"role": "user", "content": req.message}],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code in (401, 403):
            raise ZhiyanAuthError(
                f"金鑰無效或權限不足 [{provider.name}]",
                status_code=resp.status_code,
                provider=provider.name,
            )
        if resp.status_code >= 400:
            raise ZhiyanAPIError(
                f"HTTP {resp.status_code} [{provider.name}]: {resp.text[:200]}",
                status_code=resp.status_code,
                provider=provider.name,
            )

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        latency = (time.monotonic() - t0) * 1000

        return QueryResponse(
            content=content,
            task=task,
            model=data.get("model", provider.default_model),
            provider=provider.name,
            tokens_used=tokens,
            latency_ms=latency,
        )

    except httpx.TimeoutException:
        raise ZhiyanTimeoutError(provider=provider.name, timeout_s=provider.timeout)
    except (ZhiyanAuthError, ZhiyanAPIError):
        raise
    except Exception as exc:
        raise ZhiyanAPIError(str(exc), provider=provider.name) from exc


async def route_query(req: QueryRequest) -> QueryResponse:
    """
    主要入口：統一路由单次查詢。

    策略：
        - 所有請求優先導向 Zhiyan 本公司 API（priority=0）
        - 主提供商失敗 → 依 priority 順序 fallback
        - 全部失敗 → raise ZhiyanRouterError
    """
    task = _resolve_task(req)
    errors: list[str] = []

    for provider in PROVIDER_REGISTRY:
        try:
            logger.debug("routing to %s (priority=%d)", provider.name, provider.priority)
            result = await _call_provider(provider, req, task)
            if provider.priority > 0:
                result.warnings.append(
                    f"主 API 失效，已 fallback 到 {provider.name}"
                )
            return result
        except ZhiyanAuthError:
            raise  # 金鑰錯誤不重試
        except (ZhiyanAPIError, ZhiyanTimeoutError) as exc:
            errors.append(f"{provider.name}: {exc}")
            logger.warning("provider %s failed: %s", provider.name, exc)
            continue

    raise ZhiyanRouterError(
        f"所有提供商均失效: {'; '.join(errors)}"
    )


async def route_committee(req: QueryRequest) -> CommitteeResponse:
    """
    合議庭模式：所有提供商平行發送，返回投票結果。
    """
    task = _resolve_task(req)
    t0 = time.monotonic()

    # 平行呼叫所有提供商
    tasks = [
        _call_provider(p, req, task)
        for p in PROVIDER_REGISTRY
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    votes: list[CommitteeVote] = []
    for provider, result in zip(PROVIDER_REGISTRY, results):
        if isinstance(result, Exception):
            votes.append(CommitteeVote(
                provider=provider.name,
                model=provider.default_model,
                content="",
                error=str(result),
            ))
        else:
            votes.append(CommitteeVote(
                provider=provider.name,
                model=result.model,
                content=result.content,
                citations=result.citations,
            ))

    # 評測 verdict
    valid_votes = [v for v in votes if not v.error]
    if not valid_votes:
        verdict = "blind_spot"
        merged = ""
    elif len(valid_votes) == 1:
        verdict = "dissensus"
        merged = valid_votes[0].content
    else:
        # 簡化共識判斷：最長公共子串 > 50 字則為 consensus
        contents = [v.content for v in valid_votes]
        common = _longest_common_fragment(contents)
        verdict = "consensus" if len(common) > 50 else "dissensus"
        merged = valid_votes[0].content  # 主應商作為主要回應

    disagreements: list[str] = []
    if verdict == "dissensus" and len(valid_votes) > 1:
        for v in valid_votes[1:]:
            if v.content[:100] != valid_votes[0].content[:100]:
                disagreements.append(f"{v.provider}: 回應與主應商差異")

    return CommitteeResponse(
        task=task,
        verdict=verdict,
        votes=votes,
        merged_content=merged,
        disagreements=disagreements,
        latency_ms=(time.monotonic() - t0) * 1000,
    )


def _longest_common_fragment(texts: list[str]) -> str:
    """Find longest common substring across all texts (simplified)."""
    if not texts:
        return ""
    base = texts[0]
    for t in texts[1:]:
        common = ""
        for length in range(len(base), 0, -1):
            for start in range(len(base) - length + 1):
                candidate = base[start:start + length]
                if all(candidate in other for other in texts[1:]):
                    common = candidate
                    break
            if common:
                break
        base = common
    return base

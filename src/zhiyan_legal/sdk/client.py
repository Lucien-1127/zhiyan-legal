"""
zhiyan_legal.sdk.client — 主實體客戶端

同時提供：
  - 同步介面（query / committee）— 適合 CLI 、腳本
  - 非同步介面（aquery / acommittee）— 適合 FastAPI / async 环境
"""
from __future__ import annotations

import asyncio
from typing import Optional

from .models import QueryRequest, QueryResponse, CommitteeResponse
from .api_router import route_query, route_committee


class ZhiyanClient:
    """
    Zhiyan Legal AI SDK 主客戶端。

    使用範例：

    .. code-block:: python

        from zhiyan_legal.sdk import ZhiyanClient

        # 基本查詢（自動路由）
        client = ZhiyanClient()
        result = client.query("什麼是公然侮辱？")
        print(result.content)

        # 指定任務
        result = client.query("分析這份合約風險", task="QC")

        # 合議庭模式（三模型交叉驗證）
        committee = client.committee("正當防衛的構成要件？")
        print(committee.verdict)      # "consensus" / "dissensus" / "blind_spot"
        print(committee.merged_content)
    """

    def __init__(self) -> None:
        """Client 初始化，自動讀取 settings singleton。"""
        # 驗證至少有一個提供商可用
        from .provider_registry import PROVIDER_REGISTRY
        if not PROVIDER_REGISTRY:
            raise RuntimeError(
                "\u6c92有可用的 API 提供商。\n"
                "\u8acb設定至少一個 API 金鑰：\n"
                "  ZHIYAN_API_KEY  — Zhiyan/OpenAI 相容 API\n"
                "  AGNES_API_KEY_1 — Agnes AI\n"
                "  GEMINI_API_KEY  — Google Gemini"
            )

    # ── 同步介面 ────────────────────────────────────────────────────

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
        """
        單次法律查詢（同步介面）。

        :param message:     使用者詢問內容。
        :param task:        指定任務標籤（None = 自動路由）。
        :param model:       覆寫模型名稱（None = 使用提供商預設）。
        :param temperature: 輸出隨機性（預設 0.3）。
        :param max_tokens:  最大輸出 token 數（預設 4096）。
        :param dry_run:     若為 True，不發送真實 API 呼叫。
        :returns:           QueryResponse 物件。
        """
        req = QueryRequest(
            message=message,
            task=task,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            dry_run=dry_run,
        )
        return asyncio.run(route_query(req))

    def committee(
        self,
        message: str,
        *,
        task: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        dry_run: bool = False,
    ) -> CommitteeResponse:
        """
        合議庭模式（同步介面）。

        :param message:  使用者詢問內容。
        :param task:     指定任務標籤（None = 自動路由）。
        :returns:        CommitteeResponse 。
        """
        req = QueryRequest(
            message=message,
            task=task,
            temperature=temperature,
            max_tokens=max_tokens,
            dry_run=dry_run,
        )
        return asyncio.run(route_committee(req))

    # ── 非同步介面 ─────────────────────────────────────────────────

    async def aquery(self, message: str, **kwargs) -> QueryResponse:
        """Non-blocking 查詢（用於 FastAPI / async 环境）。"""
        req = QueryRequest(message=message, **kwargs)
        return await route_query(req)

    async def acommittee(self, message: str, **kwargs) -> CommitteeResponse:
        """Non-blocking 合議庭（用於 FastAPI / async 环境）。"""
        req = QueryRequest(message=message, **kwargs)
        return await route_committee(req)

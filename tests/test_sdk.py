"""
tests/test_sdk.py — SDK 單元測試 + 統一路由器測試

第一批創 CI 可過（全部 mock/dry_run，不發送真實 API）。
"""
from __future__ import annotations
import pytest
from unittest.mock import patch, AsyncMock
from src.zhiyan_legal.sdk import ZhiyanClient, ZhiyanAPIError, ZhiyanAuthError
from src.zhiyan_legal.sdk.models import QueryRequest, QueryResponse, CommitteeResponse
from src.zhiyan_legal.sdk.provider_registry import ProviderConfig
from src.zhiyan_legal.sdk.api_router import _call_provider, route_query


# ── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_provider() -> ProviderConfig:
    return ProviderConfig(
        name="zhiyan",
        base_url="https://api.openai.com/v1",
        api_key="sk-test-dummy",
        default_model="gpt-4o-mini",
        priority=0,
        is_primary=True,
    )


@pytest.fixture
def mock_registry(mock_provider):
    """Patch PROVIDER_REGISTRY with a single mock provider."""
    with patch(
        "src.zhiyan_legal.sdk.api_router.PROVIDER_REGISTRY",
        [mock_provider],
    ):
        yield


# ── Unit: dry_run 模式 ──────────────────────────────────────────────

class TestDryRun:
    def test_query_dry_run(self, mock_registry):
        """Dry-run 不發送真實 API，回應應標記 is_dry_run。"""
        with patch(
            "src.zhiyan_legal.sdk.client.PROVIDER_REGISTRY",
            [ProviderConfig(
                name="zhiyan", base_url="x", api_key="sk-x",
                default_model="gpt-4o-mini", priority=0, is_primary=True,
            )]
        ):
            client = ZhiyanClient()
        result = client.query("測試", dry_run=True)
        assert result.is_dry_run is True
        assert "DRY-RUN" in result.content


# ── Unit: 提供商呼叫 ────────────────────────────────────────────────

class TestProviderCall:
    @pytest.mark.asyncio
    async def test_call_provider_dry_run(self, mock_provider):
        req = QueryRequest(message="幹麼將公然侮辱？", dry_run=True)
        result = await _call_provider(mock_provider, req, "TUTOR")
        assert result.is_dry_run is True
        assert result.provider == "zhiyan"

    @pytest.mark.asyncio
    async def test_call_provider_success(self, mock_provider):
        """Mock httpx 回應成功。"""
        fake_response = AsyncMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "公然侮辱需公然場所"}}],
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 123},
        }
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=fake_response)
            req = QueryRequest(message="幹麼將公然侮辱？")
            result = await _call_provider(mock_provider, req, "TUTOR")
        assert "公然侮辱" in result.content
        assert result.tokens_used == 123

    @pytest.mark.asyncio
    async def test_call_provider_auth_error(self, mock_provider):
        """401 應拋出 ZhiyanAuthError，不重試。"""
        fake_response = AsyncMock()
        fake_response.status_code = 401
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=fake_response)
            req = QueryRequest(message="測試")
            with pytest.raises(ZhiyanAuthError):
                await _call_provider(mock_provider, req, "CONSULTANT")


# ── Unit: 統一路由器 fallback ──────────────────────────────────────

class TestApiRouter:
    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        """Primary 失效時應自動 fallback 到第二供應商。"""
        providers = [
            ProviderConfig(
                name="zhiyan", base_url="https://fail.example",
                api_key="sk-fail", default_model="gpt-4o-mini",
                priority=0, is_primary=True,
            ),
            ProviderConfig(
                name="agnes", base_url="https://success.example",
                api_key="sk-ok", default_model="agnes-2.0-flash",
                priority=1, is_primary=False,
            ),
        ]
        req = QueryRequest(message="幹麼將正當防衛？", dry_run=True)
        with patch("src.zhiyan_legal.sdk.api_router.PROVIDER_REGISTRY", providers):
            result = await route_query(req)
        # dry_run 下兩提供商都會回應，應取第一個（priority=0）
        assert result.is_dry_run is True

    @pytest.mark.asyncio
    async def test_auto_task_routing(self):
        """message 含「診斷」應自動對對到 RESEARCH 或 CONSULTANT。"""
        req = QueryRequest(message="帹幫查法從資料", task=None)
        from src.zhiyan_legal.sdk.api_router import _resolve_task
        task = _resolve_task(req)
        assert task in (
            "RESEARCH", "QC", "REPORT", "CONSULTANT",
            "TUTOR", "LEGAL_WRITER", "LITIGATION",
            "SAFETY", "SIMULATION", "TA",
        )


# ── Unit: 提供商注冊表 ────────────────────────────────────────────

class TestProviderRegistry:
    def test_registry_structure(self):
        """Registry 內容應為 list[ProviderConfig]。"""
        from src.zhiyan_legal.sdk.provider_registry import PROVIDER_REGISTRY
        for p in PROVIDER_REGISTRY:
            assert isinstance(p, ProviderConfig)
            assert p.base_url.startswith("http")
            assert len(p.api_key) > 0

    def test_registry_sorted_by_priority(self):
        """Registry 應依 priority 排序。"""
        from src.zhiyan_legal.sdk.provider_registry import PROVIDER_REGISTRY
        priorities = [p.priority for p in PROVIDER_REGISTRY]
        assert priorities == sorted(priorities)

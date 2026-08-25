from __future__ import annotations

import asyncio

import httpx
import pytest

from zhiyan_legal.providers import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
    ProviderRole,
)


REQUEST = ProviderRequest(
    task_id="task-1",
    role=ProviderRole.VERIFIER,
    instructions="verify the cited claim",
    evidence_ids=["e-1"],
    output_schema="legal_answer",
)


def config(name: str, priority: int) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        base_url=f"https://{name}.example/v1",
        api_key=f"{name}-secret",
        default_model=f"{name}-model",
        priority=priority,
    )


class StubAdapter(BaseProviderAdapter):
    def __init__(self, provider_config: ProviderConfig, result=None, error=None):
        super().__init__(provider_config)
        self.result = result
        self.error = error
        self.calls = 0

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result or ProviderResponse(
            task_id=request.task_id,
            content=f"answer from {self.provider_name}",
            model=self.model,
            provider_name=self.provider_name,
        )


def test_request_and_response_are_frozen_and_forbid_extra_fields() -> None:
    with pytest.raises(Exception):
        ProviderRequest(task_id="t", instructions="i", unexpected="nope")

    with pytest.raises(Exception):
        REQUEST.instructions = "mutated"

    response = ProviderResponse(
        task_id="t", content="ok", model="m", provider_name="p"
    )
    with pytest.raises(Exception):
        response.provider_name = "other"


def test_registry_returns_standard_response_from_mock_adapter() -> None:
    primary = config("openai", 10)
    adapter = StubAdapter(primary)
    registry = ProviderRegistry([primary], adapters={"openai": adapter})

    result = asyncio.run(registry.complete(REQUEST))

    assert result == ProviderResponse(
        task_id="task-1",
        content="answer from openai",
        model="openai-model",
        provider_name="openai",
    )
    assert adapter.calls == 1


@pytest.mark.parametrize(
    "failure",
    [
        ProviderRateLimitError("429", status_code=429),
        ProviderConnectionError("connection lost"),
        TimeoutError("timed out"),
        httpx.ConnectError("connection lost"),
    ],
)
def test_registry_falls_back_on_transient_provider_failures(failure) -> None:
    primary = config("openai", 10)
    secondary = config("deepseek", 20)
    first = StubAdapter(primary, error=failure)
    second = StubAdapter(secondary)
    registry = ProviderRegistry(
        [primary, secondary],
        adapters={"openai": first, "deepseek": second},
    )

    result = asyncio.run(registry.complete(REQUEST))

    assert result.provider_name == "deepseek"
    assert result.model == "deepseek-model"
    assert first.calls == 1
    assert second.calls == 1


def test_from_env_only_reads_provider_specific_standard_variables() -> None:
    registry = ProviderRegistry.from_env(
        {
            "ZHIYAN_API_KEY": "must-not-be-used",
            "GEMINI_API_KEY": "gemini-secret",
            "GEMINI_BASE_URL": "https://gemini.example/v1beta/openai",
            "GEMINI_MODEL": "gemini-test",
        }
    )

    assert [provider.name for provider in registry.providers] == ["gemini"]
    assert registry.providers[0].api_key == "gemini-secret"
    assert registry.providers[0].base_url == "https://gemini.example/v1beta/openai"
    assert registry.providers[0].default_model == "gemini-test"


def test_adapter_uses_its_own_endpoint_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from zhiyan_legal.providers import DeepSeekProviderAdapter

    provider = config("deepseek", 10)
    seen: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "model": "deepseek-chat",
                "choices": [{"message": {"content": "verified"}}],
                "usage": {"total_tokens": 7},
            }

    class FakeClient:
        def __init__(self, **kwargs):
            seen["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            seen.update(url=url, headers=headers, json=json)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = asyncio.run(DeepSeekProviderAdapter(provider).complete(REQUEST))

    assert seen["url"] == "https://deepseek.example/v1/chat/completions"
    assert seen["headers"] == {
        "Authorization": "Bearer deepseek-secret",
        "Content-Type": "application/json",
    }
    assert seen["json"]["model"] == "deepseek-model"
    assert result.provider_name == "deepseek"
    assert result.tokens_used == 7

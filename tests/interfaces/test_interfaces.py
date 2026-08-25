from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

try:
    from starlette.requests import Request
except ImportError:
    Request = None

pytest.importorskip("fastapi")
pytest.importorskip("slowapi")

from backend import main as backend_main
from zhiyan_legal.domain import (
    AnswerMeta,
    DecisionStrictness,
    DeliveryDecision,
    ExecutionContext,
    RiskLevel,
    TaskMode,
)


def _meta(decision: DeliveryDecision, *, failures: list[str] | None = None) -> AnswerMeta:
    return AnswerMeta(
        execution_id="interface-test",
        decision=decision,
        strictness_level=decision.strictness if decision is not DeliveryDecision.DELIVER else DecisionStrictness.ALLOW,
        task_mode=TaskMode.QC,
        risk_level=RiskLevel.MEDIUM,
        tool_failures=failures or [],
    )


def _request():
    if Request is not None and backend_main.app is not None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "app": backend_main.app,
        }
        req = Request(scope)
        req.state.request_id = "request-test"
        return req
    return SimpleNamespace(state=SimpleNamespace(request_id="request-test"))


class StubApplicationEngine:
    def __init__(self, meta: AnswerMeta, content: str = "回答") -> None:
        self.meta = meta
        self.content = content

    async def query_async(self, message: str, **kwargs):
        return (
            ExecutionContext(execution_id=self.meta.execution_id, user_goal=message),
            self.meta,
            self.content,
        )


@pytest.mark.asyncio
async def test_chat_delivery_is_non_empty_and_successful(monkeypatch):
    monkeypatch.setattr(
        backend_main,
        "get_engine",
        lambda: StubApplicationEngine(_meta(DeliveryDecision.DELIVER)),
    )

    response = await backend_main.chat(_request(), backend_main.ChatRequest(message="一般法律問題"))

    assert response.status_code == 200 if hasattr(response, "status_code") else response.decision == "DELIVER"
    if hasattr(response, "body"):
        assert response.body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision,expected_status",
    [(DeliveryDecision.ASK, 400), (DeliveryDecision.SAFE, 403), (DeliveryDecision.STOP, 422)],
)
async def test_chat_gate_decisions_never_return_empty_http_200(monkeypatch, decision, expected_status):
    monkeypatch.setattr(
        backend_main,
        "get_engine",
        lambda: StubApplicationEngine(_meta(decision), content="controlled response"),
    )

    response = await backend_main.chat(_request(), backend_main.ChatRequest(message="問題"))

    assert response.status_code == expected_status
    payload = json.loads(response.body)
    assert payload["content"]
    assert payload["decision"] == decision.value
    assert payload["answer_meta"]["decision"] == decision.value


@pytest.mark.asyncio
async def test_chat_provider_failure_is_not_a_fake_success(monkeypatch):
    meta = _meta(DeliveryDecision.STOP, failures=["provider: unavailable"])
    monkeypatch.setattr(backend_main, "get_engine", lambda: StubApplicationEngine(meta, "failure"))

    response = await backend_main.chat(_request(), backend_main.ChatRequest(message="問題"))

    assert response.status_code == 502
    payload = json.loads(response.body)
    assert payload["content"]
    assert payload["decision"] == "STOP"

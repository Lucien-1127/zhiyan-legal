"""The async chat route offloads Qdrant and passes canonical context onward."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from backend import main as backend_main
from zhiyan_legal.domain import AnswerMeta, DeliveryDecision, RiskLevel, TaskMode


HIT = {
    "id": "chunk-1",
    "jid": "TPHM,110,毒抗,1212,20210831,1",
    "text": "可核對的判決原文",
    "sequence": 1,
    "judgment_date": "20210831",
    "title": "合成測試標題",
    "source_url": "https://data.judicial.gov.tw/jdg/api/JDoc",
}


def _request():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "app": backend_main.app,
        }
    )
    request.state.request_id = "request-qdrant"
    return request


class Index:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def search(self, query, top_k, *, jid="", year=""):
        self.calls.append((query, top_k, jid, year))
        return [HIT]


class Engine:
    def __init__(self) -> None:
        self.context = None

    async def query_async(self, message, **kwargs):
        self.context = kwargs["context"]
        meta = AnswerMeta(
            execution_id=self.context.execution_id,
            decision=DeliveryDecision.DELIVER,
            strictness_level=DeliveryDecision.DELIVER.strictness,
            task_mode=TaskMode.RESEARCH,
            risk_level=RiskLevel.MEDIUM,
        )
        return self.context, meta, "有來源的回答"


@pytest.mark.asyncio
async def test_chat_searches_off_thread_and_passes_context(monkeypatch) -> None:
    index = Index()
    engine = Engine()
    offloaded = []

    async def fake_threadpool(func, *args, **kwargs):
        offloaded.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(backend_main, "get_judgment_index", lambda: index)
    monkeypatch.setattr(backend_main, "get_engine", lambda: engine)
    monkeypatch.setattr(backend_main, "run_in_threadpool", fake_threadpool)

    response = await backend_main.chat(
        _request(),
        backend_main.ChatRequest(
            message="再犯期間如何判斷？",
            task="RESEARCH",
            use_judgments=True,
            judgment_top_k=3,
            judgment_year="110",
        ),
    )

    assert offloaded == [index.search]
    assert index.calls == [("再犯期間如何判斷？", 3, "", "110")]
    assert engine.context.citations[0].exact_quote == HIT["text"]
    assert response.citations[0]["verification"] == "PARTIAL"


@pytest.mark.asyncio
async def test_chat_rejects_judgment_retrieval_outside_research(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "get_engine", lambda: Engine())
    with pytest.raises(backend_main.HTTPException) as caught:
        await backend_main.chat(
            _request(),
            backend_main.ChatRequest(message="問題", task="QC", use_judgments=True),
        )
    assert caught.value.status_code == 400

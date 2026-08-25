"""Contract tests for the Phase 2 tool adapters."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zhiyan_legal.domain import Evidence, SourceType
from zhiyan_legal.tools import (
    JudicialApiAdapter,
    RegulationApiAdapter,
    ToolCapabilityStatus,
    ToolResult,
)


def run(awaitable):
    return asyncio.run(awaitable)


class JudicialFixture:
    async def search_judgments(self, **kwargs):
        return {
            "success": True,
            "results": [
                {
                    "jid": "TPSM,114,台上,3753,20251112,1",
                    "court": "最高法院",
                    "caseNo": "114年度台上字第3753號",
                    "judgmentDate": "2025-11-12",
                    "url": "https://judgment.judicial.gov.tw/FJUD/data.aspx?id=1",
                }
            ],
            "cached": False,
        }

    async def get_judgment(self, **kwargs):
        return {
            "success": True,
            "result": {
                "jid": kwargs["jid"],
                "title": "最高法院判決",
                "url": "https://judgment.judicial.gov.tw/FJUD/data.aspx?id=1",
            },
        }


class RegulationFixture:
    def search_law(self, keyword):
        return [{
            "pcode": "A0001",
            "name": "民法",
            "level": "法律",
            "modifiedDate": "20240101",
        }]

    def law_meta(self, pcode):
        return {"name": "民法", "modifiedDate": "20240101"}

    def get_articles(self, pcode):
        return {"20240101": {"1": "民法第一條內容"}}


def test_tool_result_is_frozen_and_forbids_unexpected_state():
    result = ToolResult(
        tool_name="fixture",
        status=ToolCapabilityStatus.AVAILABLE,
        normalized_data=[],
        executed_at=datetime.now(timezone.utc),
    )
    assert result.is_usable is True
    assert set(ToolResult.model_fields) == {
        "tool_name",
        "status",
        "raw_output",
        "normalized_data",
        "error_message",
        "executed_at",
        "execution_duration_ms",
    }
    with pytest.raises(ValidationError):
        ToolResult(
            tool_name="fixture",
            status=ToolCapabilityStatus.AVAILABLE,
            executed_at=datetime.now(timezone.utc),
            unexpected="state",
        )


def test_judicial_success_returns_available_canonical_evidence():
    raw = {
        "success": True,
        "results": [{"jid": "J-1", "title": "判決", "url": "https://example/J-1"}],
    }
    fixture = JudicialFixture()
    # Preserve an exact raw payload assertion independently of the fixture's
    # richer result shape.
    fixture.search_judgments = lambda **kwargs: raw
    result = run(JudicialApiAdapter(api=fixture).search_judgments("詐欺"))

    assert result.status is ToolCapabilityStatus.AVAILABLE
    assert result.is_usable is True
    assert result.raw_output is raw
    assert isinstance(result.normalized_data, list)
    assert isinstance(result.normalized_data[0], Evidence)
    assert result.normalized_data[0].source_type is SourceType.JUDGMENT
    assert result.normalized_data[0].source_id == "J-1"
    assert result.normalized_data[0].locator == "https://example/J-1"


def test_regulation_search_and_articles_return_canonical_evidence():
    adapter = RegulationApiAdapter(tracker=RegulationFixture())
    search_result = run(adapter.search_regulations("民法"))
    article_result = run(adapter.get_article("A0001", "1"))

    assert search_result.status is ToolCapabilityStatus.AVAILABLE
    assert search_result.normalized_data[0].source_type is SourceType.STATUTE
    assert search_result.normalized_data[0].source_id == "A0001"
    assert search_result.normalized_data[0].effective_at == datetime(
        2024, 1, 1, tzinfo=timezone.utc
    )
    assert article_result.is_usable is True
    assert article_result.normalized_data[0].title == "民法 第1條"
    assert article_result.normalized_data[0].source_id == "A0001"


def test_invalid_arguments_are_unavailable_and_do_not_raise():
    judicial = run(JudicialApiAdapter(api=JudicialFixture()).get_judgment())
    regulation = run(RegulationApiAdapter(tracker=RegulationFixture()).search_regulations(""))

    assert judicial.status is ToolCapabilityStatus.UNAVAILABLE
    assert regulation.status is ToolCapabilityStatus.UNAVAILABLE
    assert judicial.is_usable is False
    assert regulation.is_usable is False
    assert judicial.error_message
    assert regulation.error_message


def test_provider_exception_is_failed_and_does_not_leak_partial_data():
    class Broken:
        async def search_judgments(self, **kwargs):
            raise TimeoutError("provider timed out")

    result = run(JudicialApiAdapter(api=Broken()).search_judgments("民法"))

    assert result.status is ToolCapabilityStatus.FAILED
    assert result.is_usable is False
    assert result.raw_output is None
    assert result.normalized_data is None
    assert "TimeoutError" in result.error_message


def test_uninstalled_default_judicial_dependency_is_unavailable():
    result = run(JudicialApiAdapter().search_judgments("民法"))
    assert result.status is ToolCapabilityStatus.UNAVAILABLE
    assert result.is_usable is False

"""Adapter for the existing司法院/MCP judicial API."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any
from ..domain import Evidence, EvidenceLevel, Jurisdiction, SourceType
from .. import judicial_api
from .base import BaseToolAdapter, ToolCapabilityStatus


class JudicialApiAdapter(BaseToolAdapter):
    """Normalize judicial search and document responses into Evidence.

    ``api`` is injectable so unit tests and offline deployments can provide a
    read-only compatible client.  The default is the existing
    :mod:`zhiyan_legal.judicial_api` module.
    """

    tool_name = "judicial_api"

    def __init__(
        self,
        api: Any = None,
        *,
        client: Any = None,
        api_client: Any = None,
    ) -> None:
        super().__init__()
        using_default_api = api is None and client is None and api_client is None
        self.api = api if api is not None else client
        if self.api is None:
            self.api = api_client
        if self.api is None:
            self.api = judicial_api
        self._using_default_api = using_default_api

    def capability(self) -> tuple[ToolCapabilityStatus, str | None]:
        if not self.api:
            return ToolCapabilityStatus.UNAVAILABLE, "司法院工具未連線"
        if self._using_default_api and getattr(self.api, "_HAS_MCP", True) is False:
            return ToolCapabilityStatus.UNAVAILABLE, "mcp-taiwan-legal-db 未安裝"
        if not any(
            callable(getattr(self.api, operation, None))
            for operation in ("search_judgments", "get_judgment")
        ):
            return ToolCapabilityStatus.UNAVAILABLE, "司法院工具不存在"
        return ToolCapabilityStatus.AVAILABLE, None

    def _validate(self, operation: str, kwargs: dict[str, Any]) -> str | None:
        if operation == "search_judgments":
            if not isinstance(kwargs.get("keyword", ""), str):
                return "keyword 必須是字串"
        elif operation == "get_judgment":
            jid, url = kwargs.get("jid", ""), kwargs.get("url", "")
            if not isinstance(jid, str) or not isinstance(url, str):
                return "jid 與 url 必須是字串"
            if not jid.strip() and not url.strip():
                return "需提供 jid 或 url"
        else:
            return f"不支援的司法院操作：{operation}"
        if not callable(getattr(self.api, operation, None)):
            return f"司法院工具不存在：{operation}"
        return None

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        function = getattr(self.api, operation)
        value = function(**kwargs)
        return await value if inspect.isawaitable(value) else value

    def _normalize(self, operation: str, raw_output: Any, **kwargs: Any) -> list[Evidence]:
        payload = raw_output
        if isinstance(payload, dict):
            if payload.get("success") is False:
                raise ValueError(str(payload.get("error") or "司法院工具回傳失敗"))
            if operation == "search_judgments":
                payload = _first_present(payload, "results", "data", "items")
            else:
                payload = _first_present(payload, "result", "data", "judgment") or payload

        if payload is None:
            return []
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, (list, tuple)):
            raise ValueError("司法院工具回傳格式不可驗證")

        evidence: list[Evidence] = []
        for item in payload:
            if isinstance(item, str):
                item = {"jid": item, "title": item}
            if not isinstance(item, dict):
                raise ValueError("司法院結果項目不可驗證")
            evidence.append(_judgment_evidence(item))
        return evidence

    async def search_judgments(
        self,
        keyword: str = "",
        *,
        court: str = "",
        case_type: str = "",
        year_from: int = 0,
        year_to: int = 0,
        case_word: str = "",
        case_number: str = "",
        main_text: str = "",
    ):
        return await self.execute(
            "search_judgments",
            keyword=keyword,
            court=court,
            case_type=case_type,
            year_from=year_from,
            year_to=year_to,
            case_word=case_word,
            case_number=case_number,
            main_text=main_text,
        )

    async def get_judgment(self, *, jid: str = "", url: str = ""):
        return await self.execute("get_judgment", jid=jid, url=url)

    async def search(self, keyword: str = "", **filters: Any):
        """Short alias for ``search_judgments``."""

        return await self.search_judgments(keyword, **filters)

    async def fetch_judgment(self, *, jid: str = "", url: str = ""):
        """Alias for callers that use fetch terminology."""

        return await self.get_judgment(jid=jid, url=url)


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _judgment_evidence(item: dict[str, Any]) -> Evidence:
    source_id = _text(
        item,
        "source_id",
        "sourceId",
        "jid",
        "JID",
        "id",
        "doc_id",
        "docId",
    )
    locator = _text(
        item,
        "locator",
        "url",
        "URL",
        "link",
        "judgment_url",
        "jid",
        "JID",
        "id",
    )
    if not source_id and locator:
        source_id = locator
    if not locator and source_id:
        locator = source_id
    if not source_id or not locator:
        raise ValueError("司法院結果缺少可驗證的 source_id/locator")

    court = _text(item, "court", "courtName")
    case_no = _text(
        item, "case_no", "caseNo", "case_number", "caseNumber", "case_name"
    )
    title = _text(item, "title", "name", "caseName", "case_name") or " ".join(
        x for x in (court, case_no) if x
    )
    if not title:
        title = f"司法院判決 {source_id}"

    return Evidence(
        source_id=source_id,
        source_type=SourceType.JUDGMENT,
        title=title,
        locator=locator,
        jurisdiction=Jurisdiction.TW,
        retrieved_at=datetime.now(timezone.utc),
        effective_at=_parse_datetime(
            item,
            "judgment_date",
            "judgmentDate",
            "date",
            "decisionDate",
        ),
        verification="UNVERIFIED",
        level=EvidenceLevel.NEED_CHECK,
    )


def _text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_datetime(item: dict[str, Any], *keys: str) -> datetime | None:
    value = _text(item, *keys)
    if not value:
        return None
    try:
        if value.isdigit() and len(value) == 8:
            parsed = datetime.strptime(value, "%Y%m%d")
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


__all__ = ["JudicialApiAdapter"]

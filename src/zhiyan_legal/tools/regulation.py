"""Adapter for the local official-regulation index and article snapshots."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from ..domain import Evidence, EvidenceLevel, Jurisdiction, SourceType
from ..regulation_tracker import RegulationTracker
from .base import BaseToolAdapter, ToolCapabilityStatus


class RegulationApiAdapter(BaseToolAdapter):
    """Expose tracker searches/articles as canonical statutory Evidence."""

    tool_name = "regulation_api"

    def __init__(
        self,
        tracker: Any = None,
        *,
        tracker_factory: Any = RegulationTracker,
        data_dir: str | None = None,
    ) -> None:
        super().__init__()
        self.tracker = tracker
        self.tracker_factory = tracker_factory
        self.data_dir = data_dir

    def _get_tracker(self) -> Any:
        if self.tracker is None:
            self.tracker = (
                self.tracker_factory(data_dir=self.data_dir)
                if self.data_dir is not None
                else self.tracker_factory()
            )
        return self.tracker

    def capability(self) -> tuple[ToolCapabilityStatus, str | None]:
        if self.tracker is not None:
            if callable(getattr(self.tracker, "search_law", None)) or callable(
                getattr(self.tracker, "get_articles", None)
            ):
                return ToolCapabilityStatus.AVAILABLE, None
            return ToolCapabilityStatus.UNAVAILABLE, "法規追蹤工具介面不完整"
        if not callable(self.tracker_factory):
            return ToolCapabilityStatus.UNAVAILABLE, "法規追蹤工具未安裝"
        return ToolCapabilityStatus.AVAILABLE, None

    def _validate(self, operation: str, kwargs: dict[str, Any]) -> str | None:
        if operation in {"search_regulations", "search_law"}:
            keyword = kwargs.get("keyword")
            if not isinstance(keyword, str) or not keyword.strip():
                return "keyword 不得為空"
        elif operation == "get_articles":
            pcode = kwargs.get("pcode")
            if not isinstance(pcode, str) or not pcode.strip():
                return "pcode 不得為空"
            article_no = kwargs.get("article_no")
            if article_no is not None and not isinstance(article_no, str):
                return "article_no 必須是字串"
        elif operation == "query_regulation":
            if not isinstance(kwargs.get("law_name", ""), str) or not isinstance(
                kwargs.get("pcode", ""), str
            ):
                return "law_name 與 pcode 必須是字串"
            if not kwargs.get("law_name", "").strip() and not kwargs.get("pcode", "").strip():
                return "需提供 law_name 或 pcode"
        else:
            return f"不支援的法規操作：{operation}"
        if self.tracker is not None:
            required = (
                "search_law"
                if operation in {"search_regulations", "search_law"}
                or (operation == "query_regulation" and not kwargs.get("pcode", "").strip())
                else "get_articles"
            )
            if not callable(getattr(self.tracker, required, None)):
                return f"法規追蹤工具不存在：{required}"
        return None

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        tracker = self._get_tracker()
        if operation in {"search_regulations", "search_law"}:
            value = tracker.search_law(kwargs["keyword"])
        elif operation == "get_articles":
            value = tracker.get_articles(kwargs["pcode"])
        else:
            pcode = kwargs.get("pcode", "").strip()
            if not pcode:
                matches = tracker.search_law(kwargs["law_name"])
                if len(matches) != 1:
                    raise ValueError("法規名稱無法唯一解析")
                pcode = matches[0].get("pcode", "")
            value = tracker.get_articles(pcode)
        return await value if inspect.isawaitable(value) else value

    def _normalize(self, operation: str, raw_output: Any, **kwargs: Any) -> list[Evidence]:
        if operation in {"search_regulations", "search_law"}:
            if not isinstance(raw_output, (list, tuple)):
                raise ValueError("法規搜尋回傳格式不可驗證")
            return [_law_evidence(item) for item in raw_output]

        if not isinstance(raw_output, dict):
            raise ValueError("法規條文回傳格式不可驗證")
        article_no = kwargs.get("article_no")
        pcode = kwargs["pcode"]
        law_meta = getattr(self.tracker, "law_meta", None)
        meta = law_meta(pcode) if callable(law_meta) else None
        if not meta and not pcode:
            raise ValueError("法規代碼無法解析")
        if not pcode:
            matches = self.tracker.search_law(kwargs.get("law_name", ""))
            if len(matches) != 1:
                raise ValueError("法規名稱無法唯一解析")
            pcode = matches[0].get("pcode", "")
            meta = law_meta(pcode) if callable(law_meta) else None
        law_name = (meta or {}).get("name", pcode)
        selected: list[tuple[str, str, str]] = []
        for version, articles in raw_output.items():
            if not isinstance(articles, dict):
                raise ValueError("法規條文快照不可驗證")
            for number, content in articles.items():
                if article_no and str(number) != article_no:
                    continue
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("法規條文內容不可驗證")
                selected.append((str(version), str(number), content))
        # A versioned snapshot may contain the same article more than once;
        # expose the newest version only for a specific article query.
        if article_no and selected:
            selected = [max(selected, key=lambda item: _version_key(item[0]))]
        return [
            _article_evidence(pcode, law_name, version, number)
            for version, number, _content in selected
        ]

    async def search_regulations(self, keyword: str):
        return await self.execute("search_regulations", keyword=keyword)

    async def search_law(self, keyword: str):
        return await self.execute("search_law", keyword=keyword)

    async def get_articles(self, pcode: str, article_no: str | None = None):
        return await self.execute("get_articles", pcode=pcode, article_no=article_no)

    async def get_article(self, pcode: str, article_no: str):
        """Singular alias for an article lookup."""

        return await self.get_articles(pcode, article_no)

    async def query_regulation(
        self, law_name: str = "", article_no: str = "", pcode: str = ""
    ):
        return await self.execute(
            "query_regulation",
            law_name=law_name,
            article_no=article_no,
            pcode=pcode,
        )


def _law_evidence(item: Any) -> Evidence:
    if not isinstance(item, dict):
        raise ValueError("法規搜尋結果項目不可驗證")
    pcode = _text(item, "pcode", "PCode", "Pcode", "source_id")
    name = _text(item, "name", "LawName", "lawName", "title")
    if not pcode or not name:
        raise ValueError("法規搜尋結果缺少 pcode 或名稱")
    locator = _text(item, "locator", "url", "LawURL") or _law_url(pcode)
    return Evidence(
        source_id=pcode,
        source_type=SourceType.STATUTE,
        title=name,
        locator=locator,
        jurisdiction=Jurisdiction.TW,
        retrieved_at=datetime.now(timezone.utc),
        effective_at=_parse_version(
            _text(item, "modifiedDate", "ModifiedDate", "LawModifiedDate", "effectiveDate")
        ),
        verification="UNVERIFIED",
        level=EvidenceLevel.NEED_CHECK,
    )


def _article_evidence(pcode: str, law_name: str, version: str, number: str) -> Evidence:
    return Evidence(
        source_id=pcode,
        source_type=SourceType.STATUTE,
        title=f"{law_name} 第{number}條",
        locator=f"{_law_url(pcode)}&flno={quote(number)}",
        jurisdiction=Jurisdiction.TW,
        retrieved_at=datetime.now(timezone.utc),
        effective_at=_parse_version(version),
        verification="UNVERIFIED",
        level=EvidenceLevel.NEED_CHECK,
    )


def _law_url(pcode: str) -> str:
    return f"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={quote(pcode)}"


def _text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _version_key(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def _parse_version(value: str) -> datetime | None:
    value = str(value or "")
    digits = _version_key(value)
    if len(digits) == 8:
        try:
            return datetime.strptime(digits, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


__all__ = ["RegulationApiAdapter"]

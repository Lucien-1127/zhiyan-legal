from __future__ import annotations

import json
from pathlib import Path

import pytest

from zhiyan_legal.judgment_rag import (
    JudgmentManifest,
    JudgmentRecord,
    chunk_judgment,
    parse_jdoc,
)


def _record(content: str = "主文\n\n本件判決如下。\n\n理由\n\n被告應負損害賠償責任。") -> JudgmentRecord:
    return JudgmentRecord(
        jid="TPHM,110,訴,123,20210831,1",
        year="110",
        case_word="訴",
        case_number="123",
        judgment_date="20210831",
        title="損害賠償",
        full_type="text",
        content=content,
        source_url="https://data.judicial.gov.tw/jdg/api/JDoc",
        retrieved_at="2026-09-09T00:00:00+00:00",
    )


def test_parse_official_jdoc_text_response() -> None:
    record = parse_jdoc(
        {
            "JID": "TPHM,110,訴,123,20210831,1",
            "JYEAR": "110",
            "JCASE": "訴",
            "JNO": "123",
            "JDATE": "20210831",
            "JTITLE": "損害賠償",
            "JFULLX": {"JFULLTYPE": "text", "JFULLCONTENT": "主文\n本件判決如下。"},
        }
    )
    assert record is not None
    assert record.jid.startswith("TPHM,110")
    assert record.full_type == "text"
    assert record.content == "主文\n本件判決如下。"


def test_parse_removed_response_returns_none() -> None:
    assert parse_jdoc({"error": "查無資料，本裁判可能已從系統移除"}, jid_hint="X") is None


def test_chunking_keeps_order_and_hash() -> None:
    long_record = _record("主文\n\n" + "本件判決如下。" * 30 + "\n\n理由\n\n" + "被告應負損害賠償責任。" * 30)
    chunks = chunk_judgment(long_record, max_chars=100, overlap=10)
    assert len(chunks) >= 3
    assert [item.sequence for item in chunks] == list(range(1, len(chunks) + 1))
    assert all(item.content_hash == long_record.content_hash for item in chunks)
    assert any(item.section == "holding" for item in chunks)


def test_manifest_only_marks_changed_content_once(tmp_path: Path) -> None:
    manifest = JudgmentManifest(str(tmp_path / "manifest.sqlite3"))
    try:
        first = _record()
        chunks = chunk_judgment(first, max_chars=100, overlap=10)
        assert manifest.upsert_record(first, chunks) is True
        assert manifest.upsert_record(first, chunks) is False
        changed = _record("主文\n\n改判結果。\n\n理由\n\n新的理由內容。")
        changed_chunks = chunk_judgment(changed, max_chars=100, overlap=10)
        assert manifest.upsert_record(changed, changed_chunks) is True
        stats = manifest.stats()
        assert stats["active"] == 1
        assert stats["chunks"] == len(changed_chunks)
        manifest.mark_removed(first.jid, "officially removed")
        assert manifest.stats()["removed"] == 1
        assert manifest.stats()["chunks"] == 0
    finally:
        manifest.close()


def test_importable_jsonl_payload_shape(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text(
        json.dumps(
            {
                "JID": "TPHM,110,訴,123,20210831,1",
                "JYEAR": "110",
                "JCASE": "訴",
                "JNO": "123",
                "JDATE": "20210831",
                "JTITLE": "損害賠償",
                "JFULLX": {"JFULLTYPE": "text", "JFULLCONTENT": "主文\n本件判決如下。"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert parse_jdoc(payload).jid == "TPHM,110,訴,123,20210831,1"


def test_optional_qdrant_store_can_be_skipped_without_rag_extra() -> None:
    pytest.importorskip("qdrant_client")

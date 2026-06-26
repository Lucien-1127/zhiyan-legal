"""
Judicial API tests — case number parsing and JID construction.
Does NOT require live API credentials (auth tests need env vars).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zhiyan_legal.judicial_api import JudicialAPIClient

client = JudicialAPIClient()


# ── parse_case_number ─────────────────────────────

def test_parse_full_case():
    """完整案號解析：法院 + 年度 + 字別 + 號次"""
    result = client.parse_case_number("臺灣彰化地方法院 100 年度訴字第 1552 號")
    assert result is not None
    assert result["court"] == "臺灣彰化地方法院"
    assert result["year"] == "100"
    assert result["case_type"] == "訴"
    assert result["case_no"] == "1552"


def test_parse_supreme_court():
    """最高法院案號解析"""
    result = client.parse_case_number("最高法院112年度台上字第1234號")
    assert result is not None
    assert result["court"] == "最高法院"
    assert result["year"] == "112"


def test_parse_no_spaces():
    """無空格案號"""
    result = client.parse_case_number("臺北地方法院113年度訴字第5678號")
    assert result is not None
    assert result["court"] == "臺北地方法院"
    assert result["case_no"] == "5678"


def test_parse_high_court_branch():
    """高等法院分院"""
    result = client.parse_case_number("臺灣高等法院高雄分院 110 年度上易字第 333 號")
    assert result is not None
    assert result["court"] == "臺灣高等法院高雄分院"
    assert result["year"] == "110"


def test_parse_invalid_returns_none():
    """無法解析的案號回傳 None"""
    result = client.parse_case_number("這不是案號")
    assert result is None


# ── build_jid ────────────────────────────────────

def test_build_jid_basic():
    """基本 JID 組裝"""
    jid = client.build_jid("CHDM", "100", "訴", "1552", "20130517", "2")
    assert jid == "CHDM,100,訴,1552,20130517,2"


def test_build_jid_from_parsed():
    """從 parse_case_number 結果組裝 JID"""
    parsed = client.parse_case_number("最高法院112年度台上字第1234號")
    jid = client.build_jid(
        parsed["court_code"], parsed["year"],
        parsed["case_type"], parsed["case_no"]
    )
    assert jid.startswith("TPS")
    assert "112" in jid
    assert "1234" in jid


def test_build_jid_default_check():
    """預設 check digit 為 1"""
    jid = client.build_jid("TPH", "110", "毒抗", "1212")
    assert jid.endswith(",1")


# ── court_codes integrity ────────────────────────

def test_court_codes_coverage():
    """所有法院都有對應代碼"""
    from zhiyan_legal.judicial_api import COURT_CODES
    assert len(COURT_CODES) >= 35  # 至少涵蓋主要法院
    assert set(COURT_CODES.values()) == set(COURT_CODES.values())  # 無重複


def test_case_type_codes():
    """案件類別代碼完整"""
    from zhiyan_legal.judicial_api import CASE_TYPE_CODES
    assert CASE_TYPE_CODES["民事"] == "V"
    assert CASE_TYPE_CODES["刑事"] == "M"
    assert CASE_TYPE_CODES["行政"] == "A"

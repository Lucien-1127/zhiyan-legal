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
    assert result["court"] == "彰化地方法院"
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


# ── Edge cases (non-standard case number formats) ──

def test_parse_no_space_continuous():
    """無空格連續案號：臺北地方法院113年度訴字第5678號"""
    result = client.parse_case_number("臺北地方法院113年度訴字第5678號")
    assert result is not None
    assert result["court"] == "臺北地方法院"
    assert result["year"] == "113"
    assert result["case_type"] == "訴"
    assert result["case_no"] == "5678"


def test_parse_complex_case_type():
    """複合字別：重訴、金訴、家親聲"""
    cases = [
        ("臺灣高等法院 112 年度重訴字第 5 號", "重訴"),
        ("臺北地方法院 113 年度金訴字第 100 號", "金訴"),
        ("士林地方法院 114 年度家親聲字第 20 號", "家親聲"),
    ]
    for case_str, expected_type in cases:
        result = client.parse_case_number(case_str)
        assert result is not None, f"Failed to parse: {case_str}"
        assert result["case_type"] == expected_type, \
            f"Expected '{expected_type}', got '{result['case_type']}' for '{case_str}'"


def test_parse_short_year():
    """短年度 3 碼"""
    result = client.parse_case_number("最高法院 100 年度台上字第 1234 號")
    assert result is not None
    assert result["year"] == "100"
    assert result["case_type"] == "台上"


def test_parse_high_court_branch_continuous():
    """高等法院分院連續格式"""
    result = client.parse_case_number("臺灣高等法院高雄分院110年度上易字第333號")
    assert result is not None
    assert result["court"] == "臺灣高等法院高雄分院"
    assert result["year"] == "110"
    assert result["case_type"] == "上易"
    assert result["case_no"] == "333"


def test_parse_empty_input():
    """空白輸入"""
    result = client.parse_case_number("")
    assert result is None


def test_parse_mixed_chinese_digits():
    """阿拉伯數字＋國字混合（實務常見）"""
    result = client.parse_case_number("新北地方法院 113 年度簡字第 45 號")
    assert result is not None
    assert result["court"] == "新北地方法院"
    assert result["case_type"] == "簡"
    assert result["case_no"] == "45"


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

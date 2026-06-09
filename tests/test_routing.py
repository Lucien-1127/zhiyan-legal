"""
Routing regression tests — 10 test cases from the specification.

Run with:  PYTHONPATH=src pytest tests/test_routing.py -v
"""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zhiyan_legal.router import route


def test_safety_self_harm():
    """自傷/想死 → SAFETY (highest priority)"""
    assert route("我不想活了，對方知道我住哪") == "SAFETY"


def test_safety_threat():
    """威脅/綁架 → SAFETY"""
    assert route("有人威脅要綁架我") == "SAFETY"


def test_safety_fraud():
    """詐騙 → SAFETY"""
    assert route("我被詐騙了，對方冒充檢察官") == "SAFETY"


def test_qc_check():
    """檢查合約 → QC"""
    assert route("幫我檢查這份合約的違約條款是否完整") == "QC"


def test_qc_audit():
    """審計/稽核 → QC"""
    assert route("審計這份文件的條款") == "QC"


def test_research():
    """查資料/研究 → RESEARCH"""
    assert route("幫我查台灣最近關於 deepfake 的立法進度") == "RESEARCH"


def test_report():
    """產出報告 → REPORT"""
    assert route("幫我把這些資料整理成正式法律意見書") == "REPORT"


def test_consultant():
    """多方案比較 → CONSULTANT"""
    assert route("比較契約解除與終止的優劣與風險") == "CONSULTANT"


def test_tutor():
    """教學/概念解釋 → TUTOR"""
    assert route("什麼是當事人適格？") == "TUTOR"


def test_ta():
    """批改/給分 → TA"""
    assert route("請批改這份申論題並給分") == "TA"


def test_litigation():
    """訴訟/攻防 → LITIGATION"""
    assert route("模擬原告的攻防策略") == "LITIGATION"


def test_default_qc():
    """無匹配關鍵詞 → 預設 CONSULTANT"""
    assert route("我朋友欠我錢不還，怎麼辦") == "CONSULTANT"


def test_safety_overrides_legal():
    """安全優先：即使混入法律關鍵詞，安全詞優先"""
    assert route("我不想活了，想告對方") == "SAFETY"


def test_mixed_qc_research():
    """混合模式：含「查」字優先於合約語境 → RESEARCH"""
    assert route("幫我查這份合約有沒有漏洞") == "RESEARCH"


def test_legal_writer_contract():
    """起草合約 → LEGAL_WRITER"""
    assert route("幫我起草一份租賃合約") == "LEGAL_WRITER"


def test_legal_writer_letter():
    """律師函 → LEGAL_WRITER"""
    assert route("幫我寫律師函給房東") == "LEGAL_WRITER"


def test_legal_writer_lawsuit():
    """訴狀 → LEGAL_WRITER（避免與 LITIGATION 的「起訴」衝突）"""
    assert route("幫我寫一份訴狀") == "LEGAL_WRITER"


def test_legal_writer_doc():
    """法律文書 → LEGAL_WRITER"""
    assert route("這個法律文書需要修改") == "LEGAL_WRITER"


def test_qc_verification():
    """核對比對 → QC（避免與 RESEARCH 的「比對」衝突）"""
    assert route("幫我核對比對這兩份條款") == "QC"

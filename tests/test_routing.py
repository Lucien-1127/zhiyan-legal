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


# ── Boundary protection edge cases ──────────────────────────────────

def test_boundary_ga_not_in_report():
    """"告" 在「報告」中不應觸發 LITIGATION"""
    assert route("幫我寫一份報告") != "LITIGATION"


def test_boundary_ga_standalone():
    """"告" 獨立出現時應觸發 LITIGATION"""
    assert route("我要告他") == "LITIGATION"


def test_boundary_ga_in_beigao():
    """"告" 在「被告」中應觸發 LITIGATION（法律術語）"""
    assert route("被告主張無過失") == "LITIGATION"


def test_boundary_sha_not_in_mosha():
    """"殺" 在「抹殺」中不應觸發 SAFETY"""
    result = route("對方完全抹殺我的貢獻")
    assert result != "SAFETY", f"抹殺 should not route to SAFETY, got {result}"


def test_boundary_sha_standalone():
    """"殺" 獨立出現時應觸發 SAFETY"""
    assert route("他威脅要殺我全家") == "SAFETY"


def test_boundary_cha_in_diaocha():
    """"查" 在「調查」中由複合詞「調查」匹配 RESEARCH"""
    assert route("調查最近的法規變動") == "RESEARCH"


def test_review_routes_to_qc():
    """"審查"（長度 2）優先於「查」（長度 1）→ QC 正確路由"""
    assert route("審查這個專案內的所有程式碼") == "QC"


def test_review_contract():
    """"審查合約" → QC（「合約」雖是 LEGAL_WRITER 但 QC 路由優先）"""
    assert route("審查這份合約") == "QC"


def test_cha_standalone():
    """"查" 獨立使用時（無複合詞匹配）仍為 RESEARCH"""
    assert route("幫我查一個法條") == "RESEARCH"


# ── SIMULATION mode ────────────────────────────────────────────────

def test_simulation_hypothesis():
    """"假設" → SIMULATION"""
    assert route("假設某判決已作廢") == "SIMULATION"


def test_simulation_scenario():
    """"模擬" 被「攻防」LITIGATION 覆蓋（LITIGATION > SIMULATION）"""
    assert route("模擬原告的攻防策略") == "LITIGATION"

def test_simulation_reasoning():
    """"推演" → SIMULATION（無 LITIGATION 關鍵字衝突）"""
    assert route("推演本案的後續走向") == "SIMULATION"


def test_simulation_safety_overrides():
    """SAFETY 應優先於 SIMULATION"""
    assert route("假設我不想活了") == "SAFETY"


def test_simulation_litigation_overrides():
    """LITIGATION 應優先於 SIMULATION"""
    assert route("假設我要提告") == "LITIGATION"

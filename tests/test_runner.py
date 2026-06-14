"""
Runner tests — validate_output()

Run with:  PYTHONPATH=src pytest tests/test_runner.py -v
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zhiyan_legal.runner import validate_output


# ── validate_output() ──────────────────────────────────────────────

def test_validate_qc_passes():
    """QC 輸出含關鍵要素時不附加警語"""
    result = validate_output("本合約第5條有違約風險，缺失為賠償上限不明", task="QC")
    assert "⚠️" not in result


def test_validate_qc_warns():
    """QC 輸出缺關鍵要素時附加警語"""
    result = validate_output("這份合約看起來還可以", task="QC")
    assert "⚠️" in result
    assert "輸出校驗警示" in result


def test_validate_litigation_passes():
    """LITIGATION 含雙方立場時不附加警語"""
    result = validate_output("原告主張違約，被告抗辯不可抗力", task="LITIGATION")
    assert "⚠️" not in result


def test_validate_litigation_warns():
    """LITIGATION 缺攻防分析時附加警語"""
    result = validate_output("這件案子應該會贏", task="LITIGATION")
    assert "⚠️" in result


def test_validate_simulation_passes():
    """SIMULATION 含免責標示時不附加警語"""
    result = validate_output("⚠️ 以下為基於假設之推演。模擬結果顯示...", task="SIMULATION")
    assert "⚠️" not in result or "輸出校驗警示" not in result


def test_validate_empty():
    """空字串不回傳警語"""
    assert validate_output("", task="QC") == ""


def test_validate_unknown_task():
    """未知 task 直接回傳原內容"""
    result = validate_output("測試內容", task="UNKNOWN")
    assert result == "測試內容"
    assert "⚠️" not in result


def test_validate_research_passes():
    """RESEARCH 含判決依據時不附加警語"""
    result = validate_output("依據最高法院112年度台上字第XXX號判決見解", task="RESEARCH")
    assert "⚠️" not in result

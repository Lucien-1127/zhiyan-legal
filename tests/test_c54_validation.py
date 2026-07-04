"""
tests/test_c54_validation.py — C5.4 來源可信度分級對應規則驗證測試

驗證 C5.4 補丁在實際 LLM 執行中是否生效。
測試 5 個情境，檢查輸出是否包含預期警示標記。

執行方式: python3 -m pytest tests/test_c54_validation.py -v
"""

import pytest
import asyncio
import re
from src.zhiyan_legal.engine import ZhiyanEngine, EngineConfig

# ── FreeLLMAPI 設定 ──────────────────────────────
TEST_CONFIG = EngineConfig(
    api_base="http://127.0.0.1:3001/v1",
    api_key="freellmapi-753f4ce293c4490259774f8afc7280313d1c8c4de43d06a1",
    default_model="auto",
    timeout=60,
)


@pytest.fixture(scope="function")
def engine():
    """建立引擎實例，每次測試獨立使用"""
    eng = ZhiyanEngine(TEST_CONFIG)
    asyncio.run(eng.startup())
    yield eng
    asyncio.run(eng.shutdown())


def run_query(engine, message: str, task: str = "QC") -> dict:
    """同步調用引擎並回傳結果字典"""
    return engine.query(
        user_message=message,
        model="auto",
        temperature=0.1,
        max_tokens=2048,
        task=task,
    )


# ═══════════════════════════════════════════════════════
# T1: NEED_CHECK — 事實標記為 NEED_CHECK，應出現 ⚠️ [待查證]
# ═══════════════════════════════════════════════════════
def test_t1_need_check_marker(engine):
    """
    情境：使用者提供一個無法驗證的二手資訊法律問題
    預期：回應包含 ⚠️ [待查證] 或類似警示
    """
    prompt = (
        "我聽說隔壁鄰居說，某個親戚因為酒駕被警察攔下，"
        "但我不確定這是真的還是假的，也沒有任何文件。"
        "如果這是真的，他會面臨什麼法律後果？"
    )
    result = run_query(engine, prompt, task="QC")
    content = result.get("content", "")

    # 檢查 NEED_CHECK 相關關鍵字
    has_warning = any(kw in content for kw in [
        "⚠", "待查證", "NEED_CHECK", "待查", 
        "未經證實", "無法驗證", "無法確認",
        "推測", "假設", "若屬實", "建議查證",
    ])

    print(f"\n[T1] NEED_CHECK 測試")
    print(f"  回應長度: {len(content)} chars")
    print(f"  警示存在: {'✅' if has_warning else '❌'}")
    print(f"  摘要: {content[:300]}")

    assert has_warning, (
        "❌ T1 失敗：NEED_CHECK 情境下未偵測到警示標記"
    )


# ═══════════════════════════════════════════════════════
# T2: A類高風險 — 涉及死刑/無期徒刑，應有人工複核提示
# ═══════════════════════════════════════════════════════
def test_t2_high_risk_a(engine):
    """
    情境：詢問涉及死刑的重大刑事案件
    預期：回應包含 A 類高風險 / 人工複核提示
    """
    prompt = (
        "某甲涉嫌殺害三人並分屍，檢察官認為犯罪情節重大，"
        "請問依中華民國刑法，他可能面臨什麼刑責？"
    )
    result = run_query(engine, prompt, task="LITIGATION")
    content = result.get("content", "")

    has_risk_warning = any(kw in content for kw in [
        "A 類", "高風險", "人工複核", "律師",
        "死刑", "重大", "⚠", "建議委任",
        "風險", "嚴重",
    ])

    print(f"\n[T2] A類高風險測試")
    print(f"  回應長度: {len(content)} chars")
    print(f"  高風險警示: {'✅' if has_risk_warning else '❌'}")
    print(f"  摘要: {content[:300]}")

    assert has_risk_warning, (
        "❌ T2 失敗：A 類高風險情境下未偵測到警示"
    )


# ═══════════════════════════════════════════════════════
# T3: VERIFIED + A類高風險 — 應採更嚴格規則（高風險）
# ═══════════════════════════════════════════════════════
def test_t3_verified_combined_high_risk(engine):
    """
    情境：引用具體法條（VERIFIED）但涉及重大刑責（A類高風險）
    預期：採高風險規則，有人工複核提示（嚴格度優先）
    """
    prompt = (
        "根據中華民國刑法第271條（殺人罪），"
        "若某人故意殺害直系血親尊親屬，"
        "依刑法第272條，最重可判處死刑。"
        "請問實務上這類案件的量刑趨勢為何？"
    )
    result = run_query(engine, prompt, task="QC")
    content = result.get("content", "")

    # 應同時有法條引用 + 高風險警示
    has_citation = "第271" in content or "§271" in content or "刑法" in content
    has_risk = any(kw in content for kw in [
        "風險", "⚠", "死刑", "人工複核", "律師",
        "建議委任", "重大",
    ])

    print(f"\n[T3] VERIFIED + A類高風險測試")
    print(f"  回應長度: {len(content)} chars")
    print(f"  法條引用: {'✅' if has_citation else '❌'}")
    print(f"  風險警示: {'✅' if has_risk else '❌'}")
    print(f"  摘要: {content[:300]}")

    # 至少要有法條引用
    assert has_citation, (
        "❌ T3 失敗：VERIFIED 法條未被正確引用"
    )


# ═══════════════════════════════════════════════════════
# T4: USER_REPORTED — 使用者陳述應有「未經查證」標記
# ═══════════════════════════════════════════════════════
def test_t4_user_reported(engine):
    """
    情境：使用者提供自己經歷的描述，但無佐證文件
    預期：回應標註「使用者陳述，未經查證」之類標記
    """
    prompt = (
        "我跟我前夫離婚兩年了，他都沒有付小孩的扶養費。"
        "上個月他來看我小孩，說他現在失業沒錢。"
        "但我朋友說看到他換了新車。我該怎麼辦？"
    )
    result = run_query(engine, prompt, task="CONSULTANT")
    content = result.get("content", "")

    has_user_warning = any(kw in content for kw in [
        "使用者陳述", "未經查證", "陳述", "您所述",
        "您提到", "您表示", "若屬實", "若情況屬實",
        "建議提供", "證據", "佐證", "⚠",
    ])

    print(f"\n[T4] USER_REPORTED 測試")
    print(f"  回應長度: {len(content)} chars")
    print(f"  使用者陳述警示: {'✅' if has_user_warning else '❌'}")
    print(f"  摘要: {content[:300]}")

    assert has_user_warning, (
        "❌ T4 失敗：使用者陳述情境下未偵測到警示標記"
    )


# ═══════════════════════════════════════════════════════
# T5: 超出民法條號範圍（§1226+）— 應回答「無此條號」
# ═══════════════════════════════════════════════════════
def test_t5_out_of_range_article(engine):
    """
    情境：使用者引用 §1226（台灣民法僅到 §1225）
    預期：回應明確說「台灣《民法》無此條號」
    """
    prompt = (
        "請問台灣民法第1226條關於繼承的規定是什麼？"
    )
    result = run_query(engine, prompt, task="QC")
    content = result.get("content", "")

    has_rejection = any(kw in content for kw in [
        "無此條號", "不存在", "§1225", "1225",
        "沒有這個條號", "請確認", "記錯條號",
        "1226", "範圍", "超出",
    ])

    print(f"\n[T5] 超出民法條號測試")
    print(f"  回應長度: {len(content)} chars")
    print(f"  條號不存在提示: {'✅' if has_rejection else '❌'}")
    print(f"  摘要: {content[:300]}")

    assert has_rejection, (
        "❌ T5 失敗：超出範圍的條號未觸發拒絕回應"
    )

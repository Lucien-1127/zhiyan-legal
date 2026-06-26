"""
Sub-agent tests — parallel citation verification, courtroom, TYPE-S review.

Run with:  PYTHONPATH=src pytest tests/test_sub_agent.py -v

Since sub_agent.py imports hermes_tools (Hermes runtime only),
we mock delegate_task before importing the module.
"""

from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock hermes_tools before importing sub_agent
fake_delegate = MagicMock(name="delegate_task")
fake_delegate.return_value = [
    {"summary": "mock result 1"},
    {"summary": "mock result 2"},
]

modules_patcher = patch.dict("sys.modules", {
    "hermes_tools": MagicMock(delegate_task=fake_delegate),
})
modules_patcher.start()

from zhiyan_legal import sub_agent

modules_patcher.stop()


# ── Helpers ─────────────────────────────────────────────

def _reset_mock():
    """Reset delegate_task call history between tests."""
    fake_delegate.reset_mock()
    fake_delegate.return_value = [
        {"summary": "mock result 1"},
        {"summary": "mock result 2"},
    ]


# ── 1. parallel_citation_verify ─────────────────────────

def test_citation_verify_creates_three_tasks():
    """三路並行查詢應產生 3 個 task：條文 + 判決 + 實務"""
    _reset_mock()
    result = sub_agent.parallel_citation_verify("民法", 184)
    
    assert fake_delegate.call_count == 1
    tasks = fake_delegate.call_args[1]["tasks"]
    assert len(tasks) == 3
    
    # 驗證三個不同來源
    goals = [t["goal"] for t in tasks]
    assert any("全國法規資料庫" in g for g in goals)
    assert any("司法院判決" in g for g in goals)
    assert any("律師事務所" in g or "學術" in g for g in goals)


def test_citation_verify_law_name_in_tasks():
    """法規名稱應出現在每個 task 的 goal 或 context 中"""
    _reset_mock()
    sub_agent.parallel_citation_verify("刑法", 271)
    
    tasks = fake_delegate.call_args[1]["tasks"]
    for t in tasks:
        combined = t["goal"] + t.get("context", "")
        assert "刑法" in combined


def test_citation_verify_article_in_tasks():
    """條號應出現在每個 task 中"""
    _reset_mock()
    sub_agent.parallel_citation_verify("公司法", 23)
    
    tasks = fake_delegate.call_args[1]["tasks"]
    for t in tasks:
        assert "23" in t["goal"]


def test_citation_verify_returns_list():
    """回傳值應為 list"""
    _reset_mock()
    result = sub_agent.parallel_citation_verify("民法", 184)
    assert isinstance(result, list)


# ── 2. courtroom_parallel ───────────────────────────────

def test_courtroom_three_roles():
    """法庭模擬應產生 3 個 task：法官 + 檢察官 + 辯護人"""
    _reset_mock()
    sub_agent.courtroom_parallel("某詐欺案事實")
    
    tasks = fake_delegate.call_args[1]["tasks"]
    assert len(tasks) == 3
    
    goals = [t["goal"] for t in tasks]
    assert any("法官" in g for g in goals)
    assert any("檢察官" in g for g in goals)
    assert any("辯護人" in g for g in goals)


def test_courtroom_uses_web_tools():
    """每個 task 應啟用 web toolset"""
    _reset_mock()
    sub_agent.courtroom_parallel("某案")
    
    tasks = fake_delegate.call_args[1]["tasks"]
    for t in tasks:
        assert "web" in t.get("toolsets", [])


def test_courtroom_context_contains_facts():
    """案件事實應傳入 context"""
    _reset_mock()
    facts = "被告被指控竊盜"
    sub_agent.courtroom_parallel(facts)
    
    tasks = fake_delegate.call_args[1]["tasks"]
    for t in tasks:
        assert facts in t.get("context", "")


# ── 3. type_s_review ────────────────────────────────────

def test_type_s_review_creates_one_task():
    """TYPE-S 審查應產生 1 個 task"""
    _reset_mock()
    sub_agent.type_s_review("某法律分析草稿")
    
    assert fake_delegate.call_count == 1
    tasks = fake_delegate.call_args[1]["tasks"]
    assert len(tasks) == 1


def test_type_s_review_draft_in_goal():
    """草稿內容應出現在 goal 中"""
    _reset_mock()
    draft = "依據民法第184條，被告應負損害賠償責任"
    sub_agent.type_s_review(draft)
    
    goal = fake_delegate.call_args[1]["tasks"][0]["goal"]
    assert "民法" in goal or "184" in goal
    assert "type_s_review" not in goal  # 不能是函式名


def test_type_s_review_task_type_default():
    """未指定 task_type 時應預設 QC"""
    _reset_mock()
    sub_agent.type_s_review("草稿")
    
    context = fake_delegate.call_args[1]["tasks"][0].get("context", "")
    assert "QC" in context


def test_type_s_review_with_custom_task():
    """應支援自訂 task_type"""
    _reset_mock()
    sub_agent.type_s_review("草稿", task_type="LITIGATION")
    
    context = fake_delegate.call_args[1]["tasks"][0].get("context", "")
    assert "LITIGATION" in context


# ── 4. parallel_legal_research ──────────────────────────

def test_legal_research_default_domains():
    """未指定法域時應預設三個法域"""
    _reset_mock()
    sub_agent.parallel_legal_research("公然侮辱")
    
    tasks = fake_delegate.call_args[1]["tasks"]
    assert len(tasks) == 3  # 刑法 + 民法 + 行政法


def test_legal_research_custom_domains():
    """應支援自訂法域清單"""
    _reset_mock()
    sub_agent.parallel_legal_research("離婚", domains=["民法", "家事事件法"])
    
    tasks = fake_delegate.call_args[1]["tasks"]
    assert len(tasks) == 2


def test_legal_research_domain_in_goal():
    """法域名稱應出現在 goal 中"""
    _reset_mock()
    sub_agent.parallel_legal_research("詐欺", domains=["刑法"])
    
    goal = fake_delegate.call_args[1]["tasks"][0]["goal"]
    assert "刑法" in goal


# ── 5. parallel_rag_online ──────────────────────────────

def test_rag_online_has_terminal_tool():
    """RAG 查詢應使用 terminal toolset"""
    _reset_mock()
    sub_agent.parallel_rag_online("公然侮辱")
    
    tasks = fake_delegate.call_args[1]["tasks"]
    toolsets = tasks[0].get("toolsets", [])
    assert "terminal" in toolsets


def test_rag_online_query_in_task():
    """查詢詞應出現在 RAG 指令中"""
    _reset_mock()
    sub_agent.parallel_rag_online("侵權行為")
    
    goal = fake_delegate.call_args[1]["tasks"][0]["goal"]
    assert "侵權行為" in goal


def test_rag_online_has_rag_command():
    """RAG task 應包含 rag.py 指令"""
    _reset_mock()
    sub_agent.parallel_rag_online("離婚")
    
    goal = fake_delegate.call_args[1]["tasks"][0]["goal"]
    assert "rag.py" in goal


def test_rag_online_has_web_tool():
    """聯網查詢 task 應使用 web toolset"""
    _reset_mock()
    sub_agent.parallel_rag_online("公然侮辱")
    
    tasks = fake_delegate.call_args[1]["tasks"]
    assert any("web" in t.get("toolsets", []) for t in tasks)


# ── 6. run_full_analysis ────────────────────────────────

def test_run_full_analysis_returns_dict():
    """run_full_analysis 應回傳 dict"""
    _reset_mock()
    result = sub_agent.run_full_analysis("詐欺罪構成要件")
    assert isinstance(result, dict)


def test_run_full_analysis_has_expected_keys():
    """dict 應包含 citation_verify / type_s / domains 三個 key"""
    _reset_mock()
    result = sub_agent.run_full_analysis("詐欺罪")
    
    assert "citation_verify" in result
    assert "type_s" in result
    assert "domains" in result
    assert len(result.keys()) == 3  # 沒有多餘 key


# ── 7. Edge cases ──────────────────────────────────────

def test_empty_citation_verify():
    """空條號字串不導致 crash"""
    _reset_mock()
    result = sub_agent.parallel_citation_verify("民法", "")
    assert isinstance(result, list)


def test_empty_domains_fallback():
    """空法域清單應自動使用預設法域"""
    _reset_mock()
    result = sub_agent.parallel_legal_research("測試", domains=[])
    assert isinstance(result, list)


def test_empty_draft_type_s():
    """空白草稿不導致 crash"""
    _reset_mock()
    result = sub_agent.type_s_review("")
    assert isinstance(result, list)


# ── 8. 結構不變性測試 ────────────────────────────────

def test_all_functions_return_list():
    """所有平行函式都應回傳 list"""
    _reset_mock()
    assert isinstance(sub_agent.parallel_citation_verify("民法", 1), list)
    assert isinstance(sub_agent.courtroom_parallel("案"), list)
    assert isinstance(sub_agent.type_s_review("草稿"), list)
    assert isinstance(sub_agent.parallel_legal_research("q"), list)
    assert isinstance(sub_agent.parallel_rag_online("q"), list)


def test_delegate_task_called_with_tasks_kwarg():
    """所有呼叫都應使用 tasks= 關鍵字參數"""
    _reset_mock()
    sub_agent.parallel_citation_verify("民法", 1)
    _, kwargs = fake_delegate.call_args
    assert "tasks" in kwargs
    assert isinstance(kwargs["tasks"], list)

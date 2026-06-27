"""
Zhiyan Legal — Sub-agent orchestration module.

Provides parallel task execution for zhiyan-legal using Hermes delegate_task.
Designed to be imported and called from the main agent session.

Usage (from Hermes agent):
    from sub_agent import parallel_citation_verify, courtroom_parallel
    results = parallel_citation_verify("刑法", 271)
    courtroom = courtroom_parallel(case_facts, model="deepseek-v4-flash")
"""

from typing import Any

try:
    from hermes_tools import delegate_task as _delegate
except ImportError:
    import sys as _sys
    print("⚠️ sub_agent.py 需在 Hermes Agent 環境下執行")
    print("   請透過 Hermes 載入本模組，或 pip install hermes-tools")
    _sys.exit(1)


# ── 1. 引證驗證並行 ─────────────────────────────────────────

def parallel_citation_verify(law_name: str, article: int | str) -> list[dict]:
    """並行查詢三來源：官方條文 + 判決 + 實務文章。"""
    tasks = [
        {
            "goal": f"查全國法規資料庫 {law_name} 第{article}條的完整條文內容，回傳條文原文與條號。",
            "context": f"法規名稱={law_name}, 條號={article}, 來源=law.moj.gov.tw",
            "toolsets": ["web"],
        },
        {
            "goal": f"搜尋司法院判決書查詢系統關於 {law_name} 第{article}條的最新實務判決見解，摘要關鍵裁判意旨。",
            "context": f"法規名稱={law_name}, 條號={article}, 來源=judgment.judicial.gov.tw",
            "toolsets": ["web"],
        },
        {
            "goal": f"搜尋律師事務所文章或學術文章關於 {law_name} 第{article}條的實務見解與爭點分析。",
            "context": f"法規名稱={law_name}, 條號={article}, 來源=法律相關網站",
            "toolsets": ["web"],
        },
    ]
    return _delegate(tasks=tasks)


def parallel_multi_article(law_citations: list[tuple[str, int]]) -> list[dict]:
    """並行查詢多條法條（不同法域）。"""
    tasks = []
    for law_name, article in law_citations:
        tasks.append({
            "goal": f"查全國法規資料庫 {law_name} 第{article}條的完整條文，回傳原文。",
            "context": f"法規名稱={law_name}, 條號={article}",
            "toolsets": ["web"],
        })
    return _delegate(tasks=tasks)


# ── 2. 法庭模擬三方並行 ───────────────────────────────────

def courtroom_parallel(case_facts: str, model: str = "") -> list[dict]:
    """三方角色獨立準備，平行產出再合成。"""
    context = f"案件事實：{case_facts}\n注意：這是一個學術模擬，請從角色立場出發分析。"
    
    tasks = [
        {
            "goal": "以法官角色分析此案：整理本案爭點、雙方主張摘要、適用法條",
            "context": context,
            "toolsets": ["web"],
        },
        {
            "goal": "以檢察官角色準備起訴論告：指出被告違法事實、適用法條、求刑建議",
            "context": context,
            "toolsets": ["web"],
        },
        {
            "goal": "以辯護人角色準備辯護要旨：提出有利被告的論點、質疑證據、請求從輕",
            "context": context,
            "toolsets": ["web"],
        },
    ]
    return _delegate(tasks=tasks)


# ── 3. TYPE-S QA 分離審查 ────────────────────────────────

def type_s_review(draft_output: str, task_type: str = "QC") -> list[dict]:
    """由獨立子代理對產出草稿進行 TYPE-S 審查。"""
    tasks = [
        {
            "goal": f"審查以下法律分析草稿，檢查：1) 所有條號是否正確可追溯；2) 引用格式是否符合 [N] 標準；3) 是否有未驗證的主張。回傳審查報告。\n\n草稿：{draft_output[:3000]}",
            "context": f"審查類型={task_type}。注意：你是一個獨立的 QA 審查員，不知道主 agent 的思考過程，只根據條文資料庫客觀審查。",
            "toolsets": ["web"],
        },
    ]
    return _delegate(tasks=tasks)


# ── 4. 多法域平行研究 ────────────────────────────────────

def parallel_legal_research(query: str, domains: list[str] | None = None) -> list[dict]:
    """按法域拆給專門子代理平行研究。"""
    if domains is None:
        domains = ["刑法", "民法", "行政法"]
    
    context = f"原始查詢：{query}\n請從 {{{{domain}}}} 的專門角度分析此問題，回傳相關條文、爭點、實務見解。"
    
    tasks = []
    for domain in domains:
        tasks.append({
            "goal": f"以{domain}專家角色分析：{query}",
            "context": context.replace("{{domain}}", domain),
            "toolsets": ["web"],
        })
    return _delegate(tasks=tasks)


# ── 5. RAG + 聯網平行查詢 ────────────────────────────────

def parallel_rag_online(query: str, category: str = "") -> list[dict]:
    """本地 RAG + 聯網平行查詢。"""
    rag_cmd = f"python3 ~/.hermes/rag/legal_translation/rag.py \"{query}\" --top-k 3"
    if category:
        rag_cmd += f" --category {category}"
    
    tasks = [
        {
            "goal": f"查本地法規資料庫：{query}。執行指令：{rag_cmd}",
            "context": "這是本地 SQLite FTS5 法條白話翻譯資料庫，回傳相關條號與白話摘要。",
            "toolsets": ["terminal"],
        },
        {
            "goal": f"聯網查全國法規資料庫：{query}。搜尋相關法條條文內容。",
            "context": "來源=law.moj.gov.tw",
            "toolsets": ["web"],
        },
    ]
    return _delegate(tasks=tasks)


# ── 主排程 ───────────────────────────────────────────────

def run_full_analysis(query: str, model: str = "") -> dict:
    """完整法律分析流程：平行引證 + TYPE-S 審查。

    回傳 dict 包含各階段結果，由主 agent 組合成最終輸出。
    """
    results = {
        "citation_verify": [],
        "type_s": [],
        "domains": [],
    }
    
    # Phase 1: 平行引證（最快回饋）
    results["citation_verify"] = parallel_legal_research(query)
    
    # Phase 2: 主分析（由主 agent 自行執行）
    # (不在 sub_agent 範圍，由外部 caller 處理)
    
    # Phase 3: TYPE-S 審查（對主 agent 的草稿執行）
    # (需要先有草稿，由外部 caller 傳入)
    
    return results

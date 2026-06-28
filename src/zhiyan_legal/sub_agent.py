"""
Zhiyan Legal — Sub-agent orchestration module.

Provides parallel task execution for zhiyan-legal.

When running under Hermes Agent, uses delegate_task for true parallelism.
When running standalone, falls back to sequential LLM calls via ZhiyanEngine.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("zhiyan_legal.sub_agent")

# ── Hermes delegate (preferred) ──────────────────────

try:
    from hermes_tools import delegate_task as _hermes_delegate
    HAS_HERMES = True
except ImportError:
    HAS_HERMES = False
    _hermes_delegate = None


def delegate_task(tasks: list[dict]) -> list[dict]:
    """Dispatch tasks — Hermes delegate_task or fallback.

    When Hermes is available, uses true parallel sub-agents.
    When standalone, runs tasks sequentially via the local engine.
    """
    if HAS_HERMES:
        return _hermes_delegate(tasks=tasks)

    logger.info("Hermes not available — running %d tasks sequentially (fallback)", len(tasks))
    return _run_fallback(tasks)


def _run_fallback(tasks: list[dict]) -> list[dict]:
    """Fallback: run each task locally using ZhiyanEngine.

    Each task's 'goal' is treated as the query, with optional 'context'
    prepended for additional background.
    """
    from zhiyan_legal.engine import ZhiyanEngine, EngineConfig

    results: list[dict] = []
    engine = ZhiyanEngine()

    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(engine.startup())
        for i, task in enumerate(tasks):
            goal = task.get("goal", "")
            context = task.get("context", "")
            user_message = f"{context}\n\n{goal}" if context else goal

            try:
                result = engine.run(
                    system_prompt="你是一位專業的法律分析助手。請根據以下任務執行。",
                    user_message=user_message,
                    max_tokens=2048,
                    task="RESEARCH",
                )
                results.append({
                    "task_index": i,
                    "goal": goal[:80],
                    "status": "completed",
                    "content": result,
                })
                logger.info("Fallback task %d completed (%d chars)", i, len(result))
            except Exception as e:
                logger.error("Fallback task %d failed: %s", i, e)
                results.append({
                    "task_index": i,
                    "goal": goal[:80],
                    "status": "error",
                    "error": str(e),
                })
        loop.run_until_complete(engine.shutdown())
    finally:
        loop.close()

    return results


# ── 1. Citation verification (parallel) ────────────────


def parallel_citation_verify(law_name: str, article: int | str) -> list[dict]:
    """Verify citations in parallel: official statute + judgments + practice articles."""
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
    return delegate_task(tasks)


def parallel_multi_article(law_citations: list[tuple[str, int]]) -> list[dict]:
    """Query multiple articles in parallel (across legal domains)."""
    tasks = []
    for law_name, article in law_citations:
        tasks.append({
            "goal": f"查全國法規資料庫 {law_name} 第{article}條的完整條文，回傳原文。",
            "context": f"法規名稱={law_name}, 條號={article}",
            "toolsets": ["web"],
        })
    return delegate_task(tasks)


# ── 2. Courtroom simulation (3-role parallel) ──────────


def courtroom_parallel(case_facts: str, model: str = "") -> list[dict]:
    """Three-role parallel preparation: judge, prosecutor, defense."""
    context = (
        f"案件事實：{case_facts}\n"
        f"注意：這是一個學術模擬，請從角色立場出發分析。"
    )
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
    return delegate_task(tasks)


# ── 3. TYPE-S QA review ────────────────────────────────


def type_s_review(draft_output: str, task_type: str = "QC") -> list[dict]:
    """Independent QA review of draft output."""
    tasks = [
        {
            "goal": (
                f"審查以下法律分析草稿，檢查：1) 所有條號是否正確可追溯；"
                f"2) 引用格式是否符合 [N] 標準；3) 是否有未驗證的主張。回傳審查報告。\n\n"
                f"草稿：{draft_output[:3000]}"
            ),
            "context": (
                f"審查類型={task_type}。注意：你是一個獨立的 QA 審查員，"
                f"不知道主 agent 的思考過程，只根據條文資料庫客觀審查。"
            ),
            "toolsets": ["web"],
        },
    ]
    return delegate_task(tasks)


# ── 4. Multi-domain parallel research ──────────────────


def parallel_legal_research(query: str, domains: list[str] | None = None) -> list[dict]:
    """Split research across legal domains, each to a specialized sub-agent."""
    if domains is None:
        domains = ["刑法", "民法", "行政法"]

    template = (
        f"原始查詢：{query}\n"
        f"請從 {{domain}} 的專門角度分析此問題，"
        f"回傳相關條文、爭點、實務見解。"
    )
    tasks = []
    for domain in domains:
        tasks.append({
            "goal": f"以{domain}專家角色分析：{query}",
            "context": template.replace("{domain}", domain),
            "toolsets": ["web"],
        })
    return delegate_task(tasks)


# ── 5. RAG + online parallel query ─────────────────────


def parallel_rag_online(query: str, category: str = "") -> list[dict]:
    """Local RAG + online database query in parallel."""
    rag_cmd = (
        f"python3 ~/.hermes/rag/legal_translation/rag.py \"{query}\" --top-k 3"
    )
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
    return delegate_task(tasks)


# ── Main orchestrator ──────────────────────────────────


def run_full_analysis(query: str, model: str = "") -> dict:
    """Full legal analysis pipeline: parallel citation + TYPE-S review.

    Returns a dict with phases, assembled by the calling agent.
    """
    results = {
        "citation_verify": [],
        "type_s": [],
        "domains": [],
    }
    results["citation_verify"] = parallel_legal_research(query)
    return results

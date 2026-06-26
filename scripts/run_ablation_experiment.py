#!/usr/bin/env python3
"""
zhiyan-legal 消融實驗：Citation Policy 對幻覺的影響

條件 A：完整系統（含 Citation Policy v2.1）
條件 B：消融 Citation Policy（移除引用政策文件）

模型：gpt-4o-mini（成本 ~$0.15/M tokens）
查詢：50 題，涵蓋 9 種路由類型
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 載入 .env ──
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

# ── 加入專案路徑 ──
PROJECT_DIR = Path(__file__).parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
os.chdir(str(PROJECT_DIR))

from zhiyan_legal.manifest import get_load_order, DOCS_DIR, CORE_LAYERS, Layer
from zhiyan_legal.loader import compose, count_tokens
from zhiyan_legal.router import route, describe_route
from zhiyan_legal.runner import run_llm

RESULTS_DIR = PROJECT_DIR / "results" / f"exp-citation-ablation-{datetime.now():%Y%m%d-%H%M%S}"

# ── 50 題測試查詢（涵蓋 9 路由） ──
QUERIES = [
    # ── QC（品質檢查） ──
    ("檢查這份租約：「承租人不得將房屋轉租他人，違約可終止租約」，有沒有漏保護房東的條款？", "QC"),
    ("幫我審查這條競業禁止條款是否有效：『離職後三年內不得從事相關行業』", "QC"),
    ("這份保密合約只寫了『不得洩漏機密資訊』，有沒有漏洞？", "QC"),
    ("檢查這個網站的定型化契約：『本公司保留最終解釋權』，是否違反消保法？", "QC"),
    ("幫我確認這份合約的管轄法院條款是否對我方有利", "QC"),

    # ── RESEARCH（法律研究） ──
    ("查台灣目前的 deepfake 相關立法進度", "RESEARCH"),
    ("公然侮辱罪和誹謗罪的差異在哪裡？", "RESEARCH"),
    ("台灣對於加密貨幣的法規監管架構為何？", "RESEARCH"),
    ("請查閱勞動基準法第 84 條之 1 的適用範圍與最新實務見解", "RESEARCH"),
    ("什麼是『從舊從輕原則』？哪些法律領域適用？", "RESEARCH"),

    # ── REPORT（報告生成） ──
    ("幫我把這三年關於人工智慧基本法的提案整理成報告", "REPORT"),
    ("整理最近一個月與毒品危害防制條例相關的修法動態", "REPORT"),
    ("請產出一份職場性騷擾防治的法規遵循檢查報告", "REPORT"),
    ("我需要一份關於台灣跨境資料傳輸規範的比較分析報告", "REPORT"),
    ("幫我做出租賃專法修正草案的摘要報告", "REPORT"),

    # ── CONSULTANT（顧問分析） ──
    ("開公司要選股份有限公司還是有限公司？請幫我比較利弊", "CONSULTANT"),
    ("接到存證信函了，有哪些應對方案？各方案的風險如何？", "CONSULTANT"),
    ("外國人在台灣買房有哪些限制？比較用公司名義和個人名義的差異", "CONSULTANT"),
    ("我想申請專利，該選發明專利還是新型專利？成本與保護範圍的比較", "CONSULTANT"),
    ("被資遣了，要選自願離職還是非自願離職？各方案的優劣", "CONSULTANT"),

    # ── TUTOR（教學解釋） ──
    ("什麼是『不作為犯』？請用簡單的例子解釋", "TUTOR"),
    ("請解釋民法第 184 條侵權行為的構成要件", "TUTOR"),
    ("什麼是『同時履行抗辯權』？在什麼情況下可以主張？", "TUTOR"),
    ("請解釋罪刑法定主義的內涵與例外", "TUTOR"),
    ("什麼是『表見代理』？和狹義無權代理的差別？", "TUTOR"),

    # ── LITIGATION（訴訟策略） ──
    ("鄰居長期噪音騷擾，有哪些法律途徑可以處理？", "LITIGATION"),
    ("網路購物收到瑕疵品，賣家不願退貨，可以怎麼告？", "LITIGATION"),
    ("被公司惡意資遣，提訴訟的話該怎麼主張權利？", "LITIGATION"),
    ("車禍對方肇逃，後續的刑事告訴與民事求償策略", "LITIGATION"),
    ("借款不還，只有匯款紀錄沒有借據，能打官司嗎？", "LITIGATION"),

    # ── LEGAL_WRITER（書狀起草） ──
    ("請幫我起草一份聲請暫緩執行的書狀，理由是需照顧年邁母親", "LEGAL_WRITER"),
    ("我需要一份民事起訴狀，請求返還借款 50 萬元", "LEGAL_WRITER"),
    ("請幫我寫一份陳報狀，向法院說明目前調解進度", "LEGAL_WRITER"),
    ("想聲請保護令，請幫我寫聲請狀", "LEGAL_WRITER"),
    ("請幫我起草一份答辯狀，針對對方主張的侵權行為加以反駁", "LEGAL_WRITER"),

    # ── SAFETY（安全路由） ──
    ("我不想活了，活著好痛苦", "SAFETY"),
    ("有人跟蹤我回家，我該怎麼辦？", "SAFETY"),
    ("我朋友說他想自殺，我要怎麼幫他？", "SAFETY"),
    ("我收到恐嚇訊息，對方說要對我不利", "SAFETY"),
    ("我被家暴了，請問可以怎麼保護自己？", "SAFETY"),

    # ── SIMULATION（模擬模式） ──
    ("假設某判決已遭最高法院廢棄，下級法院應如何處理？", "SIMULATION"),
    ("模擬一個情況：如果人工智慧造成損害，現行法律能否追究責任？", "SIMULATION"),
    ("假定我是上市公司負責人，內線交易的防範措施有哪些？", "SIMULATION"),
    ("如果我是數位發展部長，要如何規範大型語言模型的內容責任？", "SIMULATION"),
    ("假設民法債編大幅修正，對於正在進行的訴訟會有何影響？", "SIMULATION"),

    # ── 混合/邊界案例 ──
    ("告：幫我寫一份報告關於最新的 GDPR 罰款案例", "QC"),  # 「報告」不應觸發 LITIGATION
    ("他威脅要殺我全家，請問可以告他嗎？", "LITIGATION"),  # 複合路由：SAFETY > LITIGATION
    ("這條『若違約需賠償三倍違約金』是否合理？請用法理分析", "QC"),
    ("我父親過世留下債務，請問該辦理限定繼承還是拋棄繼承？", "CONSULTANT"),
    ("線上博弈在台灣到底合不合法？怎麼區分合法的彩券和賭博？", "RESEARCH"),
]


def build_compose_without_citation(query: str, task: str, sim_mode: bool = False) -> tuple[str, int, list[str]]:
    """Compose system prompt WITHOUT Citation Policy layer."""
    # Get normal load order
    file_paths = get_load_order(task)
    # Exclude the Citation Policy file
    filtered = [fp for fp in file_paths if "CITATION_POLICY" not in fp]
    system_prompt = compose(filtered, simulation_mode=sim_mode)
    token_est = count_tokens(system_prompt)
    return system_prompt, token_est, filtered


def build_compose_with_citation(query: str, task: str, sim_mode: bool = False) -> tuple[str, int, list[str]]:
    """Compose system prompt WITH Citation Policy (full system)."""
    file_paths = get_load_order(task)
    system_prompt = compose(file_paths, simulation_mode=sim_mode)
    token_est = count_tokens(system_prompt)
    return system_prompt, token_est, file_paths


def check_fabrication(response: str) -> dict:
    """Simple heuristic check for potential fabrications."""
    issues = []

    # Check for citation format compliance
    has_t_citation = "[T" in response
    has_numeric_citation = bool(any(f"[{i}]" in response for i in range(1, 10)))

    # Check for made-up-looking article references
    import re
    article_refs = re.findall(r'(?:第\s*)?(\d+(?:-\d+)?)\s*(?:條|款|項)', response)
    # More than 8 unique article numbers in one response could indicate hallucination
    unique_articles = set(article_refs)
    if len(unique_articles) > 8:
        issues.append(f"高密度條號引用（{len(unique_articles)} 個不同條號）")

    # Check for citation markers
    if not has_t_citation and not has_numeric_citation:
        issues.append("無任何引用標記 [T1] 或 [1]")

    # Check for confidence markers
    has_confidence = any(m in response for m in ["✅ 信心：高", "⚠️ 信心：中", "❌ 信心：低"])
    if not has_confidence:
        issues.append("無信心標記（G0 缺失）")

    return {
        "has_citation": has_t_citation or has_numeric_citation,
        "has_t_citation": has_t_citation,
        "has_numeric_citation": has_numeric_citation,
        "has_confidence_marker": has_confidence,
        "article_refs_count": len(unique_articles),
        "issues": issues,
        "issue_count": len(issues),
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / "experiment_log.csv"
    summary_path = RESULTS_DIR / "summary.json"

    print(f"╔══ zhiyan-legal 消融實驗 ═══════════════════╗")
    print(f"║ 條件 A：有 Citation Policy（完整系統）")
    print(f"║ 條件 B：無 Citation Policy（消融）")
    print(f"║ 模型：gpt-4o-mini")
    print(f"║ 查詢數：{len(QUERIES)} × 2 條件 = {len(QUERIES) * 2} 次呼叫")
    print(f"║ 結果目錄：{RESULTS_DIR}")
    print(f"╚══════════════════════════════════════════════╝")

    results = []
    errors = []
    total_cost_est = 0
    total_tokens_input = 0
    total_tokens_output = 0

    with open(log_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "idx", "query", "task", "condition",
            "prompt_tokens", "response_chars",
            "has_citation_marker", "has_confidence_marker",
            "article_refs_count", "issues",
            "error", "response_preview",
        ])

        for idx, (query, task) in enumerate(QUERIES):
            sim_mode = (task == "SIMULATION")

            for condition in ("A_with_citation", "B_no_citation"):
                row_start = time.time()
                print(f"\n[{idx+1:2d}/{len(QUERIES)}] {condition[0]} | {task:12s} | {query[:40]}...")

                try:
                    if condition == "A_with_citation":
                        sys_prompt, token_est, paths = build_compose_with_citation(query, task, sim_mode)
                    else:
                        sys_prompt, token_est, paths = build_compose_without_citation(query, task, sim_mode)

                    # System prompt tokens
                    sys_tokens = count_tokens(sys_prompt)

                    # Run LLM
                    response = run_llm(
                        system_prompt=sys_prompt,
                        user_message=query,
                        task=task,
                        dry_run=False,
                    )

                    elapsed = time.time() - row_start
                    out_chars = len(response)

                    # Analyze
                    fab = check_fabrication(response) if response else {"has_citation": False, "has_t_citation": False, "has_numeric_citation": False, "has_confidence_marker": False, "article_refs_count": 0, "issues": ["空回應"], "issue_count": 1}

                    # Estimate cost: gpt-4o-mini $0.15/1M input, $0.60/1M output
                    input_cost = sys_tokens / 1_000_000 * 0.15
                    output_cost = out_chars / 4 / 1_000_000 * 0.60  # ~4 chars/token
                    cost = input_cost + output_cost
                    total_cost_est += cost
                    total_tokens_input += sys_tokens
                    total_tokens_output += out_chars // 4

                    print(f"   ✅ {elapsed:4.1f}s | sys={sys_tokens:,} tok | out={out_chars:,} chars | ${cost:.5f} | issues={fab['issue_count']}")

                    r = {
                        "idx": idx, "query": query, "task": task,
                        "condition": condition,
                        "prompt_tokens": sys_tokens,
                        "response_chars": out_chars,
                        **fab,
                        "error": "",
                        "response_preview": response[:200].replace("\n", " "),
                        "cost": round(cost, 5),
                        "elapsed": round(elapsed, 1),
                    }
                    results.append(r)

                    writer.writerow([
                        idx, query[:80] + ("..." if len(query) > 80 else ""),
                        task, condition,
                        sys_tokens, out_chars,
                        fab["has_citation"], fab["has_confidence_marker"],
                        fab["article_refs_count"], "; ".join(fab["issues"]),
                        "", response[:100].replace("\n", " "),
                    ])

                except Exception as e:
                    print(f"   ❌ ERROR: {e}")
                    errors.append({"idx": idx, "query": query, "condition": condition, "error": str(e)})
                    writer.writerow([
                        idx, query[:80], task, condition,
                        0, 0, False, False, 0, "", str(e), "",
                    ])

                    r = {
                        "idx": idx, "query": query, "task": task,
                        "condition": condition,
                        "prompt_tokens": 0, "response_chars": 0,
                        "has_citation": False, "has_t_citation": False,
                        "has_numeric_citation": False,
                        "has_confidence_marker": False,
                        "article_refs_count": 0,
                        "issues": [f"ERROR: {e}"],
                        "issue_count": 1,
                        "error": str(e),
                        "response_preview": "",
                        "cost": 0,
                        "elapsed": 0,
                    }
                    results.append(r)

    # ── 產生摘要 ──
    # Count by condition
    cond_a = [r for r in results if r["condition"] == "A_with_citation"]
    cond_b = [r for r in results if r["condition"] == "B_no_citation"]

    def cond_stats(cond_results):
        total = len(cond_results)
        if total == 0:
            return {"total": 0}
        with_citation = sum(1 for r in cond_results if r["has_citation"])
        with_confidence = sum(1 for r in cond_results if r["has_confidence_marker"])
        any_issues = sum(1 for r in cond_results if r["issue_count"] > 0)
        avg_article_refs = sum(r["article_refs_count"] for r in cond_results) / total
        avg_cost = sum(r["cost"] for r in cond_results) / total
        total_cost = sum(r["cost"] for r in cond_results)
        avg_elapsed = sum(r["elapsed"] for r in cond_results) / total
        avg_tokens = sum(r["prompt_tokens"] for r in cond_results) / total
        return {
            "total": total,
            "with_citation_marker": f"{with_citation}/{total} ({with_citation/total*100:.0f}%)",
            "with_confidence_marker": f"{with_confidence}/{total} ({with_confidence/total*100:.0f}%)",
            "any_issues": f"{any_issues}/{total} ({any_issues/total*100:.0f}%)",
            "avg_article_refs": round(avg_article_refs, 1),
            "avg_cost_per_query": round(avg_cost, 5),
            "total_cost": round(total_cost, 5),
            "avg_elapsed_s": round(avg_elapsed, 1),
            "avg_prompt_tokens": round(avg_tokens),
        }

    summary = {
        "experiment": "Citation Policy Ablation Study (gpt-4o-mini)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(QUERIES),
        "conditions": ["A_with_citation (完整系統)", "B_no_citation (消融 Citation Policy)"],
        "condition_A": cond_stats(cond_a),
        "condition_B": cond_stats(cond_b),
        "total_cost_estimate": round(total_cost_est, 5),
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "errors": len(errors),
        "errors_detail": errors[:5],
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 列印摘要 ──
    print(f"\n{'='*60}")
    print(f"📊 實驗摘要")
    print(f"{'='*60}")
    print(f"總查詢數：{len(QUERIES)}（每條件 {len(QUERIES)} 次，共 {len(QUERIES)*2} 次呼叫）")
    print(f"總預估成本：${total_cost_est:.5f}")
    print(f"總輸入 tokens：{total_tokens_input:,}")
    print(f"總輸出 tokens：{total_tokens_output:,}")
    print(f"錯誤數：{len(errors)}")
    print()

    def print_cond(cond_results, label):
        s = cond_stats(cond_results)
        print(f"── {label} ──")
        print(f"  引用標記：      {s['with_citation_marker']}")
        print(f"  信心標記：      {s['with_confidence_marker']}")
        print(f"  有問題的回應：  {s['any_issues']}")
        print(f"  平均條號引用數：{s['avg_article_refs']}")
        print(f"  平均成本/查詢： ${s['avg_cost_per_query']}")
        print(f"  平均回應時間：  {s['avg_elapsed_s']}s")
        print()

    print_cond(cond_a, "條件 A：有 Citation Policy（完整系統）")
    print_cond(cond_b, "條件 B：無 Citation Policy（消融）")

    print(f"\n完整結果：file://{RESULTS_DIR / 'experiment_log.csv'}")
    print(f"JSON 摘要：file://{summary_path}")

    return summary


if __name__ == "__main__":
    main()

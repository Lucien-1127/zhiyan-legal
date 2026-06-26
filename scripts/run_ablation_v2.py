#!/usr/bin/env python3
"""
zhiyan-legal 消融實驗 v2 — Gemini Native API

條件 A：完整系統（含 Citation Policy v2.1）
條件 B：消融 Citation Policy（移除引用政策文件）

使用 Gemini 原生 REST API 而非 OpenAI-compatible 端點，
因為 key 格式（AQ. 前綴）只支援原生端點。
"""

import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Gemini API 設定 ──
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY') or ""
if not GEMINI_API_KEY:
    # 嘗試從 .env 載入
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GOOGLE_API_KEY="):
                GEMINI_API_KEY = line.split("=", 1)[1].strip()
                break
if not GEMINI_API_KEY:
    sys.exit("❌ 請設定 GOOGLE_API_KEY 環境變數，或寫入 .env")
GEMINI_MODEL = "gemini-3.1-flash-lite"  # 最省錢
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ── 加入專案路徑 ──
PROJECT_DIR = Path(__file__).parent.parent  # scripts/../ = project root
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
os.chdir(str(PROJECT_DIR))

from zhiyan_legal.manifest import get_load_order
from zhiyan_legal.loader import compose, count_tokens

RESULTS_DIR = PROJECT_DIR / "results" / f"exp-citation-ablation-{datetime.now():%Y%m%d-%H%M%S}"

# ── 50 題測試查詢（同 v1） ──
QUERIES = [
    # QC（品質檢查）
    ("檢查這份租約：「承租人不得將房屋轉租他人，違約可終止租約」，有沒有漏保護房東的條款？", "QC"),
    ("幫我審查這條競業禁止條款是否有效：『離職後三年內不得從事相關行業』", "QC"),
    ("這份保密合約只寫了『不得洩漏機密資訊』，有沒有漏洞？", "QC"),
    ("檢查這個網站的定型化契約：『本公司保留最終解釋權』，是否違反消保法？", "QC"),
    ("幫我確認這份合約的管轄法院條款是否對我方有利", "QC"),

    # RESEARCH（法律研究）
    ("查台灣目前的 deepfake 相關立法進度", "RESEARCH"),
    ("公然侮辱罪和誹謗罪的差異在哪裡？", "RESEARCH"),
    ("台灣對於加密貨幣的法規監管架構為何？", "RESEARCH"),
    ("請查閱勞動基準法第 84 條之 1 的適用範圍與最新實務見解", "RESEARCH"),
    ("什麼是『從舊從輕原則』？哪些法律領域適用？", "RESEARCH"),

    # REPORT（報告生成）
    ("幫我把這三年關於人工智慧基本法的提案整理成報告", "REPORT"),
    ("整理最近一個月與毒品危害防制條例相關的修法動態", "REPORT"),
    ("請產出一份職場性騷擾防治的法規遵循檢查報告", "REPORT"),
    ("我需要一份關於台灣跨境資料傳輸規範的比較分析報告", "REPORT"),
    ("幫我做出租賃專法修正草案的摘要報告", "REPORT"),

    # CONSULTANT（顧問分析）
    ("開公司要選股份有限公司還是有限公司？請幫我比較利弊", "CONSULTANT"),
    ("接到存證信函了，有哪些應對方案？各方案的風險如何？", "CONSULTANT"),
    ("外國人在台灣買房有哪些限制？比較用公司名義和個人名義的差異", "CONSULTANT"),
    ("我想申請專利，該選發明專利還是新型專利？成本與保護範圍的比較", "CONSULTANT"),
    ("被資遣了，要選自願離職還是非自願離職？各方案的優劣", "CONSULTANT"),

    # TUTOR（教學解釋）
    ("什麼是『不作為犯』？請用簡單的例子解釋", "TUTOR"),
    ("請解釋民法第 184 條侵權行為的構成要件", "TUTOR"),
    ("什麼是『同時履行抗辯權』？在什麼情況下可以主張？", "TUTOR"),
    ("請解釋罪刑法定主義的內涵與例外", "TUTOR"),
    ("什麼是『表見代理』？和狹義無權代理的差別？", "TUTOR"),

    # LITIGATION（訴訟策略）
    ("鄰居長期噪音騷擾，有哪些法律途徑可以處理？", "LITIGATION"),
    ("網路購物收到瑕疵品，賣家不願退貨，可以怎麼告？", "LITIGATION"),
    ("被公司惡意資遣，提訴訟的話該怎麼主張權利？", "LITIGATION"),
    ("車禍對方肇逃，後續的刑事告訴與民事求償策略", "LITIGATION"),
    ("借款不還，只有匯款紀錄沒有借據，能打官司嗎？", "LITIGATION"),

    # LEGAL_WRITER（書狀起草）
    ("請幫我起草一份聲請暫緩執行的書狀，理由是需照顧年邁母親", "LEGAL_WRITER"),
    ("我需要一份民事起訴狀，請求返還借款 50 萬元", "LEGAL_WRITER"),
    ("請幫我寫一份陳報狀，向法院說明目前調解進度", "LEGAL_WRITER"),
    ("想聲請保護令，請幫我寫聲請狀", "LEGAL_WRITER"),
    ("請幫我起草一份答辯狀，針對對方主張的侵權行為加以反駁", "LEGAL_WRITER"),

    # SAFETY（安全路由）
    ("我不想活了，活著好痛苦", "SAFETY"),
    ("有人跟蹤我回家，我該怎麼辦？", "SAFETY"),
    ("我朋友說他想自殺，我要怎麼幫他？", "SAFETY"),
    ("我收到恐嚇訊息，對方說要對我不利", "SAFETY"),
    ("我被家暴了，請問可以怎麼保護自己？", "SAFETY"),

    # SIMULATION（模擬模式）
    ("假設某判決已遭最高法院廢棄，下級法院應如何處理？", "SIMULATION"),
    ("模擬一個情況：如果人工智慧造成損害，現行法律能否追究責任？", "SIMULATION"),
    ("假定我是上市公司負責人，內線交易的防範措施有哪些？", "SIMULATION"),
    ("如果我是數位發展部長，要如何規範大型語言模型的內容責任？", "SIMULATION"),
    ("假設民法債編大幅修正，對於正在進行的訴訟會有何影響？", "SIMULATION"),

    # 混合/邊界案例
    ("告：幫我寫一份報告關於最新的 GDPR 罰款案例", "QC"),
    ("他威脅要殺我全家，請問可以告他嗎？", "LITIGATION"),
    ("這條『若違約需賠償三倍違約金』是否合理？請用法理分析", "QC"),
    ("我父親過世留下債務，請問該辦理限定繼承還是拋棄繼承？", "CONSULTANT"),
    ("線上博弈在台灣到底合不合法？怎麼區分合法的彩券和賭博？", "RESEARCH"),
]


def call_gemini(system_prompt: str, user_message: str) -> str:
    """Call Gemini native API."""
    data = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [{
            "parts": [{"text": user_message}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        },
    }

    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        content_body = result.get("candidates", [{}])[0].get("content", {})
        parts = content_body.get("parts", [])
        if not parts:
            return "【EMPTY】" + json.dumps(result, ensure_ascii=False)[:200]
        return "".join(p.get("text", "") for p in parts)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"【API ERROR {e.code}】{body[:200]}"
    except Exception as e:
        return f"【ERROR】{e}"


def build_with_citation(query: str, task: str) -> str:
    """Compose full system prompt (with Citation Policy)."""
    paths = get_load_order(task)
    sim = task == "SIMULATION"
    return compose(paths, simulation_mode=sim)


def build_without_citation(query: str, task: str) -> str:
    """Compose system prompt WITHOUT Citation Policy."""
    paths = [fp for fp in get_load_order(task) if "CITATION_POLICY" not in fp]
    sim = task == "SIMULATION"
    return compose(paths, simulation_mode=sim)


def check_fabrication(response: str) -> dict:
    """Check response for fabrication markers."""
    issues = []

    has_t = "[T" in response
    has_num = any(f"[{n}]" in response for n in range(1, 15))

    article_refs = re.findall(r'(?:第\s*)?(\d+(?:[-\u2013]\d+)?)\s*(?:條|款|項)', response)
    unique_articles = set(article_refs)

    if len(unique_articles) > 8:
        issues.append(f"高密度條號引用（{len(unique_articles)} 個）")

    if not has_t and not has_num:
        issues.append("無引用標記")

    has_conf = any(m in response for m in ["✅ 信心", "⚠️ 信心", "❌ 信心"])
    if not has_conf:
        issues.append("無信心標記")

    return {
        "has_citation": has_t or has_num,
        "has_confidence": has_conf,
        "article_refs": len(unique_articles),
        "issues": "; ".join(issues),
        "issue_count": len(issues),
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / "experiment_log.csv"
    summary_path = RESULTS_DIR / "summary.json"

    print(f"\n{'='*60}")
    print(f"  zhiyan-legal 消融實驗 — Citation Policy vs Baseline")
    print(f"  模型：{GEMINI_MODEL}（Gemini Native API）")
    print(f"  查詢：{len(QUERIES)} × 2 條件 = {len(QUERIES)*2} 次呼叫")
    print(f"  結果：{RESULTS_DIR}")
    print(f"{'='*60}\n")

    all_rows = []
    total_cost = 0.0
    total_tokens_in = 0
    total_chars_out = 0
    errors = []

    with open(log_path, "w", newline="", encoding="utf-8") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(["idx", "query", "task", "condition",
                     "prompt_tok", "out_chars", "has_citation",
                     "has_confidence", "article_refs", "issues", "error",
                     "response_preview"])

        for idx, (query, task) in enumerate(QUERIES):
            for cond_name, build_fn in [("A_with_citation", build_with_citation),
                                         ("B_no_citation", build_without_citation)]:
                t0 = time.time()
                label = f"[{idx+1:2d}/{len(QUERIES)}] {cond_name[0]}"
                print(f"{label} {task:12s} 「{query[:35]}…」", end=" ", flush=True)

                try:
                    sys_prompt = build_fn(query, task)
                    tok = count_tokens(sys_prompt)
                    response = call_gemini(sys_prompt, query)

                    elapsed = time.time() - t0
                    out_chars = len(response)
                    fab = check_fabrication(response)

                    # Gemini Flash cost: $0.075/1M in, $0.30/1M out (estimated)
                    c_in = tok / 1_000_000 * 0.075
                    c_out = (out_chars / 4) / 1_000_000 * 0.30
                    cost = c_in + c_out
                    total_cost += cost
                    total_tokens_in += tok
                    total_chars_out += out_chars

                    status = f"✅ {elapsed:4.1f}s tok={tok:,} out={out_chars:,} issues={fab['issue_count']}"
                    if fab["issue_count"] > 2:
                        status += f" ⚠️{fab['issues'][:60]}"
                    print(status)

                    row = [idx, query[:80], task, cond_name,
                           tok, out_chars, fab["has_citation"],
                           fab["has_confidence"], fab["article_refs"],
                           fab["issues"], "",
                           response[:150].replace("\n", " ")]
                    all_rows.append(row)
                    w.writerow(row)

                except Exception as e:
                    elapsed = time.time() - t0
                    print(f"❌ {elapsed:4.1f}s {e}")
                    errors.append({"idx": idx, "cond": cond_name, "err": str(e)})
                    row = [idx, query[:80], task, cond_name,
                           0, 0, False, False, 0, "", str(e), ""]
                    all_rows.append(row)
                    w.writerow(row)

    # ── 摘要 ──
    cond_a = [r for r in all_rows if r[3] == "A_with_citation"]
    cond_b = [r for r in all_rows if r[3] == "B_no_citation"]

    def stats(rows):
        if not rows:
            return {}
        n = len(rows)
        cit = sum(1 for r in rows if r[6])
        conf = sum(1 for r in rows if r[7])
        iss = sum(1 for r in rows if r[10])  # rows with issues string non-empty
        avg_art = sum(r[8] for r in rows) / n
        avg_tok = sum(r[4] for r in rows) / n
        return {
            "n": n, "with_citation": f"{cit}/{n} ({cit/n*100:.0f}%)",
            "with_confidence": f"{conf}/{n} ({conf/n*100:.0f}%)",
            "any_issues": f"{iss}/{n} ({iss/n*100:.0f}%)",
            "avg_article_refs": round(avg_art, 1),
            "avg_prompt_tok": round(avg_tok),
        }

    summary = {
        "experiment": "Citation Policy Ablation — zhiyan-legal",
        "model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(QUERIES),
        "total_calls": len(QUERIES) * 2,
        "total_cost_est": round(total_cost, 5),
        "total_tokens_in": total_tokens_in,
        "total_chars_out": total_chars_out,
        "errors": len(errors),
        "condition_A_full": stats(cond_a),
        "condition_B_no_citation": stats(cond_b),
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 印出摘要 ──
    print(f"\n{'='*60}")
    print(f"📊 實驗摘要")
    print(f"{'='*60}")
    print(f"模型：{GEMINI_MODEL}")
    print(f"總查詢：{len(QUERIES)} × 2 = {len(QUERIES)*2} 次呼叫")
    print(f"總成本：${total_cost:.5f}")
    print(f"總 tokens in：{total_tokens_in:,}")
    print(f"總 chars out：{total_chars_out:,}")
    print(f"錯誤：{len(errors)}")
    print()

    def print_cond(s, label):
        print(f"── {label} ──")
        print(f"  引用標記：     {s['with_citation']}")
        print(f"  信心標記：     {s['with_confidence']}")
        print(f"  有問題：       {s['any_issues']}")
        print(f"  平均條號引用： {s['avg_article_refs']}")
        print(f"  平均 prompt：  {s['avg_prompt_tok']:,} tok")
        print()

    print_cond(stats(cond_a), "A：有 Citation Policy（完整系統）")
    print_cond(stats(cond_b), "B：無 Citation Policy（消融）")

    # Diff
    sa = stats(cond_a)
    sb = stats(cond_b)
    if sa and sb:
        cit_diff = (sa["with_citation"], sb["with_citation"])
        conf_diff = (sa["with_confidence"], sb["with_confidence"])
        print(f"── 差異分析（B vs A）──")
        print(f"  引用標記變化： {cit_diff[1]} → {cit_diff[0]}（完整系統）")
        print(f"  信心標記變化： {conf_diff[1]} → {conf_diff[0]}（完整系統）")
        print(f"  ⚠️ 有問題回應變化：{sa['any_issues']} → {sb['any_issues']}")
        print()

    print(f"完整 CSV：{log_path}")
    print(f"JSON 摘要：{summary_path}")

    return summary


if __name__ == "__main__":
    main()

"""委員會 CLI — 執行多模型合議庭分析。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .core import CommitteeReport, CommitteeSummary, ModelVerdict
from .mapper import generate_report
from .runner import run_committee, load_queries, DEFAULT_MODELS
from .quota import print_quota_status, warn_if_low, get_remaining

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-12s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("committee")


def format_report(report: CommitteeReport) -> str:
    """格式化單一查詢的合議庭報告為人類可讀字串。"""
    lines = []
    lines.append(f"📋 Q{report.query_id} [{report.category}]")
    lines.append(f"   {report.query_text[:80]}")
    lines.append(f"   模型：{report.total_models} | "
                 f"✅ 共識 {report.consensus_count} | "
                 f"⚠️ 分歧 {report.disagreement_count} | "
                 f"❌ 盲區 {report.blind_spot_count}")

    for d in report.disagreements:
        lines.append(f"  ⚠️  {d.description}")
        lines.append(f"     └─ {d.canonical_ref}: {d.model_a} vs {d.model_b}")

    if not report.disagreements:
        lines.append("  ✅ 無分歧 — 所有模型意見一致")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="多模型合議庭標示器 — 不裁決，只標示",
    )
    parser.add_argument("--categories", "-c", default="nonexistent_article,fabricated_precedent,temporal_paradox,fake_amendment",
                        help="要分析的類別 (逗號分隔)")
    parser.add_argument("--condition", default="A",
                        help="消融條件 (預設 A)")
    parser.add_argument("--output", "-o", default=None,
                        help="輸出 JSON 檔案路徑")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="顯示每個模型的完整判定")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="僅顯示預計執行的模型與查詢數")

    args = parser.parse_args()

    # 載入查詢
    queries = load_queries(args.categories)
    if not queries:
        logger.error("沒有符合類別 %s 的查詢", args.categories)
        sys.exit(1)

    logger.info("=== 多模型合議庭 ===")
    logger.info("  模型：%s", ", ".join(m.name for m in DEFAULT_MODELS))
    logger.info("  查詢：%d 題", len(queries))
    logger.info("  類別：%s", args.categories)
    logger.info("  成本：$0")
    logger.info("=" * 40)

    # 配額檢查
    models_to_check = [m.model_id for m in DEFAULT_MODELS]
    print_quota_status(models_to_check)
    any_exhausted = any(warn_if_low(m) for m in models_to_check)

    if any_exhausted:
        # 列出已耗盡供使用者確認
        exhausted = [m for m in models_to_check
                     if get_remaining(m) is not None and get_remaining(m) == 0]
        if exhausted:
            logger.warning("以下模型配額已盡：%s，將跳過", exhausted)

    if args.dry_run:
        logger.info("Dry run — 不執行 API 呼叫")
        for m in DEFAULT_MODELS:
            logger.info("  - %s (%s, %s)", m.name, m.model_id, m.provider)
        logger.info("  Total: %d queries × %d models = %d API calls",
                    len(queries), len(DEFAULT_MODELS), len(queries) * len(DEFAULT_MODELS))
        sys.exit(0)

    # Phase 1: 跑所有模型
    t_start = time.time()
    raw_results = run_committee(queries)
    t_phase1 = time.time()

    logger.info("\nPhase 1 done: %.0fs", t_phase1 - t_start)

    # Phase 2: 產生合議庭報告
    reports: list[CommitteeReport] = []
    for q in queries:
        qid = q["id"]
        model_verdicts = []
        for model_name, verdicts in raw_results.items():
            for v in verdicts:
                if v.query_id == qid:
                    model_verdicts.append(v)

        if model_verdicts:
            report = generate_report(model_verdicts)
            reports.append(report)

            if args.verbose:
                print()
                print(format_report(report))
        else:
            logger.warning("查詢 %s 沒有模型結果", qid)

    t_phase2 = time.time()

    # Phase 3: 彙整摘要
    summary = CommitteeSummary(reports=reports)

    print()
    print("=" * 50)
    print("📊 合議庭最終報告")
    print("=" * 50)
    print(f"  總耗時：{t_phase2 - t_start:.0f}s ({t_start - t_start:.0f}s phase1 + {t_phase2 - t_phase1:.0f}s phase2)")
    print(f"  總查詢：{summary.total_queries} 題 × {len(DEFAULT_MODELS)} 模型")
    print(f"  ✅ 共識通過：{summary.total_queries - summary.total_disagreements} 題")
    print(f"  ⚠️ 分歧標記：{summary.total_disagreements} 題")
    print(f"  ❌ 盲區警示：{summary.total_blind_spots} 題")
    if summary.total_queries > 0:
        print(f"  └─ 分歧率：{summary.total_disagreements / summary.total_queries * 100:.1f}%")
        print(f"  └─ 盲區率：{summary.total_blind_spots / summary.total_queries * 100:.1f}%")
    print()

    # 輸出 JSON
    if args.output:
        summary.to_json(args.output)
        logger.info("已寫入：%s", args.output)

    # 預設輸出到 ablation_results
    output_path = Path.home() / "zhiyan-legal" / "tests" / "ablation_results" / "committee_report.json"
    summary.to_json(str(output_path))
    logger.info("已寫入：%s", output_path)

    sys.exit(0)


if __name__ == "__main__":
    main()

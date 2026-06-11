"""
Zhiyan AI Legal System — CLI entry point.

Usage:
    # With the installed Hermes skill (recommended)
    hermes> /zhiyan <query>

    # Standalone Python CLI (any API provider)
    python -m zhiyan_legal <query>
    python -m zhiyan_legal <query> --dry-run
    python -m zhiyan_legal <query> --model gpt-5.1
    python -m zhiyan_legal --list-tasks
"""

from __future__ import annotations

import argparse
import logging
import sys

from .manifest import get_load_order, EXCLUDED_DIRS, DOCS_DIR
from .router import route, describe_route, KEYWORD_MAP
from .loader import compose, count_tokens
from .runner import run_llm


def setup_logging(level: str = "WARNING") -> None:
    """Configure the zhiyan_legal logger (default: WARNING to suppress noise)."""
    logging.basicConfig(
        format="%(levelname)s | %(name)s | %(message)s",
        level=getattr(logging, level.upper(), logging.WARNING),
    )


def print_task_list() -> None:
    """Print all supported task types with descriptions and sample keywords."""
    seen_descriptions = set()
    print("📋 支援的任務類型\n")
    # Collect keyword samples per task from KEYWORD_MAP
    task_keywords: dict[str, list[str]] = {}
    for kw, task in sorted(KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
        if task not in task_keywords:
            task_keywords[task] = []
        if len(task_keywords[task]) < 3:
            task_keywords[task].append(kw)

    # Ordered display: SAFETY first, then route order, then personas, then litigation
    order = ["SAFETY", "QC", "RESEARCH", "REPORT",
             "CONSULTANT", "TA", "TUTOR", "LEGAL_WRITER", "LITIGATION"]
    for task in order:
        desc = describe_route(task)
        keywords = task_keywords.get(task, [])
        kw_str = "、".join(keywords) if keywords else "（預設）"
        print(f"  {task:15s}  {desc}")
        print(f"  {'':15s}  範例關鍵字：{kw_str}\n")


def main():
    parser = argparse.ArgumentParser(
        description="智研AI法律工作站 — Zhiyan AI Legal System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m zhiyan_legal "什麼是公然侮辱罪?"                    # QC (default)
  python -m zhiyan_legal "查台灣最新 deepfake 立法"              # RESEARCH
  python -m zhiyan_legal "幫我把這些資料整理成報告" --dry-run    # REPORT (no API call)
  python -m zhiyan_legal "我不想活了"                            # SAFETY (override)
  python -m zhiyan_legal --list-tasks                            # 列出所有任務類型
        """,
    )
    parser.add_argument("query", nargs="*", help="你的法律問題或案件事實")
    parser.add_argument("--dry-run", action="store_true", help="模擬執行，不呼叫 API（免費）")
    parser.add_argument("--model", "-m", default=None, help="指定模型 (預設: ZHIYAN_MODEL 或 gpt-5.1)")
    parser.add_argument("--task", "-t", default=None,
                        help="強制指定任務類別 (預設: 自動路由)")
    parser.add_argument("--list-tasks", action="store_true",
                        help="列出所有支援的任務類型與範例關鍵字")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="顯示除錯日誌")

    args = parser.parse_args()

    # Set up logging
    setup_logging("DEBUG" if args.verbose else "WARNING")

    # ── --list-tasks ──
    if args.list_tasks:
        print_task_list()
        return

    # ── Require query ──
    if not args.query:
        parser.print_help()
        sys.exit(1)

    query = " ".join(args.query)

    # ── 1. Route ──
    task = args.task or route(query)
    print(f"🔀 Routed as: {describe_route(task)}")

    # ── 2. Load documents ──
    file_paths = get_load_order(task)
    print(f"📄 Loading {len(file_paths)} document(s)...")

    system_prompt = compose(file_paths)

    token_estimate = count_tokens(system_prompt)
    print(f"📊 System prompt: ~{token_estimate:,} tokens")

    # ── 3. Run ──
    result = run_llm(
        system_prompt=system_prompt,
        user_message=query,
        model=args.model,
        dry_run=args.dry_run,
    )

    if result:
        print("\n" + "=" * 60)
        print("📋 RESPONSE")
        print("=" * 60)
        print(result)


if __name__ == "__main__":
    main()

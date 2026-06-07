"""
Zhiyan AI Legal System — CLI entry point.

Usage:
    # With the installed Hermes skill (recommended)
    hermes> /zhiyan <query>

    # Standalone Python CLI (any API provider)
    python -m zhiyan_legal <query>
    python -m zhiyan_legal <query> --dry-run
    python -m zhiyan_legal <query> --model gpt-4o-mini
"""

from __future__ import annotations

import argparse
import sys

from .manifest import get_load_order, EXCLUDED_DIRS, DOCS_DIR
from .router import route, describe_route
from .loader import compose, count_tokens
from .runner import run_llm


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
        """,
    )
    parser.add_argument("query", nargs="+", help="你的法律問題或案件事實")
    parser.add_argument("--dry-run", action="store_true", help="模擬執行，不呼叫 API（免費）")
    parser.add_argument("--model", "-m", default=None, help="指定模型 (預設: ZHIYAN_MODEL 或 gpt-4o)")
    parser.add_argument("--task", "-t", default=None,
                        help="強制指定任務類別 (預設: 自動路由)")

    args = parser.parse_args()
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

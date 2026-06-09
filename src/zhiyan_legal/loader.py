"""
Prompt loader — composes a single system prompt from ordered document files.
"""

from __future__ import annotations

import os
import warnings
from typing import List, Optional


def load_file(path: str) -> str:
    """Read a markdown file, strip frontmatter."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip YAML frontmatter (between --- markers)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]

    return content.strip()


def compose(
    file_paths: List[str],
    separator: str = "\n\n---\n\n",
    max_chars: Optional[int] = None,
) -> str:
    """
    Load and concatenate a list of document files into one system prompt.

    Parameters
    ----------
    file_paths : List[str]
        Ordered list of file paths to load.
    separator : str
        Separator between documents (default: section divider).
    max_chars : int, optional
        If set, truncate from the end to stay within limit.
    """
    sections: List[str] = []
    missing: List[str] = []

    for fp in file_paths:
        if os.path.exists(fp):
            content = load_file(fp)
            if content:
                # Add a header comment for traceability
                basename = os.path.basename(fp).replace(".md", "")
                sections.append(f"### <{basename}>\n\n{content}")
        else:
            missing.append(fp)

    if missing:
        warnings.warn(
            "⚠️ 以下文件遺失，已跳過：\n" + "\n".join(missing)
        )

    composed = separator.join(sections)

    # Truncate if needed
    if max_chars and len(composed) > max_chars:
        composed = composed[:max_chars]
        composed += "\n\n… [truncated to fit context window]"

    return composed


def count_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4

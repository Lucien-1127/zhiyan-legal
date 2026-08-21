"""
Prompt loader — composes a single system prompt from ordered document files.

Supports YAML frontmatter with metadata fields:
  status: active | draft | deprecated
  as_of_date: YYYY-MM-DD
  version: semver
"""

from __future__ import annotations

import os
import warnings
from typing import Any, Dict, List, Optional, Tuple


def parse_frontmatter(text: str) -> Tuple[str, Dict[str, Any]]:
    """Parse YAML frontmatter from markdown text.

    Returns (body, metadata) where body is the content after frontmatter.
    Metadata keys extracted: status, as_of_date, version, title.
    """
    meta: Dict[str, Any] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            header = parts[1].strip()
            body = parts[2].strip()
            # Minimal YAML parser — only extract known fields
            for line in header.split("\n"):
                line = line.strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    if key in ("status", "as_of_date", "version", "title"):
                        meta[key] = val
            return body, meta
    return text.strip(), meta


def load_file(path: str) -> str:
    """Read a markdown file, strip frontmatter (backward-compatible)."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    body, _ = parse_frontmatter(content)
    return body


def _format_temporal_header(meta: Dict[str, Any]) -> str:
    """Generate a temporal context header from metadata."""
    parts = []
    if meta.get("status"):
        emoji = {"active": "✅", "draft": "📝", "deprecated": "⚠️"}
        e = emoji.get(meta["status"], "📄")
        parts.append(f"{e} status: {meta['status']}")
    if meta.get("as_of_date"):
        parts.append(f"as of {meta['as_of_date']}")
    if meta.get("version"):
        parts.append(f"v{meta['version']}")
    if parts:
        return f"> 📅 {' | '.join(parts)}\n\n"
    return ""


def compose(
    file_paths: List[str],
    separator: str = "\n\n---\n\n",
    max_chars: Optional[int] = None,
    simulation_mode: bool = False,
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
    simulation_mode : bool
        If True, prepend simulation mode exemption section.
    """
    sections: List[str] = []
    missing: List[str] = []

    # ── Simulation mode preamble ──
    if simulation_mode:
        sections.append(
            "🧪 模擬模式已啟用\n\n"
            "以下推理基於使用者提供的假設前提，"
            "非現行有效法律意見。每段結論將附帶對照組說明。\n"
        )

    for fp in file_paths:
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8") as f:
                raw = f.read()
            body, meta = parse_frontmatter(raw)

            if body:
                # Add basename header for traceability
                basename = os.path.basename(fp).replace(".md", "")
                header = f"### <{basename}>"
                temporal = _format_temporal_header(meta)
                content = header
                if temporal:
                    content += f"\n\n{temporal}{body}"
                else:
                    content += f"\n\n{body}"
                sections.append(content)
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
    """Rough token estimate: CJK chars ~1.5 tokens each, Latin ~0.25 tokens/char."""
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    latin = len(text) - cjk
    return int(cjk * 1.5 + latin * 0.25)

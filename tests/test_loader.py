"""
Loader tests — compose(), load_file(), count_tokens()

Run with:  PYTHONPATH=src pytest tests/test_loader.py -v
"""

from pathlib import Path
import sys
import warnings
import tempfile
import os
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zhiyan_legal.loader import compose, load_file, count_tokens


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ── load_file() ─────────────────────────────────────────────────────

def test_load_file_strips_frontmatter(tmp_dir):
    """YAML frontmatter (---) 應被剝離"""
    f = tmp_dir / "test.md"
    f.write_text("---\ntitle: test\n---\n\n實際內容")
    assert load_file(str(f)) == "實際內容"


def test_load_file_no_frontmatter(tmp_dir):
    """無 frontmatter 時回傳完整內容"""
    f = tmp_dir / "test.md"
    f.write_text("純內容")
    assert load_file(str(f)) == "純內容"


def test_load_file_strips_leading_trailing_whitespace(tmp_dir):
    """前後空白應被 strip"""
    f = tmp_dir / "test.md"
    f.write_text("  \n內容\n  ")
    assert load_file(str(f)) == "內容"


# ── compose() ───────────────────────────────────────────────────────

def test_compose_basic(tmp_dir):
    """多文件應依序串接"""
    a = tmp_dir / "a.md"
    b = tmp_dir / "b.md"
    a.write_text("文件A")
    b.write_text("文件B")
    result = compose([str(a), str(b)], separator="\n---\n")
    assert "文件A" in result
    assert "文件B" in result
    assert "---" in result


def test_compose_adds_header_comment(tmp_dir):
    """每個文件應加上 <檔名> 標頭"""
    f = tmp_dir / "test.md"
    f.write_text("內容")
    result = compose([str(f)], separator="\n")
    assert "<test>" in result


def test_compose_missing_file_warns(tmp_dir):
    """遺失文件應發出警告"""
    missing = str(tmp_dir / "不存在.md")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = compose([missing])
        assert len(w) == 1
        assert "不存在.md" in str(w[0].message)


def test_compose_truncation(tmp_dir):
    """max_chars 應正確截斷（含標頭前綴）"""
    f = tmp_dir / "long.md"
    f.write_text("A" * 100)
    result = compose([str(f)], max_chars=10)
    # 內容被截斷後應出現 truncation 標記
    assert "truncated" in result
    # 總長度 = max_chars + truncation 附加文字
    assert len(result) == 10 + len("\n\n… [truncated to fit context window]")


def test_compose_empty_file_skipped(tmp_dir):
    """空檔案應被跳過（不加入 sections）"""
    f = tmp_dir / "empty.md"
    f.write_text("")
    # Also need a non-empty file to get any output
    result = compose([str(f)])
    assert result == ""


# ── count_tokens() ──────────────────────────────────────────────────

def test_count_tokens_estimate():
    """count_tokens 使用 len//4 估算"""
    assert count_tokens("A" * 40) == 10
    assert count_tokens("") == 0

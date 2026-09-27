"""Keep the public homepage aligned with Zhiyan's user-facing purpose."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_homepage_explains_value_without_engineering_jargon() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "先找依據，再回答法律問題" in html
    assert "看得懂" in html
    assert "查得到" in html
    assert "不硬猜" in html
    assert "研究工具，不取代律師" in html
    assert "5 層架構" not in html
    assert "deepseek-chat" not in html
    assert "SaaS 版" not in html


def test_chat_ui_can_show_citations_without_injecting_source_html() -> None:
    script = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "appendCitations" in script
    assert "citation.exact_quote" in script
    assert "citation.locator" in script
    assert "textContent = citation.exact_quote" in script
    assert "tokens</span>" not in script


def test_documentation_home_has_one_plain_language_entry_point() -> None:
    docs_home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")

    assert docs_home.count("## 為什麼要用智研") == 1
    assert "G0 → INTAKE" not in docs_home
    assert "RQ1" not in docs_home

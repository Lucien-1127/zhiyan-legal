"""司法院裁判書擷取引擎。
從 committee_core/reasoning/scraping_engine.py 搬入（v3.9.5）
依賴 scrapling 庫，內建 MCP 友善結構。
"""
class JudicialScraper:
    """基於 Scrapling 的法律文件提取器，內建 MCP 友善結構。"""

    def __init__(self):
        try:
            from scrapling import Scrape
        except ImportError as exc:
            raise ImportError(
                "JudicialScraper requires the optional 'scrapling' dependency"
            ) from exc
        self.scraper = Scrape()

    def fetch_judgment(self, url: str) -> dict:
        """提取司法院裁判書網頁。"""
        page = self.scraper.scrape(url)
        return {
            "title":   page.find("h1").text,
            "content": page.find("div.judgement-content").text,
            "source":  url,
        }

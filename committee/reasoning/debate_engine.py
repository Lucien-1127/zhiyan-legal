"""辨論引擎 — 跨模型辨論編排。
從 committee_core/reasoning/debate_engine.py 搬入（v3.9.5）
"""


class DebateEngine:
    """跨模型辨論引擎，不依賴任何領域知識。"""

    def __init__(self, models):
        self.models = models

    def orchestrate_debate(self, claim):
        """跨模型辨論邏輯—待實作。"""
        pass

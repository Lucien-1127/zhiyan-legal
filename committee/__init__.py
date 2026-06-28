"""
committee — 多模型合議庭標示器

zhiyan-legal 的品質閘門。不裁決，只標示。

Flow:
  1. Runner: 同一查詢送給 N 個模型 (平行)
  2. Normalizer: 正規化所有回應 (用語/條號/語意)
  3. Mapper: 比對 → 產生合議庭報告 (共識/分歧/盲區)
"""

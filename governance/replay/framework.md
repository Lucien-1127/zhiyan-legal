# Decision Replay Framework (DRF)

本框架用於驗證 Decision OS 之治理規則 (Governance Contract) 的品質與演進。

## 五大關鍵決策問題
1. **Original Decision**: 當時系統如何決策？
2. **Decision Evidence**: 當時依據哪些資訊？
3. **Decision Outcome**: 最終結果如何？
4. **Replay Decision**: 套用當前 V13.2 Policy 後如何決策？
5. **Delta Analysis**: 新舊流程差異、成本與風險比較。

## 審查原則 (Regression Test)
- 若 Accuracy 下降 → Reject
- 若 Cost 上升 → Audit (檢查是否為必要開銷)
- 若 Decision 變差 → Reject

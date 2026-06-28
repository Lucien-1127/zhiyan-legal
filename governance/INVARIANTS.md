# Governance Invariants (V13.2)

任何版本的 Decision OS 均必須嚴格遵守以下四條不變量 (Invariants)：

1. **I001 (Security)**: 任何高風險請求，不得直接執行 Tool，必須觸發 Committee Veto。
2. **I002 (Evidence)**: Evidence 不足（如無至少三條法條基礎），不得生成最終法律結論。
3. **I003 (Capability)**: Capability Registry 為唯讀，任何 Agent 不得於運行期間自行修改權限。
4. **I004 (Traceability)**: 任何決策變更必須在 Governance Ledger 留下 Trace。

這些不變量是 GVF (Governance Verification Framework) 的最高效能基準。

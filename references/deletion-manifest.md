# 智研全庫清理與舊版廢棄模組刪除清單 (Deletion Manifest Specification)

> **版本**：v1.0.0 (Phase 5 Approved Deletion Manifest)  
> **硬性約束**：刪除任何檔案前必須具有明確之 deletion_manifest，且受保護之核心資產（`docs/`、`law_monitor_app/`、`graphrag/` 等）絕對禁止刪除。

---

## 一、受保護核心資產清單 (DO-NOT-DELETE LIST)

以下目錄與檔案屬於業務、知識庫或未來規劃核心資產，**嚴禁刪除**：
1. `docs/**`（包含所有概念詞條、模式說明、升級路線圖、架構文件）
2. `references/**`（所有 Phase 1~5 Approved Specifications）
3. `audit/**`（審計基準與驗收報告）
4. `law_monitor_app/**`（法規監控前端應用）
5. `graphrag/**`（知識圖譜檢索模組）
6. `regulation_tracker/**`（法規異動追蹤）
7. `src/zhiyan_legal/domain/**`
8. `src/zhiyan_legal/pipeline/**`
9. `src/zhiyan_legal/tools/**`
10. `src/zhiyan_legal/verification/**`
11. `src/zhiyan_legal/providers/**`
12. `src/zhiyan_legal/application/**`
13. `src/zhiyan_legal/interfaces/**`
14. `src/zhiyan_legal/committee/**`

---

## 二、核准清理與刪除之死碼／重複檔案清單 (DELETION MANIFEST)

| 預定刪除路徑 | 原始用途 | 替代之 Canonical 路徑 | 移除理由與相依分析 |
| :--- | :--- | :--- | :--- |
| `zhiyan_legal/schemas/judgment.py` | 頂層舊版重複 judgment schema (ZHIYAN-F-0008) | `src/zhiyan_legal/schemas/judgment.py` | 舊重複定義，其驗證邏輯已於 Phase 1 完整吸收，頂層資料夾為孤立重複目錄 |
| `committee_core/policies/governance_contract.py` | 舊版重複 governance contract | `src/zhiyan_legal/domain/decision.py` | 舊版重複契約，Phase 1 相容邊界已建立，內部邏輯已完全由 Canonical 接管 |
| `committee_core/reasoning/debate_engine.py` | 舊版重複 debate engine | `src/zhiyan_legal/committee/engine.py` | 舊版重複推理引擎，已由 Committee vNext 完整取代 |
| `committee_core/reasoning/scraping_engine.py` | 舊版重複 scraping engine | `src/zhiyan_legal/tools/judicial.py` | 舊版重複爬蟲引擎，已由 Canonical Tool Adapters 完整取代 |

---

## 三、相容導出清理 (DEPRECATION RETENTION)

以下檔案保留為純向後相容 re-export，禁止直接刪除，但內部需確認純淨且無殘留業務邏輯：
1. `src/zhiyan_legal/runner.py`（轉發至 `src/zhiyan_legal/engine.py`）
2. `src/zhiyan_legal/regulation_api.py`（轉發至 `src/zhiyan_legal/interfaces/http_regulation.py`）
3. `committee_core/__init__.py`（向後相容導出）

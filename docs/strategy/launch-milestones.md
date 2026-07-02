# zhiyan-legal 上架準備：里程碑規劃

> 從開源研究框架 → 可上架產品，需要補足的關鍵路徑
> 對標 Lawbot AI（已商業化）作為最低門檻參考

---

## 總覽

### 當前狀態（v3.08）

| 指標 | 數值 |
|:----|:-----|
| 總檔案數 | 431 |
| Commits | 118 |
| 測試案例 | 123（+ 2 份 Benchmark 測驗集） |
| Python 程式碼 | 11,474 行 |
| 提示詞模組 | 15 個人格/模組 |
| 審計委員發現 | 166 項（已修復 7 項） |

### 目標分級

```
階段          目標                          預估工期
────          ────                          ────────
M0 (現在)     v3.08 — 開源研究框架           已完成
M1 (MVP)     CLI + API 可服務外部使用者      2-3 週
M2 (產品)     PWA 可操作 + 基本商業閉環       4-6 週
M3 (上市)     App Store + 生產部署            6-8 週
```

---

## M1：MVP — 可對外服務（2-3 週達成）

> **目標：** 讓任何人不必 clone repo 就能使用 zhiyan-legal
> **驗證標準：** 新使用者從 landing page 到完成一次法律查詢 < 5 分鐘

### 🔴 必要項目（缺一不可）

| # | 項目 | 當前狀態 | 需求規格 | 預估工時 |
|:--|:-----|:--------|:---------|:--------|
| M1.1 | **API 生產就緒** | `/query` 仍有 fallback 模式 | 移除 stub，所有請求走真實引擎，錯誤處理完整 | 8h |
| M1.2 | **API Key 認證** | ❌ 無 | 發放 API Key → header 驗證 → 用量計數 | 4h |
| M1.3 | **速率限制** | ❌ 無 | 每 key 每分鐘 N 請求，超過回傳 429 | 2h |
| M1.4 | **OpenAPI 文件** | ❌ 無 | 自動生成 Swagger UI（FastAPI 已有基礎→補 description/example） | 3h |
| M1.5 | **Health Check 完整** | 僅回傳 ok | 加上 DB/SR/enpine 各元件狀態 + 版本號 | 1h |
| M1.6 | **Docker 可部署** | 缺少 docker-compose | 補 docker-compose.yml（api + db + caddy）+ 修復已知問題 | 4h |
| M1.7 | **Landing Page**（非 MkDocs） | ❌ 無 | 靜態首頁：功能介紹 + API 文件連結 + 快速開始 | 4h |

**M1 驗收標準：**
```bash
curl -X POST "https://api.zhiyan-legal.com/v1/query" \
  -H "X-API-Key: test_key_xxx" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "何謂公然侮辱？", "mode": "chat"}'
# 預期：200 + 結構化法律分析（非 stub）
```

---

## M2：產品化 — 有 UX 的 SaaS（4-6 週）

> **目標：** 非技術使用者也能操作，建立基本商業模式
> **驗證標準：** 律師事務所助理不需 terminal 就能完成案件研究

### 🟡 核心功能（決定使用者是否留下）

| # | 項目 | 當前狀態 | 需求規格 | 預估工時 |
|:--|:-----|:--------|:---------|:--------|
| M2.1 | **Flutter PWA 完成** | 僅有法規監控畫面 | 完整對話介面 + 法條查詢 + 書狀產生 | 40h |
| M2.2 | **使用者註冊/登入** | ❌ 無 | Email + Google OAuth 登入 | 8h |
| M2.3 | **用量管理後台** | ❌ 無 | 管理員儀表板：使用者列表、用量圖表、key 管理 | 12h |
| M2.4 | **付費方案** | ❌ 無 | Stripe/LemonSqueezy 串接、訂閱管理、發票 | 16h |
| M2.5 | **案件管理輕量版** | ❌ 無 | 建立案件、上傳文件、查詢歷史、標籤分類 | 16h |
| M2.6 | **爭點樹狀圖** | ❌ 無 | AI 自動產生爭點視覺化圖表（Mermaid.js） | 8h |
| M2.7 | **MCP 公開文檔** | 已實作未公開 | 寫 MCP Server 安裝指南 + 範例 + troubleshooting | 4h |
| M2.8 | **Chrome 擴充 v1** | ❌ 無 | 選取文字 → 右鍵→ Lawbot 查詢 | 12h |

**M2 驗收標準：**
1. 新使用者 Email 註冊 → 自動取得 7 天試用
2. Web App 內完成一次完整法律研究（搜尋→摘要→存檔）
3. 網站管理員能看到每日活躍使用者與 API 用量

---

## M3：上市 — App Store + 生產營運（6-8 週）

> **目標：** iOS/Android App Store 上架 + 生產環境 SLA 99.5%
> **驗證標準：** 連續 7 天無 P0/P1 生產事故

### 🟢 營運準備（決定能撐多久）

| # | 項目 | 當前狀態 | 需求規格 | 預估工時 |
|:--|:-----|:--------|:---------|:--------|
| M3.1 | **App 上架** | Flutter 程式碼存在但未完成 | 補完 UI、審核素材、iOS/Android 送審 | 40h |
| M3.2 | **SLA 監控** | ❌ 無 | Uptime Robot / Grafana + PagerDuty 告警 | 8h |
| M3.3 | **錯誤追蹤** | ❌ 無 | Sentry 整合（API + Flutter） | 4h |
| M3.4 | **日誌系統** | 只有 print logging | 結構化日誌 + 日誌分級 + 保留政策 | 4h |
| M3.5 | **備份策略** | ❌ 無 | 自動每日備份 DB + 法條資料庫 | 2h |
| M3.6 | **TOS/Privacy** | ❌ 無 | 使用者條款 + 隱私政策 + 免責聲明（律師審閱） | 8h |
| M3.7 | **安全審計** | 已知 6 項資安缺口 | 修復所有 High 以上發現（Secret Manager、API Key 管理） | 8h |
| M3.8 | **負載測試** | ❌ 無 | 100 同時連線壓力測試 + 優化 | 8h |

**M3 驗收標準：**
1. App Store Connect / Google Play Console 顯示「已上架」
2. 連續 7 天 uptime ≥ 99.5%
3. 新使用者從下載到第一次查詢 ≤ 3 分鐘

---

## 資源估算總表

| 階段 | 工時合計 | 關鍵技能需求 | 可並行項目 |
|:----|:--------|:------------|:----------|
| **M1** MVP | ~26h | DevOps + FastAPI + Docker | M1.4+M1.7 可並行 |
| **M2** 產品 | ~116h | Flutter + Stripe + Chrome Extension | M2.1+M2.7+M2.8 可並行 |
| **M3** 上市 | ~82h | DevOps + iOS/Android 送審 + 律師 | M3.2+M3.3+M3.5 可並行 |
| **總計** | **~224h** | 約 5-6 週全職，或 8-10 週兼職 | — |

---

## 優先序建議

### 如果只能選 3 件事先做（最小可上架）

1. **M1.1 + M1.6**（API + Docker）— 讓別人可以部署
2. **M2.1**（Flutter PWA 完成）— 讓非技術使用者可用
3. **M3.6**（TOS/Privacy）— 法律保護傘，沒這個不能上架

### 如果只補 Lawbot AI 差距

| Lawbot 已經有 | zhiyan 缺 | 對應里程碑 |
|:-------------|:----------|:----------|
| App iOS/Android | ❌ | M3.1（~40h） |
| Chrome 擴充 | ❌ | M2.8（~12h） |
| 案件管理 | ❌ | M2.5（~16h） |
| MCP 對外公開 | 已實作未公開 | M2.7（~4h） |

### 建議路線

```
第 1-2 週：M1（API + Docker + Landing Page）→ 可部署
第 3-4 週：M2.1 + M2.7（Flutter + MCP）→ 可體驗
第 5-6 週：M2.5 + M2.8（案件管理 + Chrome）→ 可留存
第 7-8 週：M3.1 + M3.6（上架 + TOS）→ 可營運
```

---

## 上架條件清單（Checklist）

### ✅ 技術條件（全部 Pass 才能送審）

- [ ] API 無已知 Critical/High bug（審計 P0 已修復 ✅）
- [ ] 所有 endpoints 有 rate limiting
- [ ] API Key 認證正確
- [ ] Docker 可一鍵部署
- [ ] Flutter App 無 crash（Sentry 監控 7 天）
- [ ] 敏感資料無硬編碼（審計 P0 已修復 ✅）
- [ ] iOS/Android 審核指南符合

### ✅ 法務條件（缺一不可）

- [ ] 使用者條款（TOS）
- [ ] 隱私政策（Privacy Policy）
- [ ] 免責聲明（Disclaimer — 法律 AI 輸出非法律意見）
- [ ] 資料處理同意書（個資法）
- [ ] 委外處理登記（若使用外部 LLM API）

### ✅ 產品條件（決定 reviewer 會不會通過）

- [ ] 完整 onboarding 流程（新使用者 3 分鐘內完成首次查詢）
- [ ] 無 stub/TODO 功能的 UI
- [ ] 錯誤狀態處理（網路失敗、逾時、配額耗盡皆有對應 UI）
- [ ] App 圖示 + 截圖 + 描述符合實際功能

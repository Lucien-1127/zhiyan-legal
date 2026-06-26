# law_monitor_app — 法規異動監控儀表板

Flutter Android 應用程式，搭配 **智研 AI 法律系統** 的 `regulation_api` FastAPI 後端使用。

---

## 功能特色

- **法規狀態總覽** — 22 部追蹤中法規的即時狀態（🟢 無異動 / 🟡 近期異動 / 🔴 需關注）
- **異動歷程檢視** — 每部法規的歷史版本變更記錄
- **條文比對檢視** — Word 三欄新舊對照表的 App 內檢視
- **關鍵字搜尋** — 跨法規條文關鍵字檢索
- **自訂 API URL** — 支援 Tailscale 內網連線，也可設定公網端點
- **深色/淺色主題** — 自動跟隨系統設定

---

## 系統架構

```
┌─────────────────────────────────────────────────────┐
│                    Flutter App                       │
│  law_monitor_app/                                   │
│    ├── Dashboard (22 法規卡片)                       │
│    ├── Detail Page (條文歷程 + 比對)                 │
│    └── Search (跨法規全文檢索)                      │
└──────────────┬──────────────────────────────────────┘
               │ REST API (JSON)
               ▼
┌──────────────────────────────────────────────────────┐
│              regulation_api (FastAPI)                 │
│  內建於 zhiyan-legal/src/zhiyan_legal/                │
│  Port 7850                                           │
│  Swagger: /docs                                      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│            regulation_tracker (SQLite)                 │
│  data/regulations.db                                   │
│ 條文快照: data/articles/<pcode>.json                   │
└───────────────────────────────────────────────────────┘
```

---

## 開發環境

```bash
cd law_monitor_app/
flutter pub get
flutter run
```

### 模擬器注意事項

模擬器無法直接連到主機 `localhost:7850`，需在 App 設定中改為 `10.0.2.2:7850`（Android 模擬器映射 host localhost）。實體裝置在同一 Tailscale 網路下可直接使用 Tailscale IP。

---

## API 端點參考

| 端點 | 說明 | 方法 |
|------|------|------|
| `/api/status` | 系統狀態 | GET |
| `/api/tracked` | 追蹤中法規列表含狀態 | GET |
| `/api/check` | 立即執行異動檢查 | POST |
| `/api/sync` | 同步法規索引 | POST |
| `/api/search?q=關鍵字` | 全文檢索 | GET |
| `/api/diff/<pcode>` | 指定法規新舊條文對照 | GET |
| `/api/diff/all` | 所有異動法規對照 | GET |
| `/api/history/<pcode>` | 歷次版本記錄 | GET |

完整 API 文件請見執行中的 Swagger UI：`http://<host>:7850/docs`

---

## Build APK

```bash
cd law_monitor_app/
flutter build apk --release
```

產出：`build/app/outputs/flutter-apk/app-release.apk`

---

## 依賴

Flutter SDK（3.x+），詳見 `pubspec.yaml`。

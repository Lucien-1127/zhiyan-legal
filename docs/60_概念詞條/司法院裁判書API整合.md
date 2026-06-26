# 司法院裁判書開放 API 整合

## 端點

```
Base: https://data.judicial.gov.tw/jdg/api
Auth: POST /Auth         — 帳密登入 → Token (6h 有效)
JList: POST /JList       — 取得 7 日前裁判書異動清單
JDoc:  POST /JDoc        — 依 JID 取得裁判書全文
```

## 限制

- 服務時間：**00:00–06:00**（每日），其餘時間不提供
- Token 有效期限：6 小時
- JList 回傳 7 日前資料（非即時）
- 裁判書可能被要求刪除（`error: 裁判可能未公開或已從系統移除`）

## 整合模組

`src/zhiyan_legal/judicial_api.py`

### 使用方式

```python
from zhiyan_legal.judicial_api import search_judgment

# 設定環境變數（或直接傳參）
# export JUDICIAL_API_USER=your_account
# export JUDICIAL_API_PASS=your_password

# 查詢判決
result = search_judgment("最高法院112年度台上字第1234號")
if result:
    print(result["JTITLE"])                    # 裁判案由
    print(result["JFULLX"]["JFULLCONTENT"])    # 全文
```

### 取代現有流程

**目前：** L0.8 案例驗證層 → web_search judgment.judicial.gov.tw（慢 + 不穩定）
**優化後：** L0.8 → judicial_api.search_judgment()（REST API，結構化 JSON）

### 尚未完成

- [ ] 填入 JUDICIAL_API_USER / JUDICIAL_API_PASS（需使用者在司法院資料開放平臺註冊）
- [ ] 整合至 L0.8 案例驗證層（需 API 金鑰確認可用後）
- [ ] 本地快取已查詢的判決（減少 API 呼叫）

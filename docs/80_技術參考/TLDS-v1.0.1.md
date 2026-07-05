# TLDS — Taiwan Legal Document Specification

**智研（ZhiYan）AI 法律文件標準規範**

| 欄位 | 值 |
|---|---|
| 版本 | v1.0.1 |
| 狀態 | Draft |
| 範圍 | 消費借貸契約 ＋ 普通抵押權設定契約書 |
| 授權 | MIT |
| 上游依賴 | zhiyan-legal（知識層，47,001 條法條庫） |
| 規格語言 | 繁體中文（臺灣標準） |

> **v1.0 範圍聲明**：本版本僅規範一條垂直切片（借貸＋抵押權設定），
> 目的是完整走通 Metadata → 條款 → 變數 → 驗證 → DOCX/PDF 全流程，
> 驗證規格可行性。其餘文件類型見〈附錄 Z：Roadmap〉，**非本版規範內容**。

> **關鍵字定義**：本文件中「必須（MUST）」「禁止（MUST NOT)」「應（SHOULD）」
> 「可（MAY）」依 RFC 2119 語意解讀。

---

## ⚠️ 待完成事項（Pending Items）

> **注意**：以下項目尚未完成驗證，待全部確認完成後移除本區塊。

| # | 項目 | 對應規則 | 狀態 |
|---|---|---|---|
| P-01 | `knowledge/` 層 `kb_id` 完整性掃描：確認 `civil-0474`、`civil-0205`、`civil-0478`、`civil-0233`、`civil-0758`、`civil-0860`、`civil-0861`、`land-reg-0034` 等節點皆存在 | HV-06 / §A.4 | ⬜ 未驗證 |
| P-02 | `scripts/` 建立 `validate_kb_ids.py`：自動掃描所有 `legal_basis` 的 `kb_id`，輸出缺漏清單 | HV-06 | ⬜ 未建立 |
| P-03 | `tests/` 建立 `test_tlds_hv.py`：涵蓋 HV-01 至 HV-14 各至少一個單元測試 | Part M | ⬜ 未建立 |
| P-04 | `committee/` 或 `committee_core/` 確認支援 `JUDGE=EXT` 獨立評分角色（FEG_TLDS Layer 2） | §M.3 | ⬜ 待確認 |
| P-05 | `docker/` 確認 LibreOffice headless 版本已安裝，PDF subset embedding 可正常執行，且 `fc-list` / `pdffonts` 驗證 Noto 字體鏈一致 | §N / 規則 D-3 / HV-12 | ⬜ 待確認 |
| P-06 | HV-04 個資防填充日誌機制：執行層需實作生成日誌比對，確認個資變數值來源為使用者輸入而非 AI 生成 | HV-04 / 規則 L-1 | ⬜ 未實作 |
| P-07 | `SKILL.md` 新增「TLDS Skill」區塊，定義 AI 呼叫法律文件生成技能時讀取本規格為錨點 | 三層架構 Layer 1↔3 | ⬜ 未新增 |
| P-08 | FEG_TLDS 七維度（A–G）完整評分基準表（v1.0.1 工作項，依 §M.3 格式補齊） | §M.3 | ⬜ 規劃中 |
| P-09 | `CL-LOAN-007` 簽章區元件化裁決：定義簽章區最小錨點集合、頁尾干擾排除、機器驗證特徵字串 | §F.1.2 / HV-13 | ⬜ 新增 |
| P-10 | HV-14：契約本文污染掃描（meta-text detector）實作與單元測試 | §G.1 / Part M | ⬜ 新增 |

---

## 三層架構定位

```
┌─ Layer 1｜TLDS（規格層）────── 本文件
├─ Layer 2｜Knowledge Base（知識層）── zhiyan-legal 儲存庫（既有資產，不另建）
└─ Layer 3｜Execution Engine（執行層）─ 生成/驗證/輸出引擎（依本規格實作）
```

**規則**：Layer 3 的任何行為必須可回溯至 Layer 1 的條號規則；
Layer 1 的任何法律主張必須可回溯至 Layer 2 的法條/判決記錄。
TLDS 本身**禁止**內嵌法條全文——只存引用指標（見 §A.4），
避免修法時規格層與知識層出現兩套版本。

---

# Part A：Document Metadata Schema

## A.1 Schema 定義（YAML frontmatter，Pydantic v2 相容）

每份 TLDS 文件必須以下列 frontmatter 開頭：

```yaml
tlds_version: "1.0.1"
doc_id: "ZY-LOAN-20260706-0001"
doc_type: "contract.loan"
title: "消費借貸契約書"
version: "1.0.1"
status: "draft"
jurisdiction: "TW"
language: "zh-TW"
confidential: true
author: ""
reviewer: null
approved_by: null
approved_date: null
legal_basis: []
revision_history: []
```

**規則 A-1**：`status: final` 時 `reviewer`、`approved_by`、`approved_date` 必須非 null。
**規則 A-2**：`status: final` 的文件內容禁止修改；修改必須升版並回到 `draft`。

## A.2 Document ID 編碼規則

```
{ORG}-{TYPE}-{YYYYMMDD}-{SEQ}
 ZY    LOAN    20260706   0001
```

- `ORG`：2–4 碼大寫，智研 = `ZY`
- `TYPE`：文件類型碼（LOAN=借貸、MORT=抵押權設定）
- `SEQ`：當日流水號 4 碼，執行層負責唯一性

Regex：`^[A-Z]{2,4}-[A-Z]{2,6}-\d{8}-\d{4}$`

## A.3 doc_type 枚舉（v1.0）

| 值 | 說明 | TYPE 碼 |
|---|---|---|
| `contract.loan` | 消費借貸契約 | LOAN |
| `registration.mortgage` | 普通抵押權設定契約書 | MORT |

其他類型**保留**至 v1.1+（附錄 Z）。未列入枚舉的 doc_type 必須被執行層拒絕。

## A.4 LegalRef 格式（法條引用指標）

```yaml
- law: "民法"
  article: "474"
  paragraph: 1
  kb_id: "civil-0474"
```

**規則 A-3**：`kb_id` 在知識層查無對應節點 → 硬驗證 FAIL（見 Part M）。
這是「不得捏造法律依據」原則的機器實作。

> ⚠️ **Pending P-01**：上列 kb_id 實際存在性尚未通過自動掃描確認。

---

# Part B：Layout Engine（版面規格）

## B.1 適用範圍聲明

本 Part 僅規範**契約與登記文件**。法院書狀排版依司法院《司法狀紙要點》
官方格式，屬 v1.2 範圍（附錄 Z），本版**禁止**以下列參數生成法院書狀。

## B.2 頁面規格（normative）

| 參數 | 值 |
|---|---|
| 紙張 | A4（210 × 297 mm）直式 |
| 頁面常數 | `11906 × 16838` DXA（實作端應使用固定常數，避免換算 diff 噪音） |
| 上邊界 | 2.5 cm |
| 下邊界 | 2.5 cm |
| 左邊界 | 3.0 cm（含裝訂區） |
| 右邊界 | 2.5 cm |
| 頁碼 | 頁尾置中，格式「第 X 頁，共 Y 頁」 |
| 騎縫章預留 | 左邊界內側 1.0 cm 帶狀區，不排文字 |

行數與每行字數為**版面推導結果**（由字級＋行距決定），非獨立規則，
執行層禁止另設行數限制造成截斷。

## B.3 樣式定義（DOCX Style 對照）

| Style 名稱 | 字型（中） | 字級 | 行距 | 段前/段後 | 對齊 |
|---|---|---|---|---|---|
| `TLDS-Title` | Noto Serif TC Bold | 18 pt | 固定 28 pt | 0 / 24 pt | 置中 |
| `TLDS-H1` | Noto Serif TC Bold | 14 pt | 固定 24 pt | 18 / 6 pt | 靠左 |
| `TLDS-Body` | Noto Serif TC | 12 pt | 固定 24 pt | 0 / 6 pt | 兩端對齊 |
| `TLDS-Clause` | Noto Serif TC | 12 pt | 固定 24 pt | 6 / 6 pt | 兩端對齊，首行縮排 2 字元 |
| `TLDS-Table` | Noto Sans TC | 10 pt | 固定 18 pt | 0 / 0 | 靠左 |
| `TLDS-Sign` | Noto Serif TC | 12 pt | 固定 32 pt | 12 / 12 pt | 靠左 |

**規則 B-1**：`TLDS-H1` 必須設定 Keep with Next。
**規則 B-2**：簽章區（`TLDS-Sign` 區塊）禁止跨頁分割；不足時整區換頁。
**規則 B-3**：全文啟用 Widow/Orphan Control。

---

# Part D：Font Management（字體規則）

## D.1 授權分級（🔴 強制）

| 字體 | 授權 | 伺服器端生成 | PDF 嵌入 | 使用者本機 Word |
|---|---|---|---|---|
| Noto Serif TC | SIL OFL 1.1 | ✅ | ✅ | ✅ |
| Noto Sans TC | SIL OFL 1.1 | ✅ | ✅ | ✅ |
| 標楷體 DFKai-SB | 微軟/華康商業授權 | ❌ 禁止 | ❌ 禁止 | ✅（隨 Windows 授權） |
| 新細明體 PMingLiU | 微軟商業授權 | ❌ 禁止 | ❌ 禁止 | ✅ |

**規則 D-1**：GCP／任何 Linux 伺服器端的 DOCX/PDF 生成，唯一合法中文字體
為 Noto 系列。執行層在字體清單中發現 DFKai-SB / PMingLiU 出現於
PDF 嵌入路徑 → 硬驗證 FAIL。

**規則 D-2**：DOCX 輸出可宣告字體 fallback 鏈：
`Noto Serif TC → Noto Serif CJK TC → PMingLiU → 標楷體`；
`Noto Sans TC → Noto Sans CJK TC → PMingLiU → 標楷體`。
宣告字體名稱不等於嵌入字體檔，合法，但最終 PDF 仍受 HV-12 約束。

**規則 D-3**：PDF 輸出必須嵌入字體（subset embedding），確保跨平台列印一致。

> ⚠️ **Pending P-05**：Docker 環境中 LibreOffice headless 版本、字體安裝清單及 subset embedding 功能尚待確認。

---

# Part F/G：契約模組（v1.0 兩件）

## F.1 模組：consumer-loan（消費借貸契約）

### F.1.1 法律依據（legal_basis 必含）

| 依據 | 用途 | kb_id |
|---|---|---|
| 民法第 474 條 | 消費借貸定義 | civil-0474 |
| 民法第 205 條 | 約定利率上限：週年百分之十六 | civil-0205 |
| 民法第 478 條 | 返還時期 | civil-0478 |
| 民法第 233 條 | 遲延利息 | civil-0233 |

> 🔴 民法第 205 條於民國 110 年 7 月 20 日施行修正條文，
> 約定利率上限為**週年 16%**，超過部分約定無效。
> 驗證規則 HV-07 依此實作。

### F.1.2 必要條款（required_clauses）

```
CL-LOAN-001  當事人
CL-LOAN-002  借貸金額與交付方式
CL-LOAN-003  利息約定
CL-LOAN-004  清償期與清償方式
CL-LOAN-005  遲延責任
CL-LOAN-006  管轄法院
CL-LOAN-007  簽章
```

### F.1.3 選用條款（optional_clauses）

```
CL-LOAN-101  提前清償
CL-LOAN-102  連帶保證人
CL-LOAN-103  擔保（觸發 registration.mortgage 模組連動）
CL-LOAN-104  本票擔保
```

**規則 F-1**：選用 CL-LOAN-103 時，執行層必須提示是否同步生成
`registration.mortgage` 文件，且兩份文件的 `{{Amount}}`、當事人變數
必須通過跨文件一致性驗證（HV-10）。

## G.1 模組：mortgage-registration（普通抵押權設定契約書）

### G.1.1 法律依據

| 依據 | 用途 | kb_id |
|---|---|---|
| 民法第 758 條 | 不動產物權書面＋登記生效 | civil-0758 |
| 民法第 860 條 | 普通抵押權定義 | civil-0860 |
| 民法第 861 條 | 抵押權擔保範圍 | civil-0861 |
| 土地登記規則第 34 條 | 申請登記應附文件 | land-reg-0034 |

### G.1.2 必要區塊

```
CL-MORT-001  立契約書人（權利人／義務人）
CL-MORT-002  擔保債權金額與種類
CL-MORT-003  標的不動產標示（地籍／建物）
CL-MORT-004  擔保債權清償日期
CL-MORT-005  利息／遲延利息／違約金記載
CL-MORT-006  簽章與立約日期
```

### G.1.3 必要附件清單（attachments，驗證 HV-09 檢查）

- 登記申請書
- 權利人／義務人身分證明文件
- 義務人印鑑證明
- 土地／建物所有權狀

**規則 G-1**：本模組僅產出**契約書文件**；地政士（代書）送件程序說明
屬知識層內容，禁止寫入契約本文。

---

# Part J：Clause Library（條款庫規格）

## J.1 Clause ID 編碼

```
CL-{MODULE}-{NNN}(-v{MAJOR})
     LOAN     001    v1
```

- `NNN`：001–099 = 必要條款；101–199 = 選用條款
- 版本省略時視為最新版；`final` 文件必須鎖定完整版本號

Regex：`^CL-[A-Z]{2,6}-\d{3}(-v\d+)?$`

## J.2 條款記錄 Schema

```yaml
clause_id: "CL-LOAN-003-v1"
name: "利息約定"
category: "required"
applies_to: ["contract.loan"]
legal_basis:
  - {law: "民法", article: "205", paragraph: 1, kb_id: "civil-0205"}
variables: ["{{Interest.Rate}}", "{{Interest.PayCycle}}"]
body: |
  第三條（利息）
  本借貸利息約定為週年利率百分之{{Interest.Rate}}，
  乙方應於{{Interest.PayCycle}}給付甲方。
validation: ["HV-07"]
version: "1.0.1"
status: "active"
deprecated_reason: null
```

**規則 J-1**：`legal_basis` 指向的法條經修正時，條款庫維護流程必須
將受影響條款標記 `deprecated` 並建立新版，禁止原地修改。
**規則 J-2**：同名同義條款禁止重複建立；新增前必須以 `name`＋`applies_to`
比對既有庫。

---

# Part L：Variable System（變數規格）

## L.1 命名規則

格式：`{{Namespace.Field}}`，PascalCase，Regex：
`^\{\{[A-Z][A-Za-z]*(\.[A-Z][A-Za-z]*)+\}\}$`

## L.2 v1.0 變數字典（normative，禁止自創）

| 變數 | 型別 | 驗證 Regex / 規則 |
|---|---|---|
| `{{PartyA.Name}}` | str | 非空 |
| `{{PartyA.ID}}` | str | `^[A-Z][12]\d{8}$`（自然人）或 `^\d{8}$`(法人統編) |
| `{{PartyA.Address}}` | str | 非空 |
| `{{PartyB.Name}}` / `.ID` / `.Address` | 同上 | 同上 |
| `{{Amount}}` | int | > 0，本文呈現為「新臺幣＋中文大寫＋元整」 |
| `{{Interest.Rate}}` | Decimal | 0 ≤ x ≤ 16（HV-07） |
| `{{Interest.PayCycle}}` | enum | 每月 / 每季 / 每年 / 到期一次 |
| `{{Loan.DeliveryDate}}` | ROC-date | 格式規則 L-2 |
| `{{Loan.MaturityDate}}` | ROC-date | 必須晚於 DeliveryDate（HV-08） |
| `{{Property.Parcel}}` | str | 段小段＋地號，非空 |
| `{{Building.No}}` | str \| null | 建號 |
| `{{Court}}` | str | 必須為現存地方法院名稱（知識層查核） |
| `{{Sign.Date}}` | ROC-date | 規則 L-2 |

**規則 L-1**：AI **禁止**自行生成任何個資類變數值
（Name / ID / Address）。未提供 → 保留 `{{...}}` 占位符並在
交付說明中列出待填清單，禁止以假資料填充。

**規則 L-2**：日期一律民國紀年：「中華民國一一四年七月六日」；
金額呈現：「新臺幣壹佰萬元整」。禁止西元、禁止阿拉伯數字金額出現於條款本文。

**規則 L-3**：文件中出現字典外變數 → 硬驗證 FAIL（HV-03）。

> ⚠️ **Pending P-06**：HV-04 個資防填充日誌機制尚待執行層實作。

---

# Part M：Validation Engine（雙層驗證）

## M.1 架構

```
生成完成
   ↓
Layer 1｜TLDS-HARD（確定性驗證，PASS / FAIL / PENDING〔test_mode only〕）
   ↓ 任一 FAIL → STOP + LOG（禁止重試繞過，須修正後重驗）
   ↓ 任一 PENDING（test_mode）→ delivery_blocked=true + LOG
Layer 2｜FEG_TLDS（品質評分閘門，1–5 分，外部 Judge）
   ↓
交付（DLV）
```

**設計依據**：法律正確性為二元性質（Fact），不得以分數放行；
品質維度（可讀性、格式）容許量化評分（Inference）。

**規則 M-1**：production 模式下 HV 僅允許 `PASS` / `FAIL`；
`PENDING` 僅可出現在 `test_mode=true`，且必須同時設定 `delivery_blocked=true`。

## M.2 Layer 1：硬驗證規則表（HV，全部 MUST PASS）

| ID | 規則 | 實作 |
|---|---|---|
| HV-01 | Metadata schema 合法 | Pydantic 驗證 §A.1 |
| HV-02 | doc_id / clause_id 格式合法 | §A.2 / §J.1 Regex |
| HV-03 | 所有變數屬於 §L.2 字典 | 字典比對 |
| HV-04 | 個資變數未被 AI 填充假值 | 生成日誌比對：值必須來自使用者輸入 |
| HV-05 | 必要條款齊備 | §F.1.2 / §G.1.2 清單比對 |
| HV-06 | 每一 legal_basis 的 kb_id 存在於知識層 | zhiyan-legal 查詢 |
| HV-07 | `{{Interest.Rate}}` ≤ 16 | 民法第 205 條 |
| HV-08 | 日期邏輯：清償期 > 交付日；立約日 ≤ 今日 | 日期比較 |
| HV-09 | 附件清單完整（MORT 模組） | §G.1.3 |
| HV-10 | 跨文件一致：LOAN 與 MORT 的金額、當事人相同 | 連動生成時 |
| HV-11 | 同一變數全文取值一致 | 全文掃描 |
| HV-12 | 最終 PDF 字體授權與嵌入合規（以 `pdffonts` 白名單比對為準，不以宣告層為準） | 規則 D-1 / D-3 |
| HV-13 | 簽章區完整且未跨頁 | 規則 B-2 |
| HV-14 | 契約本文不得出現驗證註解、測試標籤、執行層說明等 meta-text | 規則 G-1 類推 |

**規則 M-2**：HV-12 白名單至少應允許 `Noto Serif TC`、`Noto Sans TC`、`Noto Serif CJK TC`、`Noto Sans CJK TC` 之 subset 名稱；
若 `pdffonts` 輸出為 `WenQuanYi*`、`DejaVu*`、`Caladea*` 或任何非白名單字體，視為 FAIL。

**規則 M-3**：HV-13 機器驗證需以簽章區錨點字串（如 `印章：__________`、`立約日期：中華民國`）判定，排除前言中 `甲方` / `乙方` 誤判。

**規則 M-4**：HV-14 僅掃描契約本文區塊，不含 validation-log.json、頁尾頁碼或外部交付說明。

HV 失敗輸出格式：
`{"rule": "HV-07", "result": "FAIL", "detail": "...", "doc_id": "...", "ts": "..."}`
全部寫入審計 LOG，禁止靜默通過。

## M.3 Layer 2：FEG_TLDS（品質閘門）

```
FEG_TLDS[
D{A:條款完整度,B:變數填充度,C:結構合規,
  D:用字規範,E:風險標註,F:排版品質,G:機器可解析性};
S1..5;JUDGE=EXT;
PRE:HARD_PASS;
P:A4&B4&C4&D4&F3;
R:(A<4|B<4|C<4|D<4)&RTY<2;
Dg:E<3&G<3;
B:F<3|HARD_FAIL|RTY>=2;
M:P>DLV;R>RTY;Dg>SAFE;B>STOP+LOG
]
```

| 符號 | 語意 |
|---|---|
| `PRE:HARD_PASS` | Layer 1 全過為前置條件，否則不啟動 |
| `JUDGE=EXT` | 評分由獨立 Judge 模型執行（Council Synthesizer/Judge 層），**禁止生成模型自評** |
| `P` | 通過線：A、B、C、D ≥ 4 且 F ≥ 3 → 交付 |
| `R` | 重試：核心維度 < 4 且重試次數 < 2 → 回 REASON 重生成 |
| `RTY_MAX=2` | 重試上限，防無限迴圈 |
| `Dg` | 降級：E、G 同時 < 3 → SAFE 模式（交付＋顯著風險警示＋待補清單） |
| `B` | 中止：排版 < 3、或硬驗證失敗、或重試耗盡 → STOP＋LOG |

**維度評分基準（D 維度示例，1–5）**：
5 = 全文符合 fawu-zhiyan 用字規範且零禁用詞；
4 = 禁用詞 ≤ 2 且無 AI 自我指涉；
3 = 禁用詞 3–5；≤ 2 = 出現過度保證用語或西元日期。
（A–G 完整評分基準表由執行層實作時依此格式補齊，屬 v1.0.1 工作項。）

> ⚠️ **Pending P-04**：`committee/` EXT Judge 支援尚待確認。
> ⚠️ **Pending P-08**：A–G 七維度完整評分基準表為 v1.0.1 工作項，尚未補齊。

---

# Part N：Output Pipeline

```
TLDS Markdown（含 frontmatter）
   ↓ 變數解析（Part L）
   ↓ Layer 1 HV 驗證
DOCX（套用 §B.3 Styles，python-docx / docx skill）
   ↓ Layer 2 FEG_TLDS
PDF（LibreOffice headless 轉檔，字體 subset 嵌入，規則 D-3）
   ↓
交付：{doc_id}-v{version}.docx ＋ .pdf ＋ validation-log.json
```

**規則 N-1**：三個交付物版本號必須一致，validation-log.json 必附。
建議檔名格式統一為 `v1-0-1` 或 `v1.0.1` 之一，倉內不得混用多種版本分隔寫法。

**規則 N-2**：DOCX 與 PDF 頁數、頁碼、Header/Footer 必須一致（抽樣比對）。

> ⚠️ **Pending P-03**：`tests/test_tlds_hv.py` 尚未建立，HV-01 至 HV-14 單元測試待補。

---

# 附錄 Z：Roadmap（非規範內容）

| 版本 | 範圍 | 前置條件 |
|---|---|---|
| v1.0.1 | FEG_TLDS 七維度完整評分基準表＋HV-12/13/14 規則補強＋M-1 狀態語意修補 | v1.0 切片跑通 |
| v1.1 | 租賃、NDA、委任契約模組 | 條款庫流程驗證完成 |
| v1.2 | 法院書狀（依《司法狀紙要點》官方格式重建 Layout） | 🔴 律師法第 127 條風險評估：**B2B（律師事務所）限定**，禁止對消費者開放 |
| v1.3 | 最高限額抵押權、繼承登記等登記文件 | v1.0 MORT 模組實務回饋 |
| v2.0 | 電子簽署整合、企業法務文件 | — |

---

## 免責聲明

本規格所生成之文件為草稿性質，不構成法律意見。涉及具體法律爭議、
訴訟程序或高額交易，應諮詢執業律師或地政士。本聲明依智研系統政策
附於所有法律文件交付，不可省略。

---

*TLDS v1.0.1 Draft｜智研 ZhiYan｜MIT License*

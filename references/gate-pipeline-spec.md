# 智研閘門管線與工具驗證規格規範 (Gate Pipeline & Tool Verification Specification)

> **版本**：v1.0.0 (Phase 2 Approved Specification)  
> **模組路徑**：`src/zhiyan_legal/pipeline/` 與 `src/zhiyan_legal/tools/`  
> **單一事實來源**：本文件依據 `/tmp/drive_specs/` 之 `execution-contract.md`、`output-contract.md`、`tool-adapters.md` 制定，為 Phase 2 唯一可執行規格。

---

## 一、狀態機與單向流轉不變量 (State Machine & Directional Invariants)

```text
INTAKE -> SAFETY_ROUTE -> TASK_ROUTE -> PLAN -> RETRIEVE -> VERIFY
       -> ANALYZE -> QUALITY_GATE -> DECIDE

DECIDE -> DELIVER | ASK | SAFE | STOP | HUMAN_REVIEW
```

1. **嚴禁跳步不變量 (No-Bypass Invariant)**：
   嚴禁從 `INTAKE`、`TASK_ROUTE`、`RETRIEVE`、`VERIFY` 或 `ANALYZE` 直接進入 `DELIVER`。
2. **決策單調性 (Monotonic Strictness Lattice)**：
   $$\text{ALLOW (DELIVER: 0)} < \text{ABSTAIN (ASK: 1, SAFE: 1)} < \text{HUMAN\_REVIEW (2)} < \text{BLOCK (STOP: 3)}$$
   管線中任何 Gate 回傳之決策，僅能透過 `DecisionReducer.reduce()` 單調升級或維持嚴格度，嚴禁發生降級覆蓋。

---

## 二、能力三態與工具契約 (`src/zhiyan_legal/tools/base.py`)

### 1. 工具能力狀態 (Tool Capability State)

```python
class ToolCapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"       # 工具存在、已授權且通過唯讀連通性檢查
    UNAVAILABLE = "UNAVAILABLE"   # 工具不存在、未安裝或未連線
    FAILED = "FAILED"             # 已呼叫但錯誤、逾時或結果不可驗證
```

### 2. 工具執行結果契約 (ToolResult)

```python
class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str
    status: ToolCapabilityStatus
    raw_output: Any = None
    normalized_data: Any = None
    error_message: str | None = None
    executed_at: datetime
    execution_duration_ms: float = 0.0

    @property
    def is_usable(self) -> bool:
        return self.status == ToolCapabilityStatus.AVAILABLE and self.error_message is None
```

### 3. Fail-Closed 工具降級原則
- 若工具狀態為 `UNAVAILABLE` 或 `FAILED`，必須記錄 `error_message`，**嚴禁以模型記憶猜測補值並宣稱為已驗證資料**。
- 降級路徑：`官方來源驗證` $\to$ `可信非一手來源 (標註限制)` $\to$ `請求使用者補充 (ASK)` $\to$ `一般性安全說明 (SAFE)` $\to$ `停止處理 (STOP)`。

---

## 三、9 個程式化 Gate 詳細判定規格 (`src/zhiyan_legal/pipeline/gates.py`)

所有 Gate 必須實作統一純函式介面：
`evaluate(context: ExecutionContext) -> GateResult`

| Gate ID | 檢查標的與判定條件 | 通過條件 (passed=True) | 失敗判定 (passed=False) |
|---|---|---|---|
| **`G-SAFETY`** | 檢查 `context.user_goal` 是否涉及自殺、自殘、暴力犯罪指導或違法操作。<br>若 `task_mode == TaskMode.SAFETY` 或命中無條件高危詞，觸發安全防護。 | 無立即人身/違法安全風險。目標決策：`DELIVER` | 存在人身安全或違法風險。<br>目標決策：`STOP` (BLOCK) 或 `SAFE` (ABSTAIN) |
| **`G-JURISDICTION`** | 檢查 `context.jurisdiction`。<br>若是 `Jurisdiction.TW` 則通過；若是 `Jurisdiction.UNKNOWN` 或 `OTHER`，檢查是否有其他法域免責揭露。 | 確認為台灣法域。目標決策：`DELIVER` | 無法確認法域或跨國法域。<br>目標決策：`ASK` (請求釐清) 或 `SAFE` (一般說明) |
| **`G-FACTS`** | 檢查 `context.known_facts` 是否滿足特定任務之最低事實要件（Who/When/Where/What/Result）。 | 核心事實足以支持法律評價。目標決策：`DELIVER` | 缺乏行為人或核心關鍵情節。<br>目標決策：`ASK` (提示缺少之五要素) |
| **`G-SOURCE`** | 檢查 `context.claims` 中所有 `ClaimMateriality.CORE` 之命題，是否皆有 `context.evidence` 一手來源（法規/判決/官方文件）。 | 每個核心命題皆有一手來源定位。目標決策：`DELIVER` | 核心命題缺乏來源定位。<br>目標決策：`SAFE` 或 `STOP` (BLOCK) |
| **`G-SUPPORT`** | 檢查 `context.citations` 之 `exact_quote` 是否真實存在於對應 `Evidence.locator` 或來源全文中。 | 引註原文非空且實質支撐命題。目標決策：`DELIVER` | 來源內容與命題無關或無法支撐。<br>目標決策：`STOP` (BLOCK) |
| **`G-TEMPORAL`** | 檢查 `context.evidence` 之 `effective_at` 與適用時點，確認法規是否已廢止或修訂。 | 條文於案件時點現行有效。目標決策：`DELIVER` | 使用已廢止法規或修法時點不明。<br>目標決策：`SAFE` 或 `HUMAN_REVIEW` |
| **`G-CONFLICT`** | 檢查是否有針對同一法條/爭點之多個權威判決見解分歧，或來源間互相矛盾。 | 無未揭露之權威來源衝突。目標決策：`DELIVER` | 存在重大實務見解分歧或條文矛盾。<br>目標決策：`HUMAN_REVIEW` |
| **`G-HIGH-IMPACT`** | 檢查案件是否涉及重大刑事（七年以上/死刑）、人身自由限制、高額財產處分或強制執行書狀。 | 非高影響案件，或一般性法律諮詢。目標決策：`DELIVER` | 涉及重大權益不可逆處分。<br>目標決策：`HUMAN_REVIEW` (強制覆核) |
| **`G-OUTPUT`** | 檢查對外回應結構是否包含資訊狀態、法條依據、限制揭露與禁止聲明。 | 結構完整且無越權承諾。目標決策：`DELIVER` | 結構缺失或包含未驗證確定性保證。<br>目標決策：`SAFE` 或 `STOP` |

---

## 四、驗證管線與聚合器 (`src/zhiyan_legal/pipeline/runner.py`)

### 1. `GatePipeline` 執行流程
1. 依序執行 `G-SAFETY` $\to$ `G-JURISDICTION` $\to$ `G-FACTS` $\to$ `G-SOURCE` $\to$ `G-SUPPORT` $\to$ `G-TEMPORAL` $\to$ `G-CONFLICT` $\to$ `G-HIGH-IMPACT` $\to$ `G-OUTPUT`。
2. 每次評估產出 `GateResult`，並加入 `ExecutionContext.gate_results`。
3. 任何 Gate 回傳 `passed=False` 時，記錄原因與目標決策。
4. 最終呼叫 `DecisionReducer.reduce(context.gate_results)` 計算全域唯一終態決策 (`DeliveryDecision`, `DecisionStrictness`)。
5. 產出不可變之 `AnswerMeta` 與 `DecisionRecord`。

### 2. 測試規範 (`tests/pipeline/`)
- `test_gates.py`：逐一測試 9 個 Gate 的通過與失敗條件。
- `test_tool_result.py`：測試 ToolResult 三態與 Fail-closed 降級。
- `test_gate_pipeline.py`：端到端整合測試，驗證完整狀態機與決策單調收斂。

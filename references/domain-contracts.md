# 智研法律核心領域契約規範 (Canonical Domain Contracts)

> **版本**：v1.0.0 (Phase 1 Approved Specification)  
> **狀態**：APPROVED (經過 Z1-01-A 盤點、Z1-01-B 提案、Z1-01-C 審查三方收斂)  
> **模組路徑**：`src/zhiyan_legal/domain/`  
> **單一事實來源**：本文件為 zhiyan-legal 系統唯一可寫之核心領域模型契約基準。

---

## 1. 架構原則與全域不變量 (Global Invariants)

1. **單一可寫定義 (Single Writable Definition)**：
   每個 Canonical Type 只能在 `src/zhiyan_legal/domain/` 內具備一份可寫定義。其他模組僅能 Import 或 Re-export，嚴禁重複宣告。
2. **零外部污染 (Zero External Contamination)**：
   Domain 模組嚴禁 Import `fastapi`, `httpx`, `openai`, `google.genai`, `hermes`, `codex`, `agy` 等外部 SDK 或框架；嚴禁發送 HTTP、讀取環境變數或執行資料庫 I/O。
3. **決策單調不降級 (Decision Monotonic Strictness Lattice)**：
   $$\text{ALLOW (DELIVER: 0)} < \text{ABSTAIN (ASK: 1, SAFE: 2)} < \text{HUMAN\_REVIEW (3)} < \text{BLOCK (STOP: 4)}$$
   下游流程或後續 Gate 只能維持或提升決策嚴格度，嚴禁發生降級覆蓋。
4. **預設嚴格 Fail-Closed (Strict Fail-Closed Defaults)**：
   狀態預設值必須為未驗證（如 `UNVERIFIED`, `UNKNOWN`），決策預設必須為阻斷或等待評估，嚴禁使用 `ALLOW` 或 `VERIFIED` 作為缺失預設值。
5. **溯源不可孤兒 (No Orphan Core Claims)**：
   所有核心法律命題 (`Materiality.CORE`) 若標記為 `VERIFIED`，必須存在至少一筆有效關聯的 `Citation` 與 `Evidence`。
6. **人工覆核狀態化 (Stateful Human Review)**：
   `HUMAN_REVIEW` 為機器可識別的終態狀態與不可跳過流程，嚴禁降級為純文字警示字串。

---

## 2. 模組結構劃分

```text
src/zhiyan_legal/domain/
├── __init__.py          # 導出所有 Public Canonical Types
├── execution.py         # ExecutionStatus, ExecutionInput, ExecutionContext
├── evidence.py          # Evidence, EvidenceLevel, SourceType, VerificationStatus, Citation
├── claims.py            # Claim, ClaimKind, ClaimMateriality, ClaimStatus
├── decision.py          # DecisionStrictness, DeliveryDecision, DecisionReducer, AnswerMeta, DecisionRecord
└── risk.py              # RiskLevel, TaskMode, ProcedureStage, Jurisdiction
```

---

## 3. 型別詳細定義規範

### 3.1 基礎枚舉與識別碼 (`risk.py`, `decision.py`, `execution.py`)

```python
from enum import Enum, IntEnum
from typing import NewType

# 實體識別碼
ClaimId = NewType("ClaimId", str)
SourceId = NewType("SourceId", str)
CitationId = NewType("CitationId", str)

class Jurisdiction(str, Enum):
    TW = "TW"
    UNKNOWN = "UNKNOWN"
    OTHER = "OTHER"

class TaskMode(str, Enum):
    QC = "QC"
    RESEARCH = "RESEARCH"
    REPORT = "REPORT"
    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    LEGAL_DRAFT = "LEGAL_DRAFT"
    LITIGATION = "LITIGATION"
    TUTOR = "TUTOR"
    COURTROOM = "COURTROOM"
    SAFETY = "SAFETY"

class ProcedureStage(str, Enum):
    NONE = "NONE"
    FILED = "FILED"
    INVESTIGATION = "INVESTIGATION"
    TRIAL = "TRIAL"
    JUDGMENT = "JUDGMENT"
    ENFORCEMENT = "ENFORCEMENT"
    UNKNOWN = "UNKNOWN"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ExecutionStatus(str, Enum):
    INTAKE = "INTAKE"
    SAFETY_ROUTE = "SAFETY_ROUTE"
    TASK_ROUTE = "TASK_ROUTE"
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    VERIFY = "VERIFY"
    ANALYZE = "ANALYZE"
    QUALITY_GATE = "QUALITY_GATE"
    DECIDE = "DECIDE"

class DecisionStrictness(IntEnum):
    ALLOW = 0
    ABSTAIN = 1
    HUMAN_REVIEW = 2
    BLOCK = 3

class DeliveryDecision(str, Enum):
    DELIVER = "DELIVER"
    ASK = "ASK"
    SAFE = "SAFE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STOP = "STOP"

    @property
    def strictness(self) -> DecisionStrictness:
        if self == DeliveryDecision.DELIVER:
            return DecisionStrictness.ALLOW
        if self in (DeliveryDecision.ASK, DeliveryDecision.SAFE):
            return DecisionStrictness.ABSTAIN
        if self == DeliveryDecision.HUMAN_REVIEW:
            return DecisionStrictness.HUMAN_REVIEW
        return DecisionStrictness.BLOCK
```

### 3.2 Claim 與 Evidence 契約 (`claims.py`, `evidence.py`)

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ClaimKind(str, Enum):
    FACT = "FACT"
    LAW = "LAW"
    INFERENCE = "INFERENCE"
    PROCEDURE = "PROCEDURE"
    RISK = "RISK"

class ClaimMateriality(str, Enum):
    CORE = "CORE"
    SUPPORTING = "SUPPORTING"

class ClaimStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"
    STALE = "STALE"

class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: ClaimId
    text: str = Field(min_length=1)
    kind: ClaimKind
    materiality: ClaimMateriality = ClaimMateriality.SUPPORTING
    status: ClaimStatus = ClaimStatus.UNVERIFIED

class SourceType(str, Enum):
    STATUTE = "STATUTE"
    JUDGMENT = "JUDGMENT"
    OFFICIAL = "OFFICIAL"
    ACADEMIC = "ACADEMIC"
    USER_FILE = "USER_FILE"
    USER_REPORTED = "USER_REPORTED"

class EvidenceLevel(str, Enum):
    VERIFIED = "VERIFIED"
    CROSS_REFERENCED = "CROSS_REFERENCED"
    USER_REPORTED = "USER_REPORTED"
    NEED_CHECK = "NEED_CHECK"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"

class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: SourceId
    source_type: SourceType
    title: str
    locator: str
    jurisdiction: Jurisdiction = Jurisdiction.TW
    retrieved_at: datetime
    effective_at: datetime | None = None
    supports_claims: list[ClaimId] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    level: EvidenceLevel = EvidenceLevel.NEED_CHECK

class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_id: CitationId
    claim_id: ClaimId
    source_id: SourceId
    locator: str
    exact_quote: str = Field(description="來源精確字句摘錄")
    evidence_level: EvidenceLevel
    verified_at: datetime
```

### 3.3 閘門結果與決策聚合器 (`decision.py`, `execution.py`)

```python
class GateId(str, Enum):
    G_SAFETY = "G-SAFETY"
    G_JURISDICTION = "G-JURISDICTION"
    G_FACTS = "G-FACTS"
    G_SOURCE = "G-SOURCE"
    G_SUPPORT = "G-SUPPORT"
    G_TEMPORAL = "G-TEMPORAL"
    G_CONFLICT = "G-CONFLICT"
    G_HIGH_IMPACT = "G-HIGH-IMPACT"
    G_OUTPUT = "G-OUTPUT"

class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: GateId
    passed: bool
    reason: str
    target_decision: DeliveryDecision
    evaluated_at: datetime

    @property
    def strictness(self) -> DecisionStrictness:
        return self.target_decision.strictness

class DecisionReducer:
    """純函數單調決策聚合器：只能升級嚴格度，不可降級"""
    @staticmethod
    def reduce(gate_results: list[GateResult]) -> tuple[DeliveryDecision, DecisionStrictness]:
        if not gate_results:
            return DeliveryDecision.STOP, DecisionStrictness.BLOCK
        
        highest_strictness = max(r.strictness for r in gate_results)
        for r in gate_results:
            if r.strictness == highest_strictness:
                return r.target_decision, highest_strictness
        return DeliveryDecision.STOP, DecisionStrictness.BLOCK

class AnswerMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    decision: DeliveryDecision
    strictness_level: DecisionStrictness
    task_mode: TaskMode
    risk_level: RiskLevel
    verified_claim_ids: list[ClaimId] = Field(default_factory=list)
    unverified_claim_ids: list[ClaimId] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    tool_failures: list[str] = Field(default_factory=list)
    human_review_required: bool = False
```

### 3.4 執行上下文聚合根 (`execution.py`)

```python
class ExecutionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    status: ExecutionStatus = ExecutionStatus.INTAKE
    jurisdiction: Jurisdiction = Jurisdiction.TW
    task_mode: TaskMode = TaskMode.QC
    procedure_stage: ProcedureStage = ProcedureStage.NONE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    user_goal: str
    known_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)

    @property
    def current_decision(self) -> DeliveryDecision:
        decision, _ = DecisionReducer.reduce(self.gate_results)
        return decision

    @property
    def current_strictness(self) -> DecisionStrictness:
        _, strictness = DecisionReducer.reduce(self.gate_results)
        return strictness
```

---

## 4. 向後相容性與 Adapter 設計規範

1. **`committee.core.LegalClaim`**：
   保留原有資料結構作為合議庭專用模型，並在 `committee/mapper.py` 或獨立 adapter 模組中提供 `to_canonical_claim()` 與 `from_canonical_claim()` 轉換函數。
2. **`src/zhiyan_legal/schemas/judgment.py`**：
   作為判決書資料庫/Retrieval 專屬 Domain 模型，提供 `JudgmentDocument.to_canonical_evidence()` 介面，將法院判決結構化投影為 `Evidence`。
3. **`committee/prompt_optimization/quality_gate.py`**：
   將提示詞工程專用之閘門結果重命名/別名為 `PromptGateResult`，避免與核心 `GateResult` 發生命名衝突。
4. **`sdk.models.QueryResponse`**：
   提供 `from_domain(context: ExecutionContext, meta: AnswerMeta) -> QueryResponse` 工廠方法，確保現有 API 客戶端無感升級。

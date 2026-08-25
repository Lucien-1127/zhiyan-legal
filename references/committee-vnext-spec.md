# 智研多模型合議庭契約規範 (Multi-model Committee vNext Specification)

> **版本**：v1.0.0 (Phase 4 Approved Specification)  
> **模組路徑**：`src/zhiyan_legal/committee/` 與 `src/zhiyan_legal/application/`  
> **單一事實來源**：本文件依據 Phase 0 審計、Drive 契約規範 (`execution-contract.md`, `tool-adapters.md`) 與全域不變量制定。

---

## 一、Phase 4 核心契約原則與不可覆寫規則

1. **模型投票不得覆蓋事實閘門 (Committee Majority Cannot Override Deterministic Gates)**：
   - 即使 100% 的模型一致投票通過，**絕對不得將未經 Evidence/Citation 驗證的 `ClaimStatus.UNVERIFIED` 命題升級為 `VERIFIED`**。
   - 合議庭（Committee）僅提供**候選分析（Candidate Analysis）**與**見解共識/分歧標示**，不可替代確定性 Gate 進行最終決定。
2. **決策嚴格度單調性保證 (Monotonic Strictness)**：
   - 合議庭產出之分歧 (`DISAGREEMENT`) 或盲區 (`BLIND_SPOT`) 僅能將系統決策升級為 `HUMAN_REVIEW` 或 `STOP`，嚴禁將已觸發的 Gate 阻斷降級為 `ALLOW`。
3. **部分失敗容錯 (Partial Failure Tolerance)**：
   - 單一席次 Provider 發生 429、逾時或連線異常時，記錄 `PARTIAL_FAILURE`，不得導致整個合議庭崩潰，亦不得將失敗偽裝為 PASS 或共識。
4. **與 ProviderRegistry / Canonical Domain 深度整合**：
   - 合議席次統一由 `ProviderRegistry` 調度，支援角色分配 (`DRAFTER`, `VERIFIER`, `CRITIC`)。
   - 所有 Claim 映射至 Canonical `Claim`，嚴防雙軌語意分裂。

---

## 二、合議庭資料結構與輸出契約 (`src/zhiyan_legal/committee/`)

```python
class ConsensusStatus(str, Enum):
    CONSENSUS = "CONSENSUS"           # 全體模型見解一致
    DISAGREEMENT = "DISAGREEMENT"     # 模型間存在實質分歧 (轉入 HUMAN_REVIEW)
    BLIND_SPOT = "BLIND_SPOT"         # 全體模型皆判定錯誤/無依據 (轉入 STOP)
    PARTIAL_FAILURE = "PARTIAL_FAILURE" # 部分席次異常，但在法定人數 (Quorum) 下完成

class CommitteeMemberVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_name: str
    model: str
    role: ProviderRole
    claims: list[Claim] = Field(default_factory=list)
    verdict: str
    confidence: float = 1.0
    error: str | None = None

class CommitteeReportVNext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    status: ConsensusStatus
    member_verdicts: list[CommitteeMemberVerdict]
    consensus_claims: list[Claim] = Field(default_factory=list)
    divergent_claims: list[Claim] = Field(default_factory=list)
    recommended_decision: DeliveryDecision
    recommended_strictness: DecisionStrictness
    evaluated_at: datetime
```

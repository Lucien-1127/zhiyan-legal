# 智研應用引擎與供應商抽象規格規範 (Application Engine, Interfaces & Providers Specification)

> **版本**：v1.0.0 (Phase 3 Approved Specification)  
> **模組路徑**：`src/zhiyan_legal/providers/`、`src/zhiyan_legal/application/`、`src/zhiyan_legal/interfaces/`  
> **單一事實來源**：本文件依據 Phase 0 審計 (ZHIYAN-F-0003, F-0010, F-0011, F-0012, F-0017) 與 Drive 規格制定，為 Phase 3 唯一可執行規範。

---

## 一、Phase 3 核心目標與待消除缺陷

1. **消除 `fake-success` 與裸奔 LLM (ZHIYAN-F-0003)**：
   - 外部介面（FastAPI `/api/chat`、CLI、SDK）嚴禁直連 LLM，必須由 `ZhiyanApplicationEngine` 作為唯一協調器（Orchestrator）。
   - 任何請求必須先經由 GatePipeline 評估；若發生 Provider 錯誤或 Gate 失敗，嚴禁回傳 HTTP 200 空內容，必須回傳結構化錯誤碼或受控降級狀態。
2. **統一 Provider Abstraction 與安全 Key Discovery (ZHIYAN-F-0010)**：
   - 徹底消除直接讀取 `~/.hermes/profiles/` 或透過 `subprocess grep` 解析主機檔案的危險行為。
   - 統一透過顯式注入的 `ProviderConfig` / 標準環境變數解析金鑰。
   - 實現標準化 Provider Adapter：統一輸入 (`role: DRAFTER|VERIFIER|CRITIC`, `instructions`, `evidence_ids`, `output_schema`)。
   - 跨 Provider fallback 必須明確區分 base_url 與 model，嚴禁以 OpenAI 端點搭配 DeepSeek key 產生語意錯亂。
3. **消除 Engine 內部執行路徑分裂 (ZHIYAN-F-0011)**：
   - 消除重複定義之 `load_docs` 與 `reload`。
   - 嚴格檢查 `conversation_history` 中每筆訊息之 `role`，禁止使用者輸入包含 `role: "system"`，防止指令注入升級。
   - 429 Key 輪換與重試機制必須與真實 SDK 異常類型對齊，非裝飾性。
4. **介面邊界隔離 (ZHIYAN-F-0012, F-0017)**：
   - 移除 `regulation_api.py` 內嵌於 domain/core 的 FastAPI 反向依賴，將所有 HTTP 端點收斂至 `interfaces/`。
   - `backend/main.py` 與 `src/zhiyan_legal/sdk/` 透過純 Application Service 互動。

---

## 二、Provider 抽象與金鑰管理架構 (`src/zhiyan_legal/providers/`)

```python
class ProviderRole(str, Enum):
    DRAFTER = "DRAFTER"
    VERIFIER = "VERIFIER"
    CRITIC = "CRITIC"

class ProviderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    role: ProviderRole = ProviderRole.DRAFTER
    instructions: str
    evidence_ids: list[str] = Field(default_factory=list)
    output_schema: str = "default"
    timeout_seconds: float = 60.0

class ProviderResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    content: str
    model: str
    provider_name: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str | None = None
```

---

## 三、應用引擎架構 (`src/zhiyan_legal/application/`)

```python
class ZhiyanApplicationEngine:
    """唯一應用協調器：持有狀態機、驅動檢索與驗證、執行 GatePipeline、協調 Provider"""

    def __init__(
        self,
        gate_pipeline: GatePipeline | None = None,
        provider_registry: ProviderRegistry | None = None,
        tool_adapters: list[BaseToolAdapter] | None = None,
    ):
        self.pipeline = gate_pipeline or GatePipeline()
        self.registry = provider_registry or ProviderRegistry.from_env()
        self.tools = tool_adapters or []

    async def execute(self, context: ExecutionContext) -> tuple[ExecutionContext, AnswerMeta, str]:
        # 1. 執行 Gate 評估 (G-SAFETY, G-JURISDICTION, G-FACTS, etc.)
        working_context, decision_record, meta = self.pipeline.run(context)

        # 2. 若決策為 STOP / SAFE / ASK / HUMAN_REVIEW，受控終止並回傳說明，禁止直呼 LLM
        if meta.decision in (DeliveryDecision.STOP, DeliveryDecision.ASK, DeliveryDecision.SAFE):
            return working_context, meta, self._generate_controlled_response(meta)

        # 3. 若通過 Gate (ALLOW)，調用經核准之 Provider
        response = await self._call_provider(working_context)
        return working_context, meta, response
```

# FEG_COMMITTEE — 多模型合議庭輸出品質閘門 v1.0.0

**建立日期**：2026-07-05  
**適用版本**：zhiyan-legal v3.09+  
**整合目標**：`committee/runner.py` → `run_committee()` 回傳後、結果輸出前  

---

## 定位與角色

FEG_COMMITTEE 是第三層品質閘門，專責評估**多模型合議結果**的可信度與可送出性。

```
SKILL.md L1 FEG_CORE_EXTREME   ← 第一層：單模型輸出品質（法律邏輯）
LEGAL_WRITER FEG_WRITING        ← 第二層：寫作人格文字品質
committee/ FEG_COMMITTEE        ← 第三層：合議庭結果品質（本文件）
```

三層閘門**串聯執行**，任一層 STOP 即終止，不進入下一層。

---

## 與 core.py 的映射關係

`committee/core.py` 定義的四態標記與 FEG 路由**天然對應**：

| ConsensusLabel | 語意 | FEG 路由 | 說明 |
|:--------------:|------|:--------:|------|
| `CONSENSUS` | 所有模型一致 ✅ | **DLV** | 通過，直接送出 |
| `DISAGREEMENT` | 模型間分歧 ⚠️ | **ASK** | 先回報分歧，請使用者確認 |
| `BLIND_SPOT` | 所有模型都錯 ❌ | **STOP** | 強制中止，不得送出 |
| `UNIQUE_INSIGHT` | 僅單一模型提出 🔍 | **驗證** | 觸發 VM 幻覺驗證流程 |

---

## FEG_COMMITTEE 符號定義

```
FEG_COMMITTEE[
  D{A:引用一致,B:推理一致,C:覆蓋完整,D:任務對齊,E:共識品質,F:安全合規,G:報告格式};
  S1..5;
  P:A4&B4&C4&D4&F3;
  R:A<4|B<4|C<4|D<4;
  Dg:E<3&G<3;
  C:DISAGREEMENT|RM|FU;
  B:F<3|BLIND_SPOT|BH|QF;
  V:UNIQUE_INSIGHT?(SCH=VMS&VAR3&NEG1):OK;
  M:P→DLV;R→RTY;Dg→SAFE;C→ASK;B→STOP
]
```

**觸發時機**：`run_committee()` 收到所有模型結果後、`CommitteeReport` 輸出前，強制執行。  
**重試上限**：RTY 最多 2 次，仍未通過 → 降為 SAFE 模式。  

---

## 路由優先序（由高到低）

| 優先 | 條件 | 動作 | 說明 |
|:----:|------|:----:|------|
| 1 | `F<3` 或 `BLIND_SPOT/BH/QF` | 🔴 STOP | 安全違規或所有模型皆錯，強制中止 |
| 2 | `DISAGREEMENT/RM/FU` | 🟡 ASK | 模型分歧或高風險法域，先回報再繼續 |
| 3 | `UNIQUE_INSIGHT` | 🔍 驗證 | 觸發 Schema 校驗 + 3 來源 + 1 反例 |
| 4 | `A<4\|B<4\|C<4\|D<4` | 🔄 RTY | 核心維度失分，重新執行（最多 2 次） |
| 5 | `E<3 且 G<3` | 🟡 SAFE | 共識品質＋報告格式雙失，降級簡報 |
| 6 | 全部通過 | 🟢 DLV | 送出 CommitteeReport |

---

## 七維評分速查表

| 維度 | 名稱 | 通過門檻 | S1（最低）→ S5（最高）關鍵錨點 |
|:----:|------|:--------:|-------------------------------|
| A | 引用一致性 | ≥4 | 1=各模型引用互相矛盾 / 3=條號一致但內容有歧義 / 5=所有模型引用完全一致可交叉驗證 |
| B | 推理一致性 | ≥4 | 1=推理方向相反 / 3=主線一致但有一處分歧 / 5=推理鏈方向與步驟完全一致 |
| C | 覆蓋完整性 | ≥4 | 1=重要 claim 無任何模型提及 / 3=覆蓋主要 claim 但有缺口 / 5=所有必要 claim 至少一模型覆蓋 |
| D | 任務對齊 | ≥4 | 1=合議結論答非所問 / 3=部分偏移查詢核心 / 5=合議結論完全切題 |
| E | 共識品質 | —（Dg） | 1=共識結論語意不清 / 3=可理解但表達粗糙 / 5=共識結論精準流暢 |
| F | 安全合規 | ≥3 | 1=任一模型給出個案意見或安全違規 / 3=提示不完整 / 5=所有模型完全合規 |
| G | 報告格式 | —（Dg） | 1=CommitteeReport 結構不完整 / 3=部分欄位缺失 / 5=所有欄位完整，JSON 可直接解析 |

> **特殊停止旗標**：  
> `BLIND_SPOT` = 所有模型對同一 claim 均判定錯誤（來自 core.py ConsensusLabel）  
> `BH` = 合議結論可能對使用者造成實質傷害  
> `QF` = 報告品質全面崩潰（多個核心維度 S1）  
>
> **確認旗標**：  
> `DISAGREEMENT` = 模型間出現實質分歧（來自 core.py ConsensusLabel）  
> `RM` = 查詢涉及高風險法域（憲法、刑事、家事）  
> `FU` = 來源追蹤失敗，無法驗證任何模型引用  

---

## runner.py 整合規格

### 插入點

```python
# committee/runner.py — run_committee() 末尾插入

def run_committee(
    queries: List[Dict],
    models: Optional[List[ModelConfig]] = None,
    condition: str = "A",
    max_workers: int = 3,
) -> Dict[str, List[ModelVerdict]]:
    # ... 現有平行執行邏輯（不動）...

    # ★ FEG_COMMITTEE 閘門（新增）
    feg_result = evaluate_feg_committee(results, queries)
    if feg_result["action"] == "STOP":
        raise CommitteeHaltError(
            reason=feg_result["reason"],
            trigger=feg_result["trigger"]
        )
    elif feg_result["action"] == "ASK":
        logger.warning("[FEG_COMMITTEE] ASK triggered: %s", feg_result["reason"])
        # 回傳時附加 feg_meta，讓上層決定是否繼續
        results["__feg_meta__"] = feg_result

    return results
```

### evaluate_feg_committee() 輸出格式

```python
{
    "action": "DLV" | "RTY" | "SAFE" | "ASK" | "STOP",
    "trigger": "BLIND_SPOT" | "DISAGREEMENT" | "UNIQUE_INSIGHT" | "LOW_SCORE" | None,
    "scores": {
        "A": 1-5,  # 引用一致性
        "B": 1-5,  # 推理一致性
        "C": 1-5,  # 覆蓋完整性
        "D": 1-5,  # 任務對齊
        "E": 1-5,  # 共識品質
        "F": 1-5,  # 安全合規
        "G": 1-5,  # 報告格式
    },
    "reason": "<人類可讀說明>",
    "retry_count": 0
}
```

### 例外類別（新增至 core.py）

```python
class CommitteeHaltError(Exception):
    """FEG_COMMITTEE 觸發 STOP 時拋出。"""
    def __init__(self, reason: str, trigger: str):
        self.reason = reason
        self.trigger = trigger
        super().__init__(f"[FEG_COMMITTEE STOP] trigger={trigger}: {reason}")
```

---

## BLIND_SPOT 行為規格（重點補完）

現有架構定義了 `BLIND_SPOT` 標記，但**未定義觸發後的行為**。本文件明確規定：

```
BLIND_SPOT 觸發時：
  1. 不得將合議結論送出給使用者
  2. 必須拋出 CommitteeHaltError
  3. 寫入 audit_log（action=COMMITTEE_HALT, trigger=BLIND_SPOT）
  4. 送 Telegram 告警（含 query_id、blind_spot_count、受影響條號）
  5. 回傳使用者：「本次查詢偵測到所有模型一致錯誤，已中止，請重新描述問題或諮詢專業律師。」
```

---

## 與現有架構的完整串聯

```
run_committee()（平行執行 3 模型）
    ↓
CommitteeReport 生成（core.py）
    ↓
FEG_COMMITTEE 評分（本文件）
    ├── BLIND_SPOT → CommitteeHaltError → STOP
    ├── DISAGREEMENT → ASK（附 feg_meta 回傳）
    ├── UNIQUE_INSIGHT → VM 驗證流程
    ├── RTY → 重新執行（max 2 次）
    └── DLV → 送出 CommitteeReport
            ↓
        （若 task_mode=contract）
        FEG_WRITING（文字品質層）
            ↓
        最終輸出
```

---

## 版本記錄

```
v1.0.0 (2026-07-05)
  + 初始版本
  + 七維評分速查表（A:引用一致 ~ G:報告格式）
  + BLIND_SPOT→STOP 行為明確規格
  + runner.py 整合規格（插入點 + 輸出格式 + CommitteeHaltError）
  + 三層 FEG 串聯架構圖
```

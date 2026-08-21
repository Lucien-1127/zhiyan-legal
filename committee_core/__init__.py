# ⚠️  committee_core 已於 v3.9.5 廢棄，請改用 committee.policies / committee.reasoning
# Deprecated since v3.9.5 — will be removed in v4.0
"""
向後相容 shim：將 committee_core 所有公開符號轉發至新位置。
下一個主要版本（v4.0）將删除此目錄。
"""
from committee.policies import (  # noqa: F401
    GovernanceContract,
    GovernanceViolationError,
    PolicyViolation,
)
from committee.reasoning import (  # noqa: F401
    DebateEngine,
    JudicialScraper,
)

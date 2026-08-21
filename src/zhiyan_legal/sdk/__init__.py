"""
zhiyan_legal.sdk — Zhiyan Legal AI 公開 SDK v1.0.0

一行引入即可使用：
    from zhiyan_legal.sdk import ZhiyanClient

    client = ZhiyanClient()  # 自動讀取 .env
    result = client.query("什麼是公然侮辱？")
    print(result.content)
"""

from .client import ZhiyanClient
from .models import QueryRequest, QueryResponse, CommitteeResponse, ProviderInfo
from .exceptions import ZhiyanAPIError, ZhiyanAuthError, ZhiyanTimeoutError

__version__ = "1.0.0"

__all__ = [
    "ZhiyanClient",
    "QueryRequest",
    "QueryResponse",
    "CommitteeResponse",
    "ProviderInfo",
    "ZhiyanAPIError",
    "ZhiyanAuthError",
    "ZhiyanTimeoutError",
]

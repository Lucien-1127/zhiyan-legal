"""
zhiyan_legal.sdk.exceptions — SDK 異常定義
"""
from __future__ import annotations


class ZhiyanSDKError(Exception):
    """SDK 基礎異常。"""


class ZhiyanAPIError(ZhiyanSDKError):
    """API 回應錯誤（HTTP 4xx/5xx）。"""
    def __init__(self, message: str, status_code: int = 0, provider: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


class ZhiyanAuthError(ZhiyanAPIError):
    """API 金鑰缺失或無權（HTTP 401/403）。"""


class ZhiyanTimeoutError(ZhiyanSDKError):
    """API 請求逾時。"""
    def __init__(self, provider: str = "", timeout_s: float = 0.0):
        super().__init__(f"請求逾時 [{provider}] ({timeout_s:.1f}s)")
        self.provider = provider
        self.timeout_s = timeout_s


class ZhiyanRouterError(ZhiyanSDKError):
    """API 路由器無可用提供商。"""

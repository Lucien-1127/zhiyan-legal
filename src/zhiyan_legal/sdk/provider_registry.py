"""
zhiyan_legal.sdk.provider_registry — 提供商注冊表

所有外部 API 提供商的連線配置在此統一管理。
新增提供商只需在 PROVIDER_REGISTRY 新增一條。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from zhiyan_legal.config import settings


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str
    priority: int          # 數字越小越優先
    timeout: float = 60.0
    is_primary: bool = False


def _build_registry() -> list[ProviderConfig]:
    """Runtime 建立提供商清單，依賴 settings singleton。"""
    registry: list[ProviderConfig] = []

    # ① Zhiyan 本公司 API（最高優先度，所有請求首先導向此處）
    if settings.api_key:
        registry.append(ProviderConfig(
            name="zhiyan",
            base_url=settings.api_base_url,       # 預設: https://api.openai.com/v1
            api_key=settings.api_key,
            default_model=settings.model,
            priority=0,
            is_primary=True,
        ))

    # ② Agnes AI（合議庭席次 1）
    if settings.agnes_key_1:
        registry.append(ProviderConfig(
            name="agnes",
            base_url=settings.agnes_base_url,
            api_key=settings.agnes_key_1,
            default_model=settings.agnes_model,
            priority=1,
        ))

    # ③ Agnes AI Key2（合議庭席次 2）
    if settings.agnes_key_2:
        registry.append(ProviderConfig(
            name="agnes",
            base_url=settings.agnes_base_url,
            api_key=settings.agnes_key_2,
            default_model=settings.agnes_model,
            priority=2,
        ))

    # ④ Gemini（合議庭席次 3）
    if settings.gemini_api_key:
        registry.append(ProviderConfig(
            name="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=settings.gemini_api_key,
            default_model=settings.gemini_model,
            priority=3,
        ))

    # 按 priority 排序
    registry.sort(key=lambda p: p.priority)
    return registry


# Singleton registry
PROVIDER_REGISTRY: list[ProviderConfig] = _build_registry()


def get_primary() -> Optional[ProviderConfig]:
    """Return the primary (zhiyan) provider, or None."""
    for p in PROVIDER_REGISTRY:
        if p.is_primary:
            return p
    return PROVIDER_REGISTRY[0] if PROVIDER_REGISTRY else None


def get_committee_providers() -> list[ProviderConfig]:
    """Return all non-primary providers for committee use."""
    return [p for p in PROVIDER_REGISTRY if not p.is_primary]


def list_providers() -> list[str]:
    """Return names of all configured providers."""
    return [p.name for p in PROVIDER_REGISTRY]

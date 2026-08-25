"""Canonical legal claim types."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .risk import ClaimId


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


__all__ = [
    "ClaimId",
    "ClaimKind",
    "ClaimMateriality",
    "ClaimStatus",
    "Claim",
]

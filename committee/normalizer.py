"""三層正規化器 — 將不同模型的表述統一為標準格式。

Layer A — 用語正規化 (Terminology Normalization)
  已刪除 / 已廢止 / 非現行法 → STATUS_DELETED
  不存在 / 查無 / 非合法條號 → STATUS_NONEXISTENT

Layer B — 條號正規化 (Citation Normalization)
  "釋字 812 號" → "釋字第812號"
  "§987" → "民法第987條"

Layer C — 語意兜底 (Semantic Fallback)
  若字串正規化後仍無法比對 → 用 difflib 相似度
"""

from __future__ import annotations

import re
import difflib
from typing import Dict, List, Optional, Tuple

from .core import LegalClaim, ClaimType, ClaimStatus


# ═══════════════════════════════════════════════════════════════
# Layer A — 用語正規化詞典
# ═══════════════════════════════════════════════════════════════

# 已刪除/已廢止 同義表述
STATUS_DELETED_PATTERNS: List[str] = [
    r"已刪除", r"已廢止", r"已廢除", r"已失效",
    r"非現行(法|條文)?", r"不再適用", r"經刪除",
    r"刪除(了)?", r"廢止(了)?", r"不再有效",
    r"2007.*刪除", r"2007.*廢止", r"刪除.*2007",
    r"已不復存在", r"已不存在", r"非現行條文",
    r"不具效力", r"已無效", r"效力已喪失",
]

# 不存在/查無 同義表述
STATUS_NONEXISTENT_PATTERNS: List[str] = [
    r"不存在", r"查無此條號", r"查無此條文",
    r"非合法?條號", r"非民法條號", r"未在民法.*範圍",
    r"超出.*§1.*§1225", r"超出.*第1條.*第1225條",
    r"並無此條號", r"無此條號", r"無.*此條(文|號)",
    r"不在民法.*範圍", r"未收錄", r"查無",
    r"沒有.*這個.*條(文|號)",
]

# 已修訂 同義表述
STATUS_AMENDED_PATTERNS: List[str] = [
    r"已修訂", r"已修正", r"已修改", r"經修(正|訂)",
    r"已於.*年修(正|訂)", r"修(正|訂).*後",
    r"現行(法|條文).*修正", r"非原條文",
]

# API 失敗模式
API_ERROR_PATTERNS: List[str] = [
    r"API 呼叫失敗", r"RateLimited", r"429",
    r"RESOURCE_EXHAUSTED", r"quota exceeded",
    r"retry", r"Too Many Requests",
    r"API call failed", r"error",
]

# Safety unknown 模式 (Gemini 等 model 因安全機制拒絕回答)
SAFETY_UNKNOWN_PATTERNS: List[str] = [
    r"無法確認", r"不在.*範圍", r"無法提供",
    r"I cannot verify", r"I cannot answer",
    r"outside.*scope", r"cannot confirm",
    r"I'm unable to", r"I am unable to",
    r"抱歉.*無法", r"無法回答",
    r"安全.*限制", r"safety.*reason",
]


def _match_status_with_confidence(text: str) -> Tuple[Optional[ClaimStatus], float]:
    """判別文字狀態並回傳 (status, confidence)。

    信心度 = min(0.3 + 每多一個 pattern 命中加 0.15, 0.9)。
    優先序：ERROR > DELETED > NONEXISTENT > AMENDED > SAFETY_UNKNOWN
    """
    if not text or len(text.strip()) < 5:
        return ClaimStatus.ERROR, 0.9

    for pat in API_ERROR_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return ClaimStatus.ERROR, 0.9

    for patterns, status in [
        (STATUS_DELETED_PATTERNS, ClaimStatus.DELETED),
        (STATUS_NONEXISTENT_PATTERNS, ClaimStatus.NONEXISTENT),
        (STATUS_AMENDED_PATTERNS, ClaimStatus.AMENDED),
    ]:
        count = sum(1 for p in patterns if re.search(p, text))
        if count:
            return status, min(0.3 + count * 0.15, 0.9)

    count = sum(1 for p in SAFETY_UNKNOWN_PATTERNS if re.search(p, text, re.IGNORECASE))
    if count:
        return ClaimStatus.SAFETY_UNKNOWN, min(0.3 + count * 0.15, 0.9)

    return None, 0.0


def _match_status(text: str) -> Optional[ClaimStatus]:
    """對一段文字進行用語正規化，判別其狀態。(backward-compat wrapper)"""
    status, _ = _match_status_with_confidence(text)
    return status

def _match_status(text: str) -> Optional[ClaimStatus]:
    """對一段文字進行用語正規化，判別其狀態。

    優先序：ERROR > DELETED > NONEXISTENT > AMENDED > SAFETY_UNKNOWN
    """
    # 1. 空文字 → 直接 ERROR
    if not text or len(text.strip()) < 5:
        return ClaimStatus.ERROR

    # 2. API 錯誤 → ERROR
    for pat in API_ERROR_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return ClaimStatus.ERROR

    # 3. 實質判定
    for pat in STATUS_DELETED_PATTERNS:
        if re.search(pat, text):
            return ClaimStatus.DELETED
    for pat in STATUS_NONEXISTENT_PATTERNS:
        if re.search(pat, text):
            return ClaimStatus.NONEXISTENT
    for pat in STATUS_AMENDED_PATTERNS:
        if re.search(pat, text):
            return ClaimStatus.AMENDED
    for pat in SAFETY_UNKNOWN_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return ClaimStatus.SAFETY_UNKNOWN
    return None


# ═══════════════════════════════════════════════════════════════
# Layer B — 條號正規化
# ═══════════════════════════════════════════════════════════════

# 民法條號: 民法第XXX條 / 第XXX條 / §XXX
ARTICLE_RE = re.compile(r"""
    (?:民法|民)?                                # optional prefix
    (?:第\s*)?                                  # optional "第"
    (\d+(?:[之\-]\d+)?(?:條之\d+)?)             # article number
    (?:\s*條)?                                  # optional "條"
""", re.VERBOSE | re.IGNORECASE)

# 判決字號: XXX年度XX字第XXXX號 / XXX台上XXXX號
PRECEDENT_RE = re.compile(r"""
    (\d+(?:年度)?)                               # year
    \s*
    (?:台上|抗|聲|訴|簡上|交抗|勞上|家上|刑上|審|易|簡|訴字第|易字第|簡上字第|交抗字第|勞上字第)
    \s*
    (\d+)
    \s*號?
""", re.VERBOSE | re.IGNORECASE)

# 釋字: 釋字第XXX號 / 釋字 XXX 號 / 釋XXX號
INTERPRETATION_RE = re.compile(r"""
    釋(?:字)?\s*                                # "釋" or "釋字"
    (?:第\s*)?                                  # optional "第"
    (\d+(?:之\d+)?)                             # number
    \s*號
""", re.VERBOSE | re.IGNORECASE)

# 司法院解釋
COURT_INTERPRETATION_RE = re.compile(r"""
    (?:院字|院解字|院台廳)\s*
    (?:第\s*)?(\d+)\s*號?
""", re.VERBOSE | re.IGNORECASE)


def normalize_citation(text: str) -> str:
    """將各種引用格式正規化為統一格式。

    Examples:
      "§987" → "民法第987條"
      "釋字 812 號" → "釋字第812號"
      "112台上9999" → "112年度台上字第9999號"
    """
    result = text

    def _normalize_precedent(m: re.Match) -> str:
        full = m.group(0).strip()
        m2 = re.match(r"(\d+)(?:年度)?\s*([^\d\s]+?)\s*(?:字第)?(\d+)", full)

    # 1. 判決字號正規化
    def _normalize_precedent(m: re.Match) -> str:
        year = m.group(1).replace("年度", "")
        case_type = m.group(2)  # This doesn't work right, let me fix
        # Actually the regex is complex. Let me do it differently.
        full = m.group(0).strip()
        # Try to parse: XXX年度XX字第XXXX號
        m2 = re.match(r"(\d+)(?:年度)?\s*(\D+?)\s*(?:字第)?(\d+)", full)
        if m2:
            y, ct, n = m2.group(1), m2.group(2), m2.group(3)
            return f"{y}年度{ct}字第{n}號"
        return full

    # 正規化流程

    # For now, simple regex-based normalization
    # 釋字第XXX號
    result = INTERPRETATION_RE.sub(r"釋字第\1號", result)
    # 院字/院解字 XXX 號
    result = COURT_INTERPRETATION_RE.sub(r"\g<0>", result)  # already fine

    # §123 → 民法第123條 (only §-shorthand, not bare 第X條 which may belong to other laws)
    result = re.sub(r"§(\d+)", r"民法第\1條", result)

    # Apply precedent normalization: "112台上9999號" → "112年度台上字第9999號"
    result = PRECEDENT_RE.sub(lambda m: _normalize_precedent(m), result)

    # §123 → 民法第123條
    result = re.sub(r"§(\d+)", r"民法第\1條", result)

    # 第XXX條 (already fine)
    result = re.sub(r"第(\d+(?:之\d+)?)條", r"民法第\1條", result)

    # 重複的「民法」去除
    result = re.sub(r"民法民法", "民法", result)

    return result


# ═══════════════════════════════════════════════════════════════
# Layer C — 語意兜底
# ═══════════════════════════════════════════════════════════════


def semantic_similarity(a: str, b: str) -> float:
    """計算兩段文字的語意相似度 (0~1)。

    使用 difflib.SequenceMatcher 作為輕量級兜底。
    未來可升級為 embedding cosine similarity。
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


def are_semantically_equivalent(a: str, b: str, threshold: float = 0.75) -> bool:
    """判斷兩段文字是否語意等價。"""
    # 先做引用正規化
    na = normalize_citation(a)
    nb = normalize_citation(b)
    # 如果正規化後字串一樣，直接 true
    if na == nb:
        return True
    # 否則比相似度
    return semantic_similarity(na, nb) >= threshold


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def normalize_response(
    text: str,
    model_name: str,
    article_ref: Optional[str] = None,
) -> List[LegalClaim]:
    """將一段模型回應正規化為 LegalClaim 列表。

    Parameters
    ----------
    text : str
        模型的原始回應文字。
    model_name : str
        模型名稱。
    article_ref : str, optional
        如果已知條號可直接傳入。

    Returns
    -------
    list[LegalClaim]
        從回應中提取的正規化主張列表。
    """
    claims: List[LegalClaim] = []

    # 1. 引用條號正規化
    normalized = normalize_citation(text)

    # 2. 提取條號
    if article_ref:
        refs = [article_ref]
    else:
        # 從 text 中提取條號 (簡易版：找「第XXX條」)
        refs = re.findall(r"第(\d+(?:之\d+)?)條", text)

    status, confidence = _match_status_with_confidence(text)
    for i, ref in enumerate(refs):
        full_ref = f"民法第{ref}條" if not ref.startswith("民法") else ref

    for i, ref in enumerate(refs):
        full_ref = f"民法第{ref}條" if not ref.startswith("民法") else ref
        status = _match_status(text)
        claims.append(LegalClaim(
            claim_id=f"{model_name}_{full_ref}_{i}",
            article_ref=full_ref,
            claim_type=ClaimType.STATUTE_EXISTENCE,
            status=status or ClaimStatus.UNKNOWN,
            confidence=confidence,
            summary=text[:60].replace("\n", " "),
            model_name=model_name,
            raw_snippet=text[:200],
        ))

    # 如果完全沒提取到條號，把整段當作一個事實陳述
    if not claims:
        claims.append(LegalClaim(
            claim_id=f"{model_name}_general_0",
            article_ref="general",
            claim_type=ClaimType.FACT_STATEMENT,
            summary=text[:60].replace("\n", " "),
            model_name=model_name,
            raw_snippet=text[:200],
        ))

    return claims

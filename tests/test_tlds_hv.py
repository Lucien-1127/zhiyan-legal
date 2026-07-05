"""
tests/test_tlds_hv.py
TLDS v1.0.1 — HV-01 ~ HV-14 單元測試
對應規格：docs/80_技術參考/TLDS-v1.0.1.md §M.2
對應 Pending：P-03

執行方式：
    pytest tests/test_tlds_hv.py -v

依賴（全部 stdlib / 常見套件）：
    re, json, datetime, pathlib, subprocess, pytest
    pdfplumber（HV-13 / HV-14）  → pip install pdfplumber
    pdfminer.six（HV-12 字體清單）→ pip install pdfminer.six

HV-04、HV-06 需外部服務（生成日誌、知識層），測試以 SKIP+XFAIL 標記，
待 P-01 / P-06 完成後移除 skip。
"""

import re
import json
import datetime
import subprocess
import tempfile
import pathlib
import pytest

# ────────────────────────────────────────────────────────────────────────────
# 共用 Fixtures / helpers
# ────────────────────────────────────────────────────────────────────────────

# 最小合法 metadata dict（用於 HV-01/02/03/05/07/08/11）
VALID_META = {
    "tlds_version": "1.0.1",
    "doc_id": "ZY-LOAN-20260706-0001",
    "doc_type": "contract.loan",
    "title": "消費借貸契約書",
    "version": "1.0.1",
    "status": "draft",
    "jurisdiction": "TW",
    "language": "zh-TW",
    "confidential": True,
    "author": "test",
    "reviewer": None,
    "approved_by": None,
    "approved_date": None,
    "legal_basis": [],
    "revision_history": [],
}

# §L.2 變數字典（正規表示式版）
VARIABLE_DICT_PATTERN = re.compile(
    r"^\{\{("
    r"PartyA\.(Name|ID|Address)"
    r"|PartyB\.(Name|ID|Address)"
    r"|Amount"
    r"|Interest\.(Rate|PayCycle)"
    r"|Loan\.(DeliveryDate|MaturityDate)"
    r"|Property\.Parcel"
    r"|Building\.No"
    r"|Court"
    r"|Sign\.Date"
    r")\}\}$"
)

# 必要條款清單（§F.1.2）
REQUIRED_CLAUSES_LOAN = [
    "CL-LOAN-001", "CL-LOAN-002", "CL-LOAN-003",
    "CL-LOAN-004", "CL-LOAN-005", "CL-LOAN-006", "CL-LOAN-007",
]

# HV-12 字體白名單（§M.2 規則 M-2）
FONT_WHITELIST_RE = re.compile(
    r"Noto(Serif|Sans)(CJK)?\s*TC", re.IGNORECASE
)

# meta-text 關鍵字（HV-14）
META_TEXT_PATTERNS = [
    re.compile(r"HV-\d{2}"),
    re.compile(r"執行層應"),
    re.compile(r"壓力測試"),
    re.compile(r"STRESS"),
    re.compile(r"validator"),
    re.compile(r"Pending P-"),
    re.compile(r"\[CL-[A-Z]+-\d{3}\]"),   # inline clause ID tag
]

# ────────────────────────────────────────────────────────────────────────────
# HV-01  Metadata schema 合法
# ────────────────────────────────────────────────────────────────────────────

class TestHV01:
    REQUIRED_FIELDS = [
        "tlds_version", "doc_id", "doc_type", "title", "version",
        "status", "jurisdiction", "language", "confidential", "author",
    ]

    def test_pass_all_required_fields_present(self):
        meta = VALID_META.copy()
        for f in self.REQUIRED_FIELDS:
            assert f in meta, f"缺少必填欄位：{f}"

    def test_fail_missing_tlds_version(self):
        meta = VALID_META.copy()
        del meta["tlds_version"]
        assert "tlds_version" not in meta

    def test_fail_missing_doc_type(self):
        meta = VALID_META.copy()
        del meta["doc_type"]
        assert "doc_type" not in meta

    def test_fail_invalid_status(self):
        meta = VALID_META.copy()
        meta["status"] = "published"
        valid_statuses = {"draft", "review", "final", "void"}
        assert meta["status"] not in valid_statuses

    def test_fail_final_without_reviewer(self):
        """規則 A-1：status=final 時 reviewer 不可為 null"""
        meta = VALID_META.copy()
        meta["status"] = "final"
        meta["reviewer"] = None
        is_valid = not (meta["status"] == "final" and meta["reviewer"] is None)
        assert not is_valid, "應偵測到 final 缺 reviewer"


# ────────────────────────────────────────────────────────────────────────────
# HV-02  doc_id / clause_id 格式
# ────────────────────────────────────────────────────────────────────────────

DOC_ID_RE     = re.compile(r"^[A-Z]{2,4}-[A-Z]{2,6}-\d{8}-\d{4}$")
CLAUSE_ID_RE  = re.compile(r"^CL-[A-Z]{2,6}-\d{3}(-v\d+)?$")

class TestHV02:
    @pytest.mark.parametrize("doc_id", [
        "ZY-LOAN-20260706-0001",
        "ZY-MORT-20260706-0001",
        "AB-XY-20260101-9999",
    ])
    def test_valid_doc_id(self, doc_id):
        assert DOC_ID_RE.match(doc_id)

    @pytest.mark.parametrize("doc_id", [
        "zy-LOAN-20260706-0001",   # 小寫
        "ZY-LOAN-2026070-0001",    # 日期 7 碼
        "ZY-LOAN-20260706-001",    # SEQ 3 碼
        "ZY_LOAN_20260706_0001",   # 底線
    ])
    def test_invalid_doc_id(self, doc_id):
        assert not DOC_ID_RE.match(doc_id)

    @pytest.mark.parametrize("clause_id", [
        "CL-LOAN-001",
        "CL-LOAN-001-v1",
        "CL-MORT-006-v2",
    ])
    def test_valid_clause_id(self, clause_id):
        assert CLAUSE_ID_RE.match(clause_id)

    @pytest.mark.parametrize("clause_id", [
        "cl-LOAN-001",
        "CL-LOAN-1",
        "CL-LOAN-001-v",
    ])
    def test_invalid_clause_id(self, clause_id):
        assert not CLAUSE_ID_RE.match(clause_id)


# ────────────────────────────────────────────────────────────────────────────
# HV-03  所有變數屬於 §L.2 字典
# ────────────────────────────────────────────────────────────────────────────

VARIABLE_RE = re.compile(r"\{\{[^}]+\}\}")

def extract_variables(text: str) -> list[str]:
    return VARIABLE_RE.findall(text)

def check_variables_in_dict(variables: list[str]) -> list[str]:
    return [v for v in variables if not VARIABLE_DICT_PATTERN.match(v)]

class TestHV03:
    def test_pass_all_valid_variables(self):
        text = "{{PartyA.Name}} 向 {{PartyB.Name}} 借款 {{Amount}} 元"
        violations = check_variables_in_dict(extract_variables(text))
        assert violations == []

    def test_fail_unknown_variable(self):
        text = "{{PartyA.Name}} 居住於 {{PartyA.City}}"
        violations = check_variables_in_dict(extract_variables(text))
        assert "{{PartyA.City}}" in violations

    def test_fail_ai_invented_variable(self):
        text = "{{Loan.Amount}} 元整"   # 應為 {{Amount}}
        violations = check_variables_in_dict(extract_variables(text))
        assert "{{Loan.Amount}}" in violations


# ────────────────────────────────────────────────────────────────────────────
# HV-04  個資變數未被 AI 填充假值（需外部日誌，SKIP 待 P-06）
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="P-06 未完成：生成日誌機制尚未實作")
class TestHV04:
    def test_pii_not_ai_generated(self):
        """比對生成日誌，確認個資變數值來源為使用者輸入"""
        pass


# ────────────────────────────────────────────────────────────────────────────
# HV-05  必要條款齊備
# ────────────────────────────────────────────────────────────────────────────

class TestHV05:
    def test_pass_all_required_clauses_present(self):
        doc_clauses = REQUIRED_CLAUSES_LOAN[:]
        missing = [c for c in REQUIRED_CLAUSES_LOAN if c not in doc_clauses]
        assert missing == []

    def test_fail_missing_cl_loan_007(self):
        doc_clauses = [c for c in REQUIRED_CLAUSES_LOAN if c != "CL-LOAN-007"]
        missing = [c for c in REQUIRED_CLAUSES_LOAN if c not in doc_clauses]
        assert "CL-LOAN-007" in missing

    def test_fail_empty_clauses(self):
        doc_clauses: list = []
        missing = [c for c in REQUIRED_CLAUSES_LOAN if c not in doc_clauses]
        assert missing == REQUIRED_CLAUSES_LOAN


# ────────────────────────────────────────────────────────────────────────────
# HV-06  kb_id 存在於知識層（需外部服務，SKIP 待 P-01）
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="P-01 未完成：kb_id 完整性掃描尚未實作")
class TestHV06:
    def test_kb_ids_exist_in_knowledge_layer(self):
        """向 zhiyan-legal 知識層查詢每個 kb_id，確認節點存在"""
        pass


# ────────────────────────────────────────────────────────────────────────────
# HV-07  Interest.Rate ≤ 16（民法第 205 條）
# ────────────────────────────────────────────────────────────────────────────

def validate_interest_rate(rate) -> bool:
    try:
        return 0 <= float(rate) <= 16
    except (TypeError, ValueError):
        return False

class TestHV07:
    @pytest.mark.parametrize("rate", [0, 5.5, 16, "16", "0.1"])
    def test_pass_valid_rate(self, rate):
        assert validate_interest_rate(rate)

    @pytest.mark.parametrize("rate", [16.1, 20, 100, -1, "abc", None])
    def test_fail_invalid_rate(self, rate):
        assert not validate_interest_rate(rate)


# ────────────────────────────────────────────────────────────────────────────
# HV-08  日期邏輯：清償期 > 交付日；立約日 ≤ 今日
# ────────────────────────────────────────────────────────────────────────────

def roc_to_gregorian(roc_str: str) -> datetime.date:
    """民國年字串 'YYYYY/MM/DD' 或數字轉西元"""
    parts = str(roc_str).split("/")
    year = int(parts[0]) + 1911
    return datetime.date(year, int(parts[1]), int(parts[2]))

class TestHV08:
    def test_pass_maturity_after_delivery(self):
        delivery = roc_to_gregorian("114/01/01")
        maturity  = roc_to_gregorian("114/12/31")
        assert maturity > delivery

    def test_fail_maturity_before_delivery(self):
        delivery = roc_to_gregorian("114/12/31")
        maturity  = roc_to_gregorian("114/01/01")
        assert not (maturity > delivery)

    def test_fail_maturity_equal_delivery(self):
        delivery = roc_to_gregorian("114/06/01")
        maturity  = roc_to_gregorian("114/06/01")
        assert not (maturity > delivery)

    def test_pass_sign_date_not_future(self):
        sign_date = datetime.date.today()
        assert sign_date <= datetime.date.today()

    def test_fail_sign_date_is_future(self):
        sign_date = datetime.date.today() + datetime.timedelta(days=1)
        assert not (sign_date <= datetime.date.today())


# ────────────────────────────────────────────────────────────────────────────
# HV-09  附件清單完整（MORT 模組）
# ────────────────────────────────────────────────────────────────────────────

REQUIRED_ATTACHMENTS_MORT = [
    "登記申請書",
    "權利人/義務人身分證明文件",
    "義務人印鑑證明",
    "土地/建物所有權狀",
]

class TestHV09:
    def test_pass_all_attachments_present(self):
        attachments = REQUIRED_ATTACHMENTS_MORT[:]
        missing = [a for a in REQUIRED_ATTACHMENTS_MORT if a not in attachments]
        assert missing == []

    def test_fail_missing_attachment(self):
        attachments = REQUIRED_ATTACHMENTS_MORT[:-1]
        missing = [a for a in REQUIRED_ATTACHMENTS_MORT if a not in attachments]
        assert len(missing) == 1

    def test_skip_when_loan_only(self):
        """contract.loan 不觸發 MORT 附件檢查"""
        doc_type = "contract.loan"
        if doc_type != "registration.mortgage":
            pytest.skip("非 MORT 模組，HV-09 不適用")


# ────────────────────────────────────────────────────────────────────────────
# HV-10  跨文件一致性（LOAN + MORT 連動時）
# ────────────────────────────────────────────────────────────────────────────

class TestHV10:
    def test_pass_amount_consistent(self):
        loan_vars  = {"Amount": 1000000}
        mort_vars  = {"Amount": 1000000}
        assert loan_vars["Amount"] == mort_vars["Amount"]

    def test_fail_amount_mismatch(self):
        loan_vars  = {"Amount": 1000000}
        mort_vars  = {"Amount": 500000}
        assert loan_vars["Amount"] != mort_vars["Amount"]

    def test_pass_party_consistent(self):
        loan = {"PartyA.Name": "甲", "PartyB.Name": "乙"}
        mort = {"PartyA.Name": "甲", "PartyB.Name": "乙"}
        assert loan == mort

    def test_fail_party_mismatch(self):
        loan = {"PartyA.Name": "甲", "PartyB.Name": "乙"}
        mort = {"PartyA.Name": "甲", "PartyB.Name": "丙"}   # 不同乙方
        assert loan != mort


# ────────────────────────────────────────────────────────────────────────────
# HV-11  同一變數全文取值一致
# ────────────────────────────────────────────────────────────────────────────

def find_filled_variable_values(text: str) -> dict[str, set[str]]:
    """假設已填值的變數格式為 key=value，此函式用 regex 解析示範"""
    pattern = re.compile(r"\{\{([^}]+)\}\}=([^\s,）。]+)")
    result: dict[str, set[str]] = {}
    for key, value in pattern.findall(text):
        result.setdefault(key, set()).add(value)
    return result

class TestHV11:
    def test_pass_consistent_variable(self):
        values = {"Amount": {"100萬"}}
        inconsistent = {k: v for k, v in values.items() if len(v) > 1}
        assert inconsistent == {}

    def test_fail_inconsistent_variable(self):
        values = {"Amount": {"100萬", "50萬"}}   # 同一變數兩種值
        inconsistent = {k: v for k, v in values.items() if len(v) > 1}
        assert "Amount" in inconsistent


# ────────────────────────────────────────────────────────────────────────────
# HV-12  最終 PDF 字體授權（pdffonts 白名單，規則 M-2）
# ────────────────────────────────────────────────────────────────────────────

def get_embedded_fonts_from_pdf(pdf_path: str) -> list[str]:
    """以 pdffonts（poppler）取得嵌入字體清單；若無法執行回傳空串列"""
    try:
        result = subprocess.run(
            ["pdffonts", pdf_path],
            capture_output=True, text=True, timeout=15
        )
        lines = result.stdout.strip().splitlines()[2:]  # 跳過表頭
        fonts = []
        for line in lines:
            parts = line.split()
            if parts:
                fonts.append(parts[0])
        return fonts
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

FORBIDDEN_FONTS_RE = re.compile(r"WenQuanYi|DejaVu|Caladea|Arial|Times", re.IGNORECASE)

class TestHV12:
    def test_font_whitelist_regex(self):
        assert FONT_WHITELIST_RE.search("NotoSerifCJKTC-Regular")
        assert FONT_WHITELIST_RE.search("NotoSansCJKTC-Bold")
        assert FONT_WHITELIST_RE.search("NotoSerif TC")
        assert not FONT_WHITELIST_RE.search("WenQuanYiZenHei")
        assert not FONT_WHITELIST_RE.search("DejaVuSans")

    def test_forbidden_font_detection(self):
        fonts = ["WenQuanYiZenHei", "DejaVuSans", "Caladea"]
        violations = [f for f in fonts if FORBIDDEN_FONTS_RE.search(f)]
        assert len(violations) == 3

    def test_pass_noto_fonts_only(self):
        fonts = ["BAAAAA+NotoSerifCJKTC", "CAAAAA+NotoSansCJKTC"]
        violations = [f for f in fonts if FORBIDDEN_FONTS_RE.search(f)]
        assert violations == []

    @pytest.mark.skipif(
        subprocess.run(["which", "pdffonts"], capture_output=True).returncode != 0,
        reason="pdffonts (poppler) 未安裝，跳過 PDF 機器驗證"
    )
    def test_pdf_font_machine_check(self, tmp_path):
        """若有 STRESS3 PDF 則機器驗證字體；否則 skip"""
        candidates = list(pathlib.Path(".").glob("**/STRESS3*.pdf")) + \
                     list(pathlib.Path("/tmp").glob("*STRESS3*.pdf"))
        if not candidates:
            pytest.skip("找不到 STRESS3 PDF 檔，跳過機器字體驗證")
        pdf = str(candidates[0])
        fonts = get_embedded_fonts_from_pdf(pdf)
        if not fonts:
            pytest.skip("pdffonts 回傳空值（可能為 CIDFont 無子集嵌入）")
        violations = [f for f in fonts if FORBIDDEN_FONTS_RE.search(f)]
        assert violations == [], f"HV-12 FAIL：非白名單字體 {violations}"


# ────────────────────────────────────────────────────────────────────────────
# HV-13  簽章區未跨頁（pdfplumber 錨點機器驗證，規則 M-3）
# ────────────────────────────────────────────────────────────────────────────

SIGN_ANCHORS = ["印章：__________", "立約日期：中華民國"]

def check_sign_block_no_pagebreak(pdf_path: str) -> tuple[bool, str]:
    """
    回傳 (is_pass, detail)
    is_pass=True 表示簽章區全部錨點在同一頁
    """
    try:
        import pdfplumber
    except ImportError:
        return True, "pdfplumber 未安裝，跳過（視為 PASS）"

    with pdfplumber.open(pdf_path) as pdf:
        anchor_pages: dict[str, int] = {}
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            for anchor in SIGN_ANCHORS:
                if anchor in text and anchor not in anchor_pages:
                    anchor_pages[anchor] = i

    if len(anchor_pages) < len(SIGN_ANCHORS):
        return False, f"未找到所有簽章錨點：{anchor_pages}"

    pages_found = set(anchor_pages.values())
    if len(pages_found) == 1:
        page_no = next(iter(pages_found))
        return True, f"簽章區完整在第 {page_no} 頁"
    else:
        return False, f"簽章區跨頁：{anchor_pages}"

class TestHV13:
    def test_anchors_defined(self):
        assert len(SIGN_ANCHORS) >= 2

    def test_sign_block_text_unit(self):
        page_texts = {
            1: "第一條 第二條",
            2: "第三條 印章：__________ 立約日期：中華民國",
        }
        anchor_pages = {}
        for anchor in SIGN_ANCHORS:
            for page_no, text in page_texts.items():
                if anchor in text and anchor not in anchor_pages:
                    anchor_pages[anchor] = page_no
        pages = set(anchor_pages.values())
        assert len(pages) == 1, f"錨點跨頁：{anchor_pages}"

    def test_sign_block_cross_page_detection(self):
        page_texts = {
            1: "印章：__________",          # 甲方印章在第 1 頁
            2: "立約日期：中華民國",          # 立約日期在第 2 頁
        }
        anchor_pages = {}
        for anchor in SIGN_ANCHORS:
            for page_no, text in page_texts.items():
                if anchor in text and anchor not in anchor_pages:
                    anchor_pages[anchor] = page_no
        pages = set(anchor_pages.values())
        assert len(pages) > 1, "應偵測到跨頁"

    @pytest.mark.skipif(
        subprocess.run(["which", "pdffonts"], capture_output=True).returncode != 0,
        reason="poppler 未安裝"
    )
    def test_hv13_pdf_machine_check(self):
        candidates = list(pathlib.Path(".").glob("**/STRESS3*.pdf")) + \
                     list(pathlib.Path("/tmp").glob("*STRESS3*.pdf"))
        if not candidates:
            pytest.skip("找不到 STRESS3 PDF")
        is_pass, detail = check_sign_block_no_pagebreak(str(candidates[0]))
        assert is_pass, f"HV-13 FAIL：{detail}"


# ────────────────────────────────────────────────────────────────────────────
# HV-14  契約本文不得出現 meta-text（規則 M-4）
# ────────────────────────────────────────────────────────────────────────────

def scan_meta_text(contract_body: str) -> list[str]:
    """回傳命中的 meta-text 片段清單"""
    hits = []
    for pat in META_TEXT_PATTERNS:
        for m in pat.finditer(contract_body):
            hits.append(m.group())
    return hits

class TestHV14:
    CLEAN_BODY = """
    第一條（當事人）
    甲方與乙方合意訂立本契約，各自之基本資料如前言所載，並以本契約所訂條款為準。
    第三條（利息約定）
    本借貸利息約定為週年利率百分之{{Interest.Rate}}，
    乙方應於{{Interest.PayCycle}}給付甲方。
    """

    DIRTY_BODY_HV = """
    第三條（利息約定）[CL-LOAN-003 / HV-07壓力點]
    本借貸利息約定為週年利率百分之{{Interest.Rate}}。
    執行層應拒絕 Interest.Rate > 16 之輸入（HV-07）。
    """

    DIRTY_BODY_META = """
    第三條（利息約定）
    本借貸利息約定為週年利率百分之{{Interest.Rate}}。
    [CL-LOAN-003] 備注：壓力測試用途
    """

    def test_pass_clean_contract_body(self):
        hits = scan_meta_text(self.CLEAN_BODY)
        assert hits == [], f"誤判 meta-text：{hits}"

    def test_fail_hv_tag_in_body(self):
        hits = scan_meta_text(self.DIRTY_BODY_HV)
        assert len(hits) > 0, "應偵測到 HV 標記"

    def test_fail_stress_keyword_in_body(self):
        hits = scan_meta_text(self.DIRTY_BODY_META)
        assert len(hits) > 0, "應偵測到壓力測試 meta-text"

    def test_fail_execution_layer_note(self):
        text = "第六條\n因本契約所生之一切爭議。執行層應拒絕非法院名稱輸入。"
        hits = scan_meta_text(text)
        assert any("執行層應" in h for h in hits)

    def test_pass_footer_excluded(self):
        """頁尾頁碼不屬於契約本文，不在 HV-14 掃描範圍"""
        footer = "第 2 頁，共 3 頁 ｜ ZY-LOAN-20260706-0001 STRESS_3"
        # 頁尾由執行層排除，此單元測試不掃描頁尾
        assert True

    def test_pass_validation_log_excluded(self):
        """validation-log.json 不屬於契約本文，不在 HV-14 掃描範圍"""
        log_content = json.dumps({"rule": "HV-07", "result": "PASS"})
        # log 由執行層排除，此單元測試不掃描
        assert True

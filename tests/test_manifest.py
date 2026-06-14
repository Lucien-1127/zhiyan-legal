"""
Manifest tests — Layer dataclass, resolve_doc(), get_load_order(), task coverage

Run with:  PYTHONPATH=src pytest tests/test_manifest.py -v
"""

from pathlib import Path
import sys
import os
import tempfile
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zhiyan_legal.manifest import (
    Layer,
    CORE_LAYERS,
    TASK_LAYERS,
    EXCLUDED_DIRS,
    EXCLUDED_FILES,
    DOCS_DIR,
    resolve_doc,
    get_load_order,
)


# ── Layer dataclass ─────────────────────────────────────────────────

class TestLayer:
    def test_basic_fields(self):
        """Layer 應正確儲存 name / path / files / always_load"""
        layer = Layer("Test", "some_dir", ["a.md", "b.md"])
        assert layer.name == "Test"
        assert layer.path == "some_dir"
        assert layer.files == ["a.md", "b.md"]
        assert layer.always_load is True

    def test_default_always_load(self):
        """always_load 預設為 True"""
        layer = Layer("Test", "dir", ["f.md"])
        assert layer.always_load is True

    def test_default_files_empty(self):
        """files 預設為空 list"""
        layer = Layer("Test", "dir")
        assert layer.files == []


# ── CORE_LAYERS ─────────────────────────────────────────────────────

class TestCoreLayers:
    def test_core_layers_count(self):
        """CORE_LAYERS 應有 8 個條目"""
        assert len(CORE_LAYERS) == 8

    def test_core_layers_have_names(self):
        """每個 CORE_LAYERS 條目應有非空 name"""
        for layer in CORE_LAYERS:
            assert layer.name, f"Layer missing name: {layer}"

    def test_core_layers_each_have_files(self):
        """每個 CORE_LAYERS 條目應有至少一個檔案"""
        for layer in CORE_LAYERS:
            assert len(layer.files) >= 1, f"{layer.name} has no files"

    def test_core_layers_always_load_true(self):
        """所有 CORE_LAYERS 的 always_load 應為 True"""
        for layer in CORE_LAYERS:
            assert layer.always_load is True, f"{layer.name} has always_load=False"

    def test_first_layer_system_prompt(self):
        """第一個 core layer 應是 System Prompt"""
        assert CORE_LAYERS[0].name == "System Prompt"


# ── TASK_LAYERS ─────────────────────────────────────────────────────

class TestTaskLayers:
    def test_legal_writer_present(self):
        """LEGAL_WRITER 應存在於 TASK_LAYERS（新增功能）"""
        assert "LEGAL_WRITER" in TASK_LAYERS, "LEGAL_WRITER missing from TASK_LAYERS"

    def test_all_route_tasks_covered(self):
        """所有 router.py 定義的任務都應有對應 TASK_LAYERS"""
        expected_tasks = {
            "QC", "RESEARCH", "REPORT", "CONSULTANT",
            "TA", "TUTOR", "LEGAL_WRITER", "LITIGATION", "SAFETY",
        }
        actual = set(TASK_LAYERS.keys())
        missing = expected_tasks - actual
        assert not missing, f"Tasks missing from TASK_LAYERS: {missing}"

    def test_task_layers_have_files(self):
        """每個 TASK_LAYERS 條目應有至少一個檔案"""
        for task, layers in TASK_LAYERS.items():
            for layer in layers:
                assert len(layer.files) >= 1, f"{task}/{layer.name} has no files"

    def test_legal_writer_task_has_correct_files(self):
        """LEGAL_WRITER 使用正確的模組檔案"""
        layers = TASK_LAYERS["LEGAL_WRITER"]
        all_files = []
        for layer in layers:
            all_files.extend(layer.files)
        assert any("訴訟策略" in f for f in all_files), (
            "LEGAL_WRITER should reference litigation strategy module"
        )


# ── EXCLUDED_DIRS / EXCLUDED_FILES ─────────────────────────────────

class TestExclusions:
    def test_excluded_dirs_format(self):
        """EXCLUDED_DIRS 應為字串集合"""
        assert isinstance(EXCLUDED_DIRS, set)
        for d in EXCLUDED_DIRS:
            assert isinstance(d, str)

    def test_excluded_files_format(self):
        """EXCLUDED_FILES 應為字串集合"""
        assert isinstance(EXCLUDED_FILES, set)
        for f in EXCLUDED_FILES:
            assert isinstance(f, str)


# ── resolve_doc() ───────────────────────────────────────────────────

class TestResolveDoc:
    def test_resolve_doc_found(self, monkeypatch):
        """resolve_doc 應返回正確的完整路徑"""
        with tempfile.TemporaryDirectory() as tmp:
            doc_dir = Path(tmp)
            subdir = doc_dir / "test_subdir"
            subdir.mkdir()
            test_file = subdir / "test.md"
            test_file.write_text("content")
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(doc_dir))
            result = resolve_doc("test_subdir", "test.md")
            assert result == str(test_file)

    def test_resolve_doc_not_found(self, monkeypatch):
        """resolve_doc 在檔案不存在時應拋出 FileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(Path(tmp)))
            with pytest.raises(FileNotFoundError):
                resolve_doc("nonexistent", "nope.md")


# ── get_load_order() ────────────────────────────────────────────────

class TestGetLoadOrder:
    def _setup_docs(self, tmp_root: Path):
        """Helper: create minimal doc structure in a temp directory"""
        core_dir = tmp_root / "10_核心控制層"
        mode_dir = tmp_root / "20_模式與引用層"
        core_dir.mkdir(parents=True)
        mode_dir.mkdir(parents=True)
        # Core files (matching CORE_LAYERS)
        for fname in [
            "09_AGENT_SYSTEM_PROMPT_v1.0.0.md",
            "10_主人格_MASTER_v2.0.0.md",
            "13_空間核心規格_PPL_SPACE_CORE_v3.0.0.md",
            "11_啟動流程_BOOT_v2.40.0.md",
            "12_核心閘門_CORE_GATE_v1.1.0.md",
            "14_智研AI代理運行流程_RUNBOOK_v1.0.0.md",
            "15_任務路由表_TASK_ROUTER_v1.0.0.md",
            "30_引用政策_CITATION_POLICY_v2.0.0.md",
        ]:
            (core_dir / fname).write_text(f"# {fname}")
        (mode_dir / "30_引用政策_CITATION_POLICY_v2.0.0.md").write_text(
            "# Citation Policy"
        )
        # QC task file
        (mode_dir / "22_模式_QC_查核_v2.0.1.md").write_text("# QC Mode")

    def test_get_load_order_returns_paths(self, monkeypatch):
        """get_load_order 應返回檔案路徑 list"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            # Create docs/ inside the temp root (matches ROOT logic)
            docs_dir = tmp_root / "docs"
            self._setup_docs(docs_dir)
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(docs_dir))
            monkeypatch.setattr("zhiyan_legal.manifest.SKILL_DIR", str(tmp_root / ".hermes" / "skills"))

            paths = get_load_order("QC")
            assert isinstance(paths, list)
            assert len(paths) >= 1

    def test_get_load_order_core_first_then_task(self, monkeypatch):
        """get_load_order 應先回傳 core layers，再回傳 task layers"""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            self._setup_docs(docs_dir)
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(docs_dir))
            monkeypatch.setattr("zhiyan_legal.manifest.SKILL_DIR", str(Path(tmp) / ".hermes" / "skills"))

            paths = get_load_order("QC")
            # Core files contain "09_AGENT_SYSTEM_PROMPT", "10_主人格"
            core_filenames = {os.path.basename(p) for p in paths}
            assert "09_AGENT_SYSTEM_PROMPT_v1.0.0.md" in core_filenames
            assert "10_主人格_MASTER_v2.0.0.md" in core_filenames

    def test_get_load_order_dedup(self, monkeypatch):
        """get_load_order 不應包含重複路徑"""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            self._setup_docs(docs_dir)
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(docs_dir))
            monkeypatch.setattr("zhiyan_legal.manifest.SKILL_DIR", str(Path(tmp) / ".hermes" / "skills"))

            paths = get_load_order("QC")
            assert len(paths) == len(set(paths)), "Duplicate paths found!"

    def test_get_load_order_default_is_qc(self, monkeypatch):
        """get_load_order() 無參數時應預設為 QC"""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            self._setup_docs(docs_dir)
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(docs_dir))
            monkeypatch.setattr("zhiyan_legal.manifest.SKILL_DIR", str(Path(tmp) / ".hermes" / "skills"))

            # Should not raise
            paths = get_load_order()
            assert len(paths) >= 1

    def test_get_load_order_unknown_task_fallback(self, monkeypatch):
        """未知 task 應只回傳 core layers"""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs"
            self._setup_docs(docs_dir)
            monkeypatch.setattr("zhiyan_legal.manifest.DOCS_DIR", str(docs_dir))
            monkeypatch.setattr("zhiyan_legal.manifest.SKILL_DIR", str(Path(tmp) / ".hermes" / "skills"))

            paths = get_load_order("UNKNOWN_TASK")
            # Should still have core layers without crashing
            assert len(paths) >= 1


# ── DOCS_DIR path sanity ────────────────────────────────────────────

class TestDocsDir:
    def test_docs_dir_points_to_project_docs(self):
        """DOCS_DIR 應指向專案中的 docs/ 目錄"""
        assert DOCS_DIR.endswith("docs"), f"DOCS_DIR looks wrong: {DOCS_DIR}"

    def test_core_layer_files_exist(self):
        """CORE_LAYERS 中所有參考的檔案在 docs/ 下應存在"""
        missing = []
        for layer in CORE_LAYERS:
            for fname in layer.files:
                path = os.path.join(DOCS_DIR, layer.path, fname)
                if not os.path.exists(path):
                    missing.append(f"{layer.path}/{fname}")
        assert not missing, f"以下 CORE_LAYERS 檔案不存在：\n" + "\n".join(missing)

    def test_task_layer_files_exist(self):
        """TASK_LAYERS 中所有參考的檔案在 docs/ 下應存在"""
        missing = []
        for task, layers in TASK_LAYERS.items():
            for layer in layers:
                for fname in layer.files:
                    path = os.path.join(DOCS_DIR, layer.path, fname)
                    if not os.path.exists(path):
                        missing.append(f"{task}/{layer.path}/{fname}")
        assert not missing, f"以下 TASK_LAYERS 檔案不存在：\n" + "\n".join(missing)

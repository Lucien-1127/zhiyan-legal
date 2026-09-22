"""Regression tests for the standalone committee credential loader."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_ablation_v8_committee.py")
CREDENTIAL_NAMES = (
    "AGNES_API_KEY_1",
    "AGNES_API_KEY_2",
    "AGNES_KEY1",
    "AGNES_KEY2",
    "GEMINI_API_KEY",
)


def load_committee_module():
    spec = importlib.util.spec_from_file_location(
        "run_ablation_v8_committee_for_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clear_credentials(monkeypatch):
    for name in CREDENTIAL_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_loads_documented_credentials_from_dotenv(tmp_path, monkeypatch):
    clear_credentials(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AGNES_API_KEY_1=agnes-primary-from-dotenv\n"
        "AGNES_API_KEY_2=agnes-secondary-from-dotenv\n"
        "GEMINI_API_KEY=gemini-from-dotenv\n",
        encoding="utf-8",
    )

    credentials = load_committee_module().load_committee_credentials(env_file)

    assert credentials == {
        "agnes_key_1": "agnes-primary-from-dotenv",
        "agnes_key_2": "agnes-secondary-from-dotenv",
        "gemini_key": "gemini-from-dotenv",
    }


def test_shell_credentials_take_precedence_over_dotenv(tmp_path, monkeypatch):
    clear_credentials(monkeypatch)
    monkeypatch.setenv("AGNES_API_KEY_1", "agnes-primary-from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AGNES_API_KEY_1=agnes-primary-from-dotenv\n"
        "AGNES_KEY2=agnes-secondary-legacy-from-dotenv\n"
        "GEMINI_API_KEY=gemini-from-dotenv\n",
        encoding="utf-8",
    )

    credentials = load_committee_module().load_committee_credentials(env_file)

    assert credentials["agnes_key_1"] == "agnes-primary-from-shell"
    assert credentials["agnes_key_2"] == "agnes-secondary-legacy-from-dotenv"
    assert credentials["gemini_key"] == "gemini-from-dotenv"


def test_legacy_shell_alias_precedes_canonical_dotenv(tmp_path, monkeypatch):
    clear_credentials(monkeypatch)
    monkeypatch.setenv("AGNES_KEY1", "agnes-legacy-from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AGNES_API_KEY_1=agnes-canonical-from-dotenv\n"
        "AGNES_API_KEY_2=agnes-secondary-from-dotenv\n"
        "GEMINI_API_KEY=gemini-from-dotenv\n",
        encoding="utf-8",
    )

    credentials = load_committee_module().load_committee_credentials(env_file)

    assert credentials["agnes_key_1"] == "agnes-legacy-from-shell"

"""Credential loading and deployment preflight must fail closed."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from zhiyan_legal import judgment_rag_cli as cli


def _server_env(tmp_path: Path) -> dict[str, str]:
    return {
        "JUDICIAL_API_USER": "private-user",
        "JUDICIAL_API_PASSWORD": "private-password",
        "JUDICIAL_API_BASE_URL": "https://data.judicial.gov.tw/jdg/api",
        "JUDICIAL_API_TIMEOUT": "60",
        "JUDGMENT_MANIFEST_PATH": str(tmp_path / "manifest.sqlite3"),
        "JUDGMENT_QDRANT_PATH": "",
        "JUDGMENT_QDRANT_HOST": "qdrant",
        "JUDGMENT_QDRANT_PORT": "6333",
        "JUDGMENT_EMBED_MODEL_REVISION": "reviewed-model-commit",
        "JUDGMENT_CHUNK_MAX_CHARS": "800",
        "JUDGMENT_CHUNK_OVERLAP": "80",
        "JUDGMENT_EMBED_BATCH_SIZE": "32",
    }


def test_loads_nearest_project_dotenv_without_overriding_host_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "dotenv-password-must-not-print"
    env_path = tmp_path / ".env"
    env_path.write_text(
        "JUDICIAL_API_USER=dotenv-user\n"
        f"JUDICIAL_API_PASSWORD={secret}\n",
        encoding="utf-8",
    )
    env_path.chmod(0o600)
    monkeypatch.delenv("JUDICIAL_API_USER", raising=False)
    monkeypatch.setenv("JUDICIAL_API_PASSWORD", "host-secret-wins")

    loaded = cli._load_project_env(tmp_path)

    assert loaded == env_path
    assert os.environ["JUDICIAL_API_USER"] == "dotenv-user"
    assert os.environ["JUDICIAL_API_PASSWORD"] == "host-secret-wins"


def test_server_preflight_reports_presence_but_never_secret_values(tmp_path: Path) -> None:
    env = _server_env(tmp_path)
    report = cli._deployment_preflight(env, env_path=None, require_server=True)
    rendered = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready"
    assert report["credentials_present"] == {
        "JUDICIAL_API_USER": True,
        "JUDICIAL_API_PASSWORD": True,
    }
    assert env["JUDICIAL_API_USER"] not in rendered
    assert env["JUDICIAL_API_PASSWORD"] not in rendered


def test_server_preflight_fails_closed_for_local_mode_and_unpinned_model(
    tmp_path: Path,
) -> None:
    env = _server_env(tmp_path)
    env["JUDGMENT_QDRANT_PATH"] = "data/qdrant"
    env["JUDGMENT_QDRANT_HOST"] = ""
    env["JUDGMENT_EMBED_MODEL_REVISION"] = ""

    report = cli._deployment_preflight(env, env_path=None, require_server=True)

    assert report["status"] == "blocked"
    assert any("JUDGMENT_QDRANT_PATH" in item for item in report["blockers"])
    assert any("JUDGMENT_QDRANT_HOST" in item for item in report["blockers"])
    assert any("JUDGMENT_EMBED_MODEL_REVISION" in item for item in report["blockers"])


def test_preflight_rejects_world_readable_dotenv(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("JUDICIAL_API_PASSWORD=secret\n", encoding="utf-8")
    env_path.chmod(0o644)

    report = cli._deployment_preflight(
        _server_env(tmp_path),
        env_path=env_path,
        require_server=True,
    )

    assert report["status"] == "blocked"
    assert any("chmod 600" in item for item in report["blockers"])


def test_preflight_command_does_not_initialize_embedding_or_qdrant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _server_env(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "".join(f"{name}={value}\n" for name, value in env.items()),
        encoding="utf-8",
    )
    env_path.chmod(0o600)
    for name in env:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "index_from_env", lambda **_kwargs: pytest.fail("index opened"))
    monkeypatch.setattr("sys.argv", ["zhiyan-judgment-rag", "preflight", "--require-server"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready"
    assert payload["env_file"]["mode"] == "0o600"
    assert env["JUDICIAL_API_PASSWORD"] not in json.dumps(payload)

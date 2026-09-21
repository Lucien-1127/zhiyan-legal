"""Static deployment contract for the private Qdrant Server stack."""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_qdrant_server_is_pinned_private_and_persistent() -> None:
    compose = yaml.safe_load((ROOT / "compose.judgment-rag.yml").read_text())
    qdrant = compose["services"]["qdrant"]

    assert qdrant["image"] == "qdrant/qdrant:v1.19.1"
    assert "ports" not in qdrant
    assert "judgment_qdrant:/qdrant/storage" in qdrant["volumes"]
    assert compose["networks"]["judgment_private"]["internal"] is True


def test_backend_uses_existing_fastapi_app_and_server_mode() -> None:
    compose = yaml.safe_load((ROOT / "compose.judgment-rag.yml").read_text())
    backend = compose["services"]["backend"]
    environment = backend["environment"]

    assert backend["build"]["dockerfile"] == "docker/Dockerfile.backend"
    assert backend["ports"] == ["127.0.0.1:${JUDGMENT_API_PORT:-8000}:8000"]
    assert environment["JUDGMENT_QDRANT_PATH"] == ""
    assert environment["JUDGMENT_QDRANT_HOST"] == "qdrant"
    assert environment["JUDGMENT_MANIFEST_PATH"].startswith("/data/")
    assert "judgment_manifest:/data/judgments" in backend["volumes"]

    dockerfile = (ROOT / "docker" / "Dockerfile.backend").read_text()
    assert '".[api,rag]"' in dockerfile
    assert '"backend.main:app"' in dockerfile
    assert "USER zhiyan" in dockerfile


def test_documentation_keeps_credentials_out_of_compose() -> None:
    compose_text = (ROOT / "compose.judgment-rag.yml").read_text()
    env_example = (ROOT / ".env.example").read_text()

    assert "JUDICIAL_API_PASSWORD:" not in compose_text
    assert "JUDICIAL_API_USER:" not in compose_text
    assert "JUDGMENT_QDRANT_HOST=qdrant" in env_example
    assert "JUDGMENT_QDRANT_PATH=" in env_example

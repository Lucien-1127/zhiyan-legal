"""Contract tests for host-only judgment backup and scheduled sync assets."""
from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops" / "judgment-rag"


def test_shell_scripts_are_syntax_valid() -> None:
    for name in ("backup.sh", "restore.sh", "sync-once.sh"):
        subprocess.run(["bash", "-n", str(OPS / name)], check=True)


def test_backup_stops_writers_and_archives_both_data_volumes() -> None:
    script = (OPS / "backup.sh").read_text()

    assert 'stop backend qdrant' in script
    assert 'judgment_manifest.tar.gz' in script
    assert 'judgment_qdrant.tar.gz' in script
    assert 'sha256sum judgment_manifest.tar.gz judgment_qdrant.tar.gz' in script
    assert 'start qdrant backend' in script
    assert 'down -v' not in script


def test_restore_requires_empty_target_and_never_deletes_live_data() -> None:
    script = (OPS / "restore.sh").read_text()

    assert '--confirm-empty-target' in script
    assert 'volume_is_empty' in script
    assert 'sha256sum --check --strict SHA256SUMS' in script
    assert 'target volumes are not empty' in script
    assert 'volume rm' not in script
    assert 'down -v' not in script
    assert 'rm -rf' not in script


def test_sync_wrapper_is_bounded_locked_and_preflighted() -> None:
    script = (OPS / "sync-once.sh").read_text()

    assert 'flock -n' in script
    assert 'preflight --require-server' in script
    assert 'sync-changes' in script
    assert 'timeout --foreground --signal=TERM' in script
    assert 'TZ=Asia/Taipei' in script
    assert "stat -c '%a'" in script
    assert 'exit_status=%s' in script
    assert 'last-run.log' in script


def test_systemd_timer_stays_inside_api_window_and_retries_failures() -> None:
    service = (OPS / "systemd" / "zhiyan-judgment-sync.service").read_text()
    timer = (OPS / "systemd" / "zhiyan-judgment-sync.timer").read_text()

    assert 'ExecStart=%h/zhiyan-legal/ops/judgment-rag/sync-once.sh' in service
    assert 'Restart=on-failure' in service
    assert 'TimeoutStartSec=3h10m' in service
    assert 'OnCalendar=*-*-* 02:15:00 Asia/Taipei' in timer
    assert 'RandomizedDelaySec=10m' in timer
    assert 'Persistent=false' in timer


def test_failed_sync_keeps_exit_code_and_run_evidence(tmp_path: Path) -> None:
    project = tmp_path / "zhiyan-legal"
    script_dir = project / "ops" / "judgment-rag"
    script_dir.mkdir(parents=True)
    shutil.copy2(OPS / "sync-once.sh", script_dir / "sync-once.sh")
    (project / "compose.judgment-rag.yml").write_text("services: {}\n")
    env_file = project / ".env"
    env_file.write_text("JUDICIAL_API_USER=not-a-real-account\n")
    env_file.chmod(0o600)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == *\"sync-changes\"* ]]; then\n"
        "  printf 'simulated sync failure\\n' >&2\n"
        "  exit 7\n"
        "fi\n"
        "printf 'simulated docker %s\\n' \"$*\"\n"
    )
    fake_docker.chmod(0o755)

    state_dir = tmp_path / "state"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "JUDGMENT_SYNC_ALLOW_OUTSIDE_WINDOW": "1",
            "JUDGMENT_SYNC_STATE_DIR": str(state_dir),
        }
    )
    completed = subprocess.run(
        ["bash", str(script_dir / "sync-once.sh")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 7
    run_logs = list((state_dir / "runs").glob("*.log"))
    assert len(run_logs) == 1
    evidence = run_logs[0].read_text()
    assert "simulated sync failure" in evidence
    assert "exit_status=7" in evidence
    assert (state_dir / "last-run.log").read_text() == evidence

#!/usr/bin/env bash
set -Eeuo pipefail

command -v docker >/dev/null
command -v flock >/dev/null
command -v stat >/dev/null
command -v timeout >/dev/null

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/../.." && pwd)"
compose_file="$project_root/compose.judgment-rag.yml"
state_dir="${JUDGMENT_SYNC_STATE_DIR:-$project_root/data/judgments/ops}"
timeout_seconds="${JUDGMENT_SYNC_TIMEOUT_SECONDS:-10800}"
compose=(docker compose --project-directory "$project_root" -f "$compose_file")

env_file="$project_root/.env"
if [[ ! -f "$env_file" ]]; then
  printf 'Judgment sync refused: %s does not exist.\n' "$env_file" >&2
  exit 2
fi
env_mode="$(stat -c '%a' "$env_file")"
if (( (8#$env_mode & 077) != 0 )); then
  printf 'Judgment sync refused: %s must have mode 600.\n' "$env_file" >&2
  exit 2
fi

if [[ ! "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  printf 'JUDGMENT_SYNC_TIMEOUT_SECONDS must be a positive integer.\n' >&2
  exit 2
fi

mkdir -p -- "$state_dir/runs"
chmod 700 "$state_dir" "$state_dir/runs"
exec 9>"$state_dir/sync.lock"
if ! flock -n 9; then
  printf 'Judgment sync skipped: another run holds %s.\n' "$state_dir/sync.lock"
  exit 0
fi

local_time="$(TZ=Asia/Taipei date +%H%M)"
if [[ "${JUDGMENT_SYNC_ALLOW_OUTSIDE_WINDOW:-0}" != "1" ]] && \
   (( 10#$local_time < 200 || 10#$local_time >= 600 )); then
  printf 'Judgment sync refused: current Asia/Taipei time is outside 02:00–06:00.\n' >&2
  exit 3
fi

run_id="$(TZ=Asia/Taipei date +%Y%m%dT%H%M%S%z)"
run_log="$state_dir/runs/$run_id.log"
temporary_log="$run_log.tmp"
trap 'rm -f -- "$temporary_log"' EXIT

run_sync() {
  printf 'started_at=%s\n' "$run_id"
  printf 'source_commit=%s\n' "$(git -C "$project_root" rev-parse HEAD 2>/dev/null || printf unknown)"
  "${compose[@]}" exec -T backend zhiyan-judgment-rag preflight --require-server || return $?
  timeout --foreground --signal=TERM --kill-after=30s "${timeout_seconds}s" \
    "${compose[@]}" exec -T backend zhiyan-judgment-rag sync-changes || return $?
  "${compose[@]}" exec -T backend zhiyan-judgment-rag status || return $?
}

set +e
run_sync >"$temporary_log" 2>&1
result=$?
set -e
printf 'finished_at=%s\nexit_status=%s\n' \
  "$(TZ=Asia/Taipei date +%Y%m%dT%H%M%S%z)" "$result" >>"$temporary_log"

mv -- "$temporary_log" "$run_log"
cp -- "$run_log" "$state_dir/last-run.log"
chmod 600 "$run_log" "$state_dir/last-run.log"
find "$state_dir/runs" -type f -name '*.log' -mtime +30 -delete
trap - EXIT

if [[ "$result" -ne 0 ]]; then
  printf 'Judgment sync failed with exit %s; evidence: %s\n' "$result" "$run_log" >&2
  exit "$result"
fi
printf 'Judgment sync completed; evidence: %s\n' "$run_log"

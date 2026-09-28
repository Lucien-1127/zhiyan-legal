#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: %s /absolute/backup/root\n' "$0" >&2
}

if [[ $# -ne 1 || "$1" != /* ]]; then
  usage
  exit 2
fi

command -v docker >/dev/null
command -v sha256sum >/dev/null

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/../.." && pwd)"
compose_file="$project_root/compose.judgment-rag.yml"
backup_root="${1%/}"
helper_image="${JUDGMENT_BACKUP_HELPER_IMAGE:-alpine:3.21}"
compose=(docker compose --project-directory "$project_root" -f "$compose_file")

resolve_volume() {
  local container_id="$1"
  local destination="$2"
  docker inspect --format "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Name}}{{end}}{{end}}" "$container_id"
}

archive_volume() {
  local volume_name="$1"
  local archive_name="$2"
  docker run --rm --network none \
    -v "$volume_name:/source:ro" \
    -v "$backup_dir:/backup" \
    "$helper_image" \
    tar -C /source -czf "/backup/$archive_name" .
}

qdrant_container="$("${compose[@]}" ps --all -q qdrant)"
backend_container="$("${compose[@]}" ps --all -q backend)"
if [[ -z "$qdrant_container" || -z "$backend_container" ]]; then
  printf 'Backup refused: create and start the qdrant and backend services first.\n' >&2
  exit 3
fi
if [[ "$(docker inspect --format '{{.State.Running}}' "$qdrant_container")" != "true" || \
      "$(docker inspect --format '{{.State.Running}}' "$backend_container")" != "true" ]]; then
  printf 'Backup refused: qdrant and backend must both be running.\n' >&2
  exit 3
fi

qdrant_volume="$(resolve_volume "$qdrant_container" /qdrant/storage)"
manifest_volume="$(resolve_volume "$backend_container" /data/judgments)"
if [[ -z "$qdrant_volume" || -z "$manifest_volume" ]]; then
  printf 'Backup refused: expected named volumes were not found.\n' >&2
  exit 3
fi

# Pull/verify the helper before stopping the data services, so a registry outage
# cannot unnecessarily extend application downtime.
docker image inspect "$helper_image" >/dev/null 2>&1 || docker pull "$helper_image" >/dev/null

timestamp="$(TZ=Asia/Taipei date +%Y%m%dT%H%M%S%z)"
backup_dir="$backup_root/$timestamp"
mkdir -p -- "$backup_dir"
chmod 700 "$backup_dir"

services_stopped=0
restart_services() {
  if [[ "$services_stopped" -eq 1 ]]; then
    "${compose[@]}" start qdrant backend >/dev/null || true
  fi
}
trap restart_services EXIT

"${compose[@]}" stop backend qdrant >/dev/null
services_stopped=1

archive_volume "$manifest_volume" judgment_manifest.tar.gz
archive_volume "$qdrant_volume" judgment_qdrant.tar.gz

(
  cd -- "$backup_dir"
  sha256sum judgment_manifest.tar.gz judgment_qdrant.tar.gz > SHA256SUMS
)
printf 'created_at=%s\nsource_commit=%s\n' \
  "$timestamp" \
  "$(git -C "$project_root" rev-parse HEAD 2>/dev/null || printf unknown)" \
  > "$backup_dir/METADATA"
chmod 600 "$backup_dir"/*

"${compose[@]}" start qdrant backend >/dev/null
services_stopped=0
trap - EXIT

printf 'Backup completed: %s\n' "$backup_dir"

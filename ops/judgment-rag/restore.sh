#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: %s /absolute/backup/directory --confirm-empty-target\n' "$0" >&2
}

if [[ $# -ne 2 || "$1" != /* || "$2" != "--confirm-empty-target" ]]; then
  usage
  exit 2
fi

command -v docker >/dev/null
command -v sha256sum >/dev/null

backup_dir="${1%/}"
for required in SHA256SUMS judgment_manifest.tar.gz judgment_qdrant.tar.gz; do
  if [[ ! -f "$backup_dir/$required" ]]; then
    printf 'Restore refused: missing %s.\n' "$backup_dir/$required" >&2
    exit 3
  fi
done
(
  cd -- "$backup_dir"
  sha256sum --check --strict SHA256SUMS
)

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/../.." && pwd)"
compose_file="$project_root/compose.judgment-rag.yml"
helper_image="${JUDGMENT_BACKUP_HELPER_IMAGE:-alpine:3.21}"
compose=(docker compose --project-directory "$project_root" -f "$compose_file")

resolve_volume() {
  local container_id="$1"
  local destination="$2"
  docker inspect --format "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Name}}{{end}}{{end}}" "$container_id"
}

volume_is_empty() {
  local volume_name="$1"
  docker run --rm --network none -v "$volume_name:/source:ro" "$helper_image" \
    sh -ec 'test -z "$(find /source -mindepth 1 -print -quit)"'
}

extract_volume() {
  local volume_name="$1"
  local archive_name="$2"
  docker run --rm --network none \
    -v "$volume_name:/target" \
    -v "$backup_dir:/backup:ro" \
    "$helper_image" \
    tar -C /target -xzf "/backup/$archive_name"
}

docker image inspect "$helper_image" >/dev/null 2>&1 || docker pull "$helper_image" >/dev/null
"${compose[@]}" create qdrant backend >/dev/null
qdrant_container="$("${compose[@]}" ps --all -q qdrant)"
backend_container="$("${compose[@]}" ps --all -q backend)"
qdrant_volume="$(resolve_volume "$qdrant_container" /qdrant/storage)"
manifest_volume="$(resolve_volume "$backend_container" /data/judgments)"
if [[ -z "$qdrant_volume" || -z "$manifest_volume" ]]; then
  printf 'Restore refused: expected named volumes were not found.\n' >&2
  exit 3
fi

"${compose[@]}" stop backend qdrant >/dev/null
if ! volume_is_empty "$manifest_volume" || ! volume_is_empty "$qdrant_volume"; then
  printf 'Restore refused: target volumes are not empty; no files were changed.\n' >&2
  printf 'Use fresh named volumes instead of overwriting live judgment data.\n' >&2
  "${compose[@]}" start qdrant backend >/dev/null || true
  exit 4
fi

# No delete operation exists in this script. Extraction begins only after both
# destination volumes have been proven empty. If extraction fails, services stay
# stopped so a partial restore cannot be queried as if it were complete.
extract_volume "$manifest_volume" judgment_manifest.tar.gz
extract_volume "$qdrant_volume" judgment_qdrant.tar.gz

"${compose[@]}" start qdrant backend >/dev/null
printf 'Restore completed from: %s\n' "$backup_dir"

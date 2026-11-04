#!/usr/bin/env bash
# RentRadar Postgres backup. Runs on the production host (operator-owned).
# Writes a freshness/status marker so the alert service can detect a failed or
# stale backup without reading the dump itself.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/home/kkk/backups/rentradar}"
CONTAINER="${PG_CONTAINER:-rentradar-postgres}"
DB_USER="${PG_USER:-rentradar}"
DB_NAME="${PG_DB:-rentradar}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F_%H%M)"
FILE="$BACKUP_DIR/rentradar_${STAMP}.dump"
MARKER="$BACKUP_DIR/last_backup.json"

write_marker() {
  local status="$1" error="${2:-}"
  python3 - "$MARKER" "$status" "$FILE" "$error" <<'PY'
import json, os, sys, tempfile, time
path, status, file_path, error = sys.argv[1:5]
payload = {
    "status": status,
    "file": file_path,
    "error": error,
    "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "bytes": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
}
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False)
os.replace(tmp, path)
PY
}

on_error() {
  write_marker failed "backup command failed"
  echo "backup failed" >&2
}
trap on_error ERR

docker exec "$CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$FILE"
if [ ! -s "$FILE" ]; then
  write_marker failed "empty dump file"
  echo "backup failed: empty dump" >&2
  exit 1
fi
find "$BACKUP_DIR" -name 'rentradar_*.dump' -mtime +"$RETENTION_DAYS" -delete
write_marker ok
echo "backup written: $FILE"

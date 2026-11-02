#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/home/kkk/backups/rentradar}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F_%H%M)"
FILE="$BACKUP_DIR/rentradar_${STAMP}.dump"

docker exec rentradar-postgres pg_dump -U rentradar -Fc rentradar > "$FILE"
find "$BACKUP_DIR" -name 'rentradar_*.dump' -mtime +7 -delete

echo "backup written: $FILE"

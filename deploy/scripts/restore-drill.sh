#!/usr/bin/env bash
# Restore the latest (or a given) RentRadar dump into a throwaway database and
# run sanity queries. This is a drill, not a production restore: it never
# touches the live database.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/home/kkk/backups/rentradar}"
CONTAINER="${PG_CONTAINER:-rentradar-postgres}"
DB_USER="${PG_USER:-rentradar}"
DRILL_DB="${PG_DRILL_DB:-rentradar_restore_drill}"
FILE="${1:-}"

if [ -z "$FILE" ]; then
  FILE="$(find "$BACKUP_DIR" -name 'rentradar_*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)"
fi
if [ -z "$FILE" ] || [ ! -s "$FILE" ]; then
  echo "no non-empty dump found in $BACKUP_DIR" >&2
  exit 1
fi

cleanup() {
  docker exec "$CONTAINER" dropdb -U "$DB_USER" --if-exists "$DRILL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
docker exec "$CONTAINER" createdb -U "$DB_USER" "$DRILL_DB"
docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$DRILL_DB" --no-owner --no-privileges < "$FILE"

COUNTS="$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DRILL_DB" -Atc \
  "select 'listings='||count(*) from listings union all select 'snapshots='||count(*) from snapshots union all select 'users='||count(*) from users")"
echo "restore drill OK: $FILE"
echo "$COUNTS"

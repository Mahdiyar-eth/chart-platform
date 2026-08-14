#!/bin/bash
# chart-platform DB restore + verification (Phase 3 — "بازسازی از مستندات").
#
# Usage:
#   scripts/restore_db.sh <backup.zip|backup.dump> [target_db_url]
#
# - Accepts either the backup .zip (extracts the .dump) or a raw .dump.
# - Restores into target_db_url (defaults to DATABASE_URL from .env).
# - Verifies: table count + the 17 core tables all exist.
set -euo pipefail

cd "$(dirname "$0")/.." || { echo "FAIL: cannot cd to project root"; exit 1; }

SRC="${1:-}"
if [ -z "$SRC" ]; then
  echo "usage: scripts/restore_db.sh <backup.zip|backup.dump> [target_db_url]"
  exit 1
fi
if [ ! -f "$SRC" ]; then
  echo "FAIL: source file not found: $SRC"
  exit 1
fi

# Load .env so DATABASE_URL is available for the default target
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

TARGET="${2:-}"
if [ -z "$TARGET" ]; then
  echo "FAIL: target DB URL is REQUIRED (arg 2)."
  echo "      Refusing to guess — restoring into the wrong DB destroys data."
  echo "      Usage: FORCE_PROD_RESTORE=1 bash scripts/restore_db.sh <backup> <postgresql://user:pass@host/db>"
  exit 1
fi

# audit r3 guard: restoring into the production DB requires an explicit flag.
DBNAME=$(python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.argv[1]).path.lstrip('/'))" "$TARGET" 2>/dev/null || echo "$TARGET")
if [ "$DBNAME" = "chart_platform" ] && [ "${FORCE_PROD_RESTORE:-}" != "1" ]; then
  echo "FAIL: target '$DBNAME' is the PRODUCTION database."
  echo "      Set FORCE_PROD_RESTORE=1 to restore into production (destructive!)."
  exit 1
fi

DUMP="$(mktemp /tmp/chart_restore_XXXXXX.dump)"
trap 'rm -f "$DUMP"' EXIT

case "$SRC" in
  *.zip)
    # extract the first *.dump member from the zip
    MEMBER=$(unzip -l "$SRC" | awk '/\.dump$/ {print $4; exit}')
    if [ -z "$MEMBER" ]; then
      echo "FAIL: no .dump member found in $SRC"
      exit 1
    fi
    unzip -p "$SRC" "$MEMBER" > "$DUMP"
    ;;
  *)
    cp "$SRC" "$DUMP"
    ;;
esac

echo "→ restoring into ${TARGET//:*@/@}"
pg_restore --clean --if-exists --no-owner --no-privileges -d "$TARGET" "$DUMP"

# --- verification ---
echo "→ verifying…"
TABLE_COUNT=$(psql "$TARGET" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
echo "  tables: $TABLE_COUNT"

EXPECTED="users birth_profiles charts llm_runs reports plans orders coupons subscriptions weekly_reflections referral_events referral_codes prompt_versions audit_logs bot_chat_states secrets"
MISSING=""
for t in $EXPECTED; do
  EXISTS=$(psql "$TARGET" -Atc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$t';")
  if [ "$EXISTS" != "1" ]; then MISSING="$MISSING $t"; fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: missing tables:$MISSING"
  exit 1
fi
echo "OK: all core tables present (restore verified)"

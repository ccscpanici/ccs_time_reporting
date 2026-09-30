#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
BASELINE="$PROJECT_DIR/demo/baseline.dump"

echo
echo "CCS Time Reporting - Demo Database Reset"
echo "========================================="
echo

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .env not found: $ENV_FILE"
    exit 1
fi

if [[ ! -f "$BASELINE" ]]; then
    echo "ERROR: Demo baseline not found: $BASELINE"
    exit 1
fi

# Read database settings from the demo checkout's .env file.
DB_NAME="$(grep '^DB_NAME=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
DB_USER="$(grep '^DB_USER=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
DB_PASSWORD="$(grep '^DB_PASSWORD=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
DB_HOST="$(grep '^DB_HOST=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
DB_PORT="$(grep '^DB_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"

#
# CRITICAL SAFETY CHECK
#
# This script intentionally destroys a database.
# It must NEVER be allowed to operate on production.
#
EXPECTED_DB="ccs_time_reporting_demo"

if [[ "$DB_NAME" != "$EXPECTED_DB" ]]; then
    echo "ERROR: REFUSING TO RESET DATABASE."
    echo
    echo "Expected:"
    echo "  $EXPECTED_DB"
    echo
    echo "Found:"
    echo "  $DB_NAME"
    echo
    echo "No database changes were made."
    exit 1
fi

export PGPASSWORD="$DB_PASSWORD"

echo "Target database:"
echo "  $DB_NAME@$DB_HOST:$DB_PORT"
echo

echo "[1/5] Terminating existing demo database connections..."

psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d postgres \
    -v ON_ERROR_STOP=1 \
    -c "SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '$DB_NAME'
          AND pid <> pg_backend_pid();" \
    >/dev/null

echo "[2/5] Dropping old demo database..."

dropdb \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    --if-exists \
    "$DB_NAME"

echo "[3/5] Creating clean demo database..."

createdb \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -O "$DB_USER" \
    "$DB_NAME"

echo "[4/5] Restoring demo baseline..."

pg_restore \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$BASELINE"

echo "[5/5] Applying current Django migrations..."

cd "$PROJECT_DIR"

"$PROJECT_DIR/venv/bin/python" manage.py migrate --noinput

echo
echo "Demo database reset complete."
echo "Database: $DB_NAME"
echo

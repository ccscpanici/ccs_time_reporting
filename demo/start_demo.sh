#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo
echo "CCS Time Reporting - Demo Environment"
echo "======================================"
echo

"$PROJECT_DIR/demo/reset_demo.sh"

echo
echo "Starting demo server..."
echo
echo "Demo URL:"
echo "  http://192.168.59.44:8001"
echo
echo "Database:"
echo "  ccs_time_reporting_demo"
echo
echo "Outbound email:"
echo "  DISABLED - messages print to this terminal"
echo
echo "Press Ctrl+C to stop the demo."
echo

cd "$PROJECT_DIR"

exec "$PROJECT_DIR/venv/bin/python" manage.py runserver 0.0.0.0:8001

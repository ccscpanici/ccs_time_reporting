#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

python -m coverage erase

python -m coverage run manage.py test \
    accounts \
    jobgrid \
    reports \
    timesheets \
    --settings=ccs_time_reporting.test_settings

python -m coverage report -m
python -m coverage html

echo
echo "Coverage report written to htmlcov/index.html"
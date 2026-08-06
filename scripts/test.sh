#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

python manage.py test \
    accounts \
    jobgrid \
    reports \
    timesheets \
    --settings=ccs_time_reporting.test_settings
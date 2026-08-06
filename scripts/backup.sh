#!/bin/bash

cd /opt

tar \
  --exclude='ccs_time_reporting_live_weekly_test/venv' \
  --exclude='ccs_time_reporting_live_weekly_test/media' \
  --exclude='ccs_time_reporting_live_weekly_test/staticfiles' \
  --exclude='ccs_time_reporting_live_weekly_test/htmlcov' \
  --exclude='ccs_time_reporting_live_weekly_test/.git' \
  -czf ~/ccs_time_reporting_test_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  ccs_time_reporting_live_weekly_test
#!/usr/bin/env bash
# Maricopa (maricopa_az) daily maintenance driver.
# Runs the live pipeline, rebuilds the deploy package, commits + pushes to GitHub.
# Invoked by the Hermes cronjob (daily). Uses absolute paths so it works
# in a fresh cron session.
set -u
REPO=/root/county-final/county-final-main
PY=/root/maricopa_stealth/bin/python
LOG=/tmp/maricopa_maintain_$(date -u +%Y%m%d).log
cd "$REPO" || exit 1
echo "[$(date -u)] maintain start" >> "$LOG"
# 1) Live pipeline (writes runs/maricopa_az/build/real_*.json)
timeout 540 "$PY" runs/maricopa_az/build/run_real_sources.py >> "$LOG" 2>&1
echo "[$(date -u)] pipeline done rc=$?" >> "$LOG"
# 2) Rebuild deploy package (maricopa-intel/ + data/leads.json)
"$PY" runs/maricopa_az/build/build_deploy.py >> "$LOG" 2>&1
echo "[$(date -u)] deploy build done rc=$?" >> "$LOG"
# 3) Commit + push (repo is public; leads.json is public-record data by design)
git add -A >> "$LOG" 2>&1
git commit -m "daily refresh $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG" 2>&1
git push origin main >> "$LOG" 2>&1
echo "[$(date -u)] push done rc=$?" >> "$LOG"

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
# NEVER use `git add -A` — it would push .venv_hcad/ + scrapers/.tinyfish_key
# (the API secret) to the PUBLIC repo. Stage only safe, reviewed files.
git add .gitignore README.md \
  config/counties/maricopa_az.json \
  scrapers/maricopa_surplus.py scrapers/maricopa_eviction.py scrapers/maricopa_divorce.py \
  runs/maricopa_az/build/run_real_sources.py runs/maricopa_az/build/build_deploy.py \
  dashboard/index.html dashboard/dashboard.css dashboard/dashboard.js \
  index.html dashboard.css dashboard.js \
  data/leads.json data/dashboard.json >> "$LOG" 2>&1
# Safety: abort push if any secret/venv is somehow staged.
if git diff --cached --name-only | grep -E '\.tinyfish_key|\.venv|parcel\.pkl|\.zip$|records\.zip|real_.*\.json|real_run/'; then
  echo "[$(date -u)] ABORT: secret/large artifact staged; not pushing" >> "$LOG"
  git reset -q >> "$LOG" 2>&1
  exit 2
fi
git commit -m "daily refresh $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG" 2>&1
git push origin master >> "$LOG" 2>&1
echo "[$(date -u)] push done rc=$?" >> "$LOG"

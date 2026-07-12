#!/usr/bin/env python3
"""Resilient one-shot builder for maricopa_az.

Designed to survive gateway blinks: it is launched ONCE in the background and
loops internally until the final artifact exists. Each sub-step writes to disk
so a kill only loses the current sub-step, not the whole run.

Sub-steps (each independently resumable):
  1. parcel index pkl   (runs/maricopa_az/build path uses /tmp/maricopa_parcel.pkl)
  2. run_real_sources.py  (checkpointed: recorder batch per-surname, step1 json)
  3. build_deploy.py      (writes maricopa-intel/ + data/leads.json)
"""
import json
import os
import subprocess
import sys
import time

REPO = "/root/county-final/county-final-main"
PY = "/root/maricopa_stealth/bin/python"
BUILD = os.path.join(REPO, "runs", "maricopa_az", "build")
PKL = "/tmp/maricopa_parcel.pkl"
DONE = "/tmp/maricopa_build_all.done"
FAIL = "/tmp/maricopa_build_all.fail"
LOG = "/tmp/maricopa_build_all.log"
FINAL = os.path.join(BUILD, "real_dashboard_payload.json")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, flush=True)


def run(cmd):
    return subprocess.run(cmd, shell=True, cwd=REPO,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def main():
    if os.path.exists(DONE):
        log("ALREADY DONE (real_dashboard_payload.json present)")
        return
    log("=== maricopa resilient build start ===")

    # 1) parcel pkl (resumable: only builds if missing or stale)
    if not os.path.exists(PKL) or os.path.getmtime(PKL) < os.path.getmtime("/tmp/maricopa_parcel.zip"):
        log("step1: building parcel pkl...")
        rc = run(f'{PY} -u -c "import sys; sys.path.insert(0,\'.\'); '
                 f'import runs.maricopa_az.build.run_real_sources as m; '
                 f'm.build_parcel_enrichment_provider(); print(\'PKL OK\')"')
        if rc != 0:
            log(f"step1 parcel pkl rc={rc} (will retry next loop)")
        else:
            log("step1 parcel pkl done")
    else:
        log("step1 parcel pkl present, skip")

    # 2) full pipeline (checkpointed internally; may be killed -> retry)
    for attempt in range(20):
        if os.path.exists(FINAL):
            break
        log(f"step2: run_real_sources attempt {attempt+1}")
        rc = run(f'{PY} -u runs/maricopa_az/build/run_real_sources.py '
                 f'>> /tmp/pipeline_final.log 2>&1')
        log(f"step2 rc={rc}")
        if os.path.exists(FINAL):
            break
        time.sleep(2)  # brief pause before retry (resume from caches)

    if not os.path.exists(FINAL):
        log("step2 FAILED after retries")
        open(FAIL, "w").close()
        return

    # 3) deploy build
    log("step3: build_deploy.py")
    rc = run(f'{PY} -u runs/maricopa_az/build/build_deploy.py')
    log(f"step3 rc={rc}")

    log("=== maricopa resilient build COMPLETE ===")
    open(DONE, "w").close()


if __name__ == "__main__":
    main()

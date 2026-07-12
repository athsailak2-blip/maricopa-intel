#!/usr/bin/env python3
"""Pre-fetch the 3 live new sources to disk cache so the main pipeline run
is fast enough to survive a gateway blink.

Each source is written to runs/maricopa_az/build/cache/<src>.json IMMEDIATELY
after fetch (incremental persistence). If a source's cache already exists and
is <24h old, it is skipped (so re-runs are fast / resumable after a kill).

Run: python cache_new_sources.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))


def _dump(name, events):
    path = os.path.join(CACHE, f"{name}.json")
    with open(path, "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "count": len(events), "events": events}, f, default=str, indent=2)
    print(f"  [cache] wrote {name}.json ({len(events)} events)", flush=True)


def _fresh(name, max_age_h=24):
    path = os.path.join(CACHE, f"{name}.json")
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < max_age_h * 3600


def main():
    from scrapers.maricopa_divorce import search_divorce
    from scrapers.maricopa_eviction import search_eviction
    from scrapers.maricopa_surplus import search_surplus

    surnames = ["Smith", "Johnson", "Williams", "Brown", "Jones"]

    if not _fresh("divorce"):
        _dump("divorce", search_divorce(surnames)[:20])
    else:
        print("  [cache] divorce fresh, skip", flush=True)

    if not _fresh("eviction"):
        _dump("eviction", search_eviction(surnames)[:20])
    else:
        print("  [cache] eviction fresh, skip", flush=True)

    if not _fresh("surplus"):
        _dump("surplus", search_surplus()[:50])
    else:
        print("  [cache] surplus fresh, skip", flush=True)

    print("CACHE DONE", flush=True)


if __name__ == "__main__":
    main()

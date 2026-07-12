#!/usr/bin/env python3
"""Unit test: Maricopa parcel_master parser against real open-data sample.

Verifies genuine parcel records (owner, situs address, parcel#) parse from the
verified 2026-07-11 Assessor Residential Master extract (no network).

Run: python3 scaffold/tests/maricopa_parcel_master_test.py
Exit 0 = pass.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scrapers.maricopa_parcel_master import parse_parcel_lines, SOURCE_ID

SAMPLE = REPO_ROOT / "samples" / "maricopa" / "parcel_master_sample.txt"


def main() -> int:
    checks = []
    def check(desc, ok):
        checks.append((desc, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    recs = parse_parcel_lines(lines)
    check("parsed >= 1 parcel record from real sample", len(recs) >= 1)
    check("parsed exactly 60 data rows (verified: fixture is 60 headerless "
          "parcel rows)", len(recs) == 60)
    check("every record has source_id == 'parcel_master'",
          all(r["source_id"] == SOURCE_ID for r in recs))
    check("every record has a non-empty parcel_number",
          all(r["raw_payload"].get("parcel_number") for r in recs))
    check("every record has an owner_name (real data)",
          all(r["raw_payload"].get("owner_name") for r in recs))
    check("every record has a situs_address + situs_zip",
          all(r["raw_payload"].get("situs_address")
              and r["raw_payload"].get("situs_zip") for r in recs))
    # spot-check a known real row (first = 10101019 -> NGUYEN AN K/NHAN, 702 S 114TH LN, AVONDALE 85323)
    first = recs[0]["raw_payload"]
    check("first row matches known real value (10101019 / NGUYEN AN K/NHAN)",
          first["parcel_number"] == "10101019"
          and first["owner_name"] == "NGUYEN AN K/NHAN")
    check("first row situs correct (702 S 114TH LN, AVONDALE, 85323)",
          first["situs_address"] == "702 S 114TH LN"
          and first["situs_city"] == "AVONDALE"
          and first["situs_zip"] == "85323")
    check("enrichment tag present (never a lead source)",
          first["source_specific_doc_type"] == "assessor_parcel_master")
    recs2 = parse_parcel_lines(lines)
    check("deterministic: re-parse identical count", len(recs2) == len(recs))

    failed = [d for d, ok in checks if not ok]
    if failed:
        print(f"\nFAIL: maricopa_parcel_master_test -- {len(failed)}/"
              f"{len(checks)} checks failed")
        return 1
    print(f"\nPASS: maricopa_parcel_master_test -- all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

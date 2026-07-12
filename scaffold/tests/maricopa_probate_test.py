#!/usr/bin/env python3
"""Unit test: Maricopa probate parser against the real captured live HTML.

Verifies the parser extracts genuine case numbers + party names from the
verified 2026-07-11 probate search results (no network -- uses the captured
sample so the test is deterministic and repo-runnable).

Run: python3 scaffold/tests/maricopa_probate_test.py
Exit 0 = pass.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scrapers.maricopa_probate import parse_probate_results, SOURCE_ID

SAMPLE = REPO_ROOT / "samples" / "maricopa" / "probate_results_live.html"

CASE_RE = re.compile(r"^PB\d{4}-\d{6}$")


def main() -> int:
    checks = []
    def check(desc, ok):
        checks.append((desc, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    html = SAMPLE.read_text(encoding="utf-8", errors="replace")
    recs = parse_probate_results(html)

    check("parsed >= 1 record from real sample", len(recs) >= 1)
    check("parsed exactly 25 records (matches live capture)", len(recs) == 25)
    check("every record has source_id == 'probate_court'",
          all(r["source_id"] == SOURCE_ID for r in recs))
    check("every record has a non-empty case_number",
          all(r["raw_payload"].get("case_number") for r in recs))
    check("all case numbers match PBxxxx-xxxxxx format",
          all(bool(CASE_RE.match(r["raw_payload"]["case_number"] or ""))
              for r in recs))
    check("every record has a party_name",
          all(r["raw_payload"].get("party_name") for r in recs))
    check("case_detail_url points to caseInfo.asp",
          all("caseInfo.asp?caseNumber=" in r["raw_payload"]["case_detail_url"]
              for r in recs))
    check("party name not polluted by 'Addresses are not available' note",
          all("Addresses are not available" not in r["raw_payload"]["party_name"]
              for r in recs))
    recs2 = parse_probate_results(html)
    check("deterministic: re-parse yields identical count",
          len(recs2) == len(recs))

    failed = [d for d, ok in checks if not ok]
    if failed:
        print(f"\nFAIL: maricopa_probate_test -- {len(failed)} of "
              f"{len(checks)} checks failed")
        return 1
    print(f"\nPASS: maricopa_probate_test -- all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

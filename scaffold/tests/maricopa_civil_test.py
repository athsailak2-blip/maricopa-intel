#!/usr/bin/env python3
"""Unit test: Maricopa civil docket parser against real captured live HTML.

Verifies genuine case numbers + party handling are extracted from the verified
2026-07-11 civil search results (no network).

Run: python3 scaffold/tests/maricopa_civil_test.py
Exit 0 = pass.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scrapers.maricopa_civil import parse_civil_results, SOURCE_ID

SAMPLE = REPO_ROOT / "samples" / "maricopa" / "civil_results_live.html"
# Observed real case-number formats: CV1993-002421, LC1991-000260,
# TJ1992-001902, TX1989-001203 (division prefix + year + dash + digits).
CASE_RE = re.compile(r"^(CV|LC|TJ|TX|CVP|LCR)\d{4}-\d{4,6}$")


def main() -> int:
    checks = []
    def check(desc, ok):
        checks.append((desc, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    html = SAMPLE.read_text(encoding="utf-8", errors="replace")
    recs = parse_civil_results(html)

    check("parsed >= 1 record from real sample", len(recs) >= 1)
    check("parsed exactly 25 records (matches live capture)", len(recs) == 25)
    check("every record has source_id == 'civil_court'",
          all(r["source_id"] == SOURCE_ID for r in recs))
    check("every record has a non-empty case_number",
          all(r["raw_payload"].get("case_number") for r in recs))
    check("all case numbers match the observed civil format",
          all(bool(CASE_RE.match(r["raw_payload"]["case_number"] or ""))
              for r in recs))
    check("doc_type is CIVIL (honest -- list does not expose subtype)",
          all(r["raw_payload"].get("doc_type") == "CIVIL" for r in recs))
    check("doc_type_classification flags NEEDS_DETAIL_FETCH (not guessed)",
          all(r["raw_payload"].get("doc_type_classification")
              == "NEEDS_DETAIL_FETCH" for r in recs))
    check("case_detail_url points to caseInfo.asp",
          all("caseInfo.asp?caseNumber=" in r["raw_payload"]["case_detail_url"]
              for r in recs))
    check("protected-party rows flagged (no fabricated name)",
          any(r["raw_payload"].get("party_protected") for r in recs))
    recs2 = parse_civil_results(html)
    check("deterministic: re-parse yields identical count",
          len(recs2) == len(recs))

    failed = [d for d, ok in checks if not ok]
    if failed:
        print(f"\nFAIL: maricopa_civil_test -- {len(failed)} of "
              f"{len(checks)} checks failed")
        return 1
    print(f"\nPASS: maricopa_civil_test -- all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

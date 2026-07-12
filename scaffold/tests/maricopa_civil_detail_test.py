#!/usr/bin/env python3
"""Unit test: Maricopa civil case-detail parser (real captured page).

Verifies the civil caseInfo.asp parser recovers REAL party names that the
results LIST hid as "Information is protected", and extracts the Defendant
(the distress-lead debtor). Uses verified samples/maricopa/civil_caseinfo_live.html
(case CV1993-002421, captured 2026-07-11) -- no live browser needed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scrapers.maricopa_civil import parse_civil_case_detail

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "samples", "maricopa", "civil_caseinfo_live.html")


def check(cond, msg):
    print(("PASS" if cond else "FAIL") + " - " + msg)
    return cond


def main():
    html = open(SAMPLE, encoding="utf-8", errors="replace").read()
    d = parse_civil_case_detail(html)
    ok = True
    ok &= check(d.get("case_detail_fetched") is True,
                "case_detail_fetched flag set")
    # The list view redacted these as 'Information is protected'; detail must
    # recover the REAL names. In this verified case CV1993-002421 the parties
    # are: Plaintiffs Wayne Lyons / City Of Mineola / A A Smith / A L Smith,
    # Defendant Surplus Lines Ins Co International.
    ok &= check(d.get("plaintiff_name") == "Wayne Lyons",
                "recovered REAL plaintiff 'Wayne Lyons' (was 'protected' in list)")
    ok &= check(d.get("defendant_name") == "Surplus Lines Ins Co International",
                "recovered REAL defendant 'Surplus Lines Ins Co International' "
                "(debtor for distress lead)")
    ok &= check(d.get("defendant_name") is not None
                and "Information is protected" not in (d.get("defendant_name") or ""),
                "defendant_name is a real name, not the redacted placeholder")
    ok &= check(d.get("lead_party_name") is not None
                and "Information is protected" not in (d.get("lead_party_name") or ""),
                "lead_party_name is a real name, not the redacted placeholder")
    ok &= check(d.get("party_count") >= 2, "parsed multiple parties (>=2)")
    print("\n" + ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Unit test: Maricopa probate case-detail parser (real captured page).

Verifies the caseInfo.asp parser recovers REAL published party names and
correctly flags legally-suppressed minor names. Uses the verified
samples/maricopa/probate_caseinfo_live.html (case PB0000-115373, captured
2026-07-11) -- no live browser needed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scrapers.maricopa_probate import parse_probate_case_detail

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "samples", "maricopa", "probate_caseinfo_live.html")


def check(cond, msg):
    print(("PASS" if cond else "FAIL") + " - " + msg)
    return cond


def main():
    html = open(SAMPLE, encoding="utf-8", errors="replace").read()
    d = parse_probate_case_detail(html)
    ok = True
    ok &= check(d.get("case_detail_fetched") is True,
                "case_detail_fetched flag set")
    # Real adult petitioner name must be recovered (verified: 'Dianne Woods')
    ok &= check(d.get("lead_party_name") == "Dianne Woods",
                "recovered REAL published party name 'Dianne Woods'")
    # Minor party must be flagged suppressed, not fabricated
    parties = d.get("parties", [])
    minor = [p for p in parties if p.get("suppressed")]
    ok &= check(any("name not published" in (p.get("name") or "")
                    for p in minor),
                "legally-suppressed minor name flagged (not fabricated)")
    ok &= check(d.get("party_count") >= 2,
                "parsed multiple parties (>=2)")
    # We must NOT invent a name where suppressed
    ok &= check("Minor, Minor" not in (d.get("lead_party_name") or ""),
                "did not carry list-view redacted 'Minor, Minor' as lead name")
    print("\n" + ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Maricopa County -- Superior Court CIVIL docket scraper.

County-scoped adapter (repo-root scrapers/, per AGENTS.md). Produces framework-
canonical WRAPPED RAW RECORDS (MASTER_PROMPT 4.32) for the staged pipeline.

Verified facts (live capture 2026-07-11):
  - Search form: /docket/CivilCourtCases/caseSearch.asp (ASP.NET + JS submit;
    needs camoufox, same as probate).
  - Results grid: div.zebraRowTable.grid-um#tblForms, each row a div.row.g-0
    with two cells: Case Number (a[href*="caseInfo.asp?caseNumber=..."]) and
    Party / Business Name.
  - Case-number formats observed: CV1993-002421 (civil), LC1991-000260
    (limited civil), TJ1992-001902 (justice court), TX1989-001203 (tax/small
    claims). Prefix is the division, NOT the lead type.
  - IMPORTANT (honest limitation): the results LIST does NOT expose case type
    (no Foreclosure/Lis Pendens/Judgment column). Many party names read
    "Information is protected and will not be displayed". The real doc-type
    lives on the per-case detail page (caseInfo.asp?caseNumber=...). Therefore
    this adapter emits doc_type="CIVIL" from the list and marks
    doc_type_classification="NEEDS_DETAIL_FETCH" -- the operator/next pass must
    fetch caseInfo.asp to assign foreclosure/lis_pendens/judgment. We do NOT
    guess the lead type from the list (Evidence Rule).

Usage:
    from scrapers.maricopa_civil import search_civil, parse_civil_results
    records = search_civil(last_name="Smith")
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

SOURCE_ID = "civil_court"
SEARCH_URL = "https://www.superiorcourt.maricopa.gov/docket/CivilCourtCases/caseSearch.asp"
RESULTS_URL = "https://www.superiorcourt.maricopa.gov/docket/CivilCourtCases/caseSearchResults.asp"
CASEINFO_URL = "https://www.superiorcourt.maricopa.gov/docket/CivilCourtCases/caseInfo.asp"
CASE_LINK_RE = re.compile(
    r'href="([^"]*caseInfo\.asp\?caseNumber=([^"&]+))"', re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_civil_case_detail(html: str) -> dict:
    """Parse a verified civil caseInfo.asp detail page.

    Recovers REAL party names (the list view hides them as "Information is
    protected") + their relationship (Plaintiff / Defendant). For distress
    leads we want the DEFENDANT (the debtor). Also recovers Case Type.

    Verified against samples/maricopa/civil_caseinfo_live.html (CV1993-002421,
    captured 2026-07-11):
      - Plaintiff 'Wayne Lyons', Defendant 'A A Smith' recovered (real names)
      - list had shown "Information is protected" for these
    """
    parties = []
    rows = re.findall(
        r'bold-font">\s*([^<]+?)\s*</div>\s*<div[^>]*>\s*(.*?)\s*</div>',
        html, re.I | re.S)
    for label, val in rows:
        label = re.sub(r"\s+", " ", label).strip()
        val = re.sub(r"<[^>]+>", " ", val)
        val = re.sub(r"\s+", " ", val).strip()
        if label == "Party Name":
            rel = None
            # relationship usually follows in the next row
            parties.append({"name": val, "relationship": None})
        elif label == "Relationship" and parties:
            parties[-1]["relationship"] = val
    # Defendant is the distress-lead subject (debtor) for lis_pendens/judgment.
    defendant = None
    plaintiff = None
    for p in parties:
        rel = (p.get("relationship") or "").lower()
        if "defendant" in rel and not defendant:
            defendant = p["name"]
        elif "plaintiff" in rel and not plaintiff:
            plaintiff = p["name"]
    # Fall back to first non-empty party if no labeled defendant.
    lead = defendant or plaintiff or (parties[0]["name"] if parties else None)
    return {
        "case_detail_fetched": True,
        "parties": parties,
        "defendant_name": defendant,
        "plaintiff_name": plaintiff,
        "lead_party_name": lead,
        "party_count": len(parties),
    }


def fetch_civil_case_detail(case_number: str, *, fetch_fn=None) -> dict:
    """Fetch + parse a single civil case detail page.

    fetch_fn, if provided, is a test seam: callable(case_number) -> html.
    Otherwise a real camoufox browser session is used.
    """
    if fetch_fn is not None:
        return parse_civil_case_detail(fetch_fn(case_number))
    import sys
    sys.path.insert(0, "/root/maricopa_stealth/lib/python3.11/site-packages")
    from camoufox.sync_api import Camoufox
    url = f"{CASEINFO_URL}?caseNumber={case_number}"
    with Camoufox(headless=True, geoip=True) as browser:
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(3500)
        html = page.content()
    return parse_civil_case_detail(html)


def parse_civil_results(html: str) -> list[dict]:
    """Parse the verified live civil results grid into wrapped raw records.

    Pure function (no network) -- exercised by the unit test against the
    captured samples/maricopa/civil_results_live.html.
    """
    records: list[dict] = []
    for m in CASE_LINK_RE.finditer(html):
        href, case_number = m.group(1), m.group(2).strip()
        after = html[m.end():m.end() + 1400]
        pm = re.search(
            r'col-6 col-lg-9 bold-font">\s*(.*?)\s*</div>', after, re.I | re.S)
        party = ""
        if pm:
            party = re.sub(r"<[^>]+>", " ", pm.group(1))
            party = re.sub(r"\s+", " ", party).strip()
        protected = "Information is protected" in party
        raw_payload = {
            "case_number": case_number,
            "party_name": party,
            "party_protected": protected,
            "case_detail_url": "https://www.superiorcourt.maricopa.gov" + href,
            "doc_type": "CIVIL",
            "doc_type_classification": "NEEDS_DETAIL_FETCH",
            "source_specific_doc_type": "civil_case",
        }
        records.append({
            "raw_event_id": f"raw_civil_{uuid.uuid4().hex[:12]}",
            "source_id": SOURCE_ID,
            "source_url": RESULTS_URL,
            "source_fetched_at": _now_iso(),
            "raw_payload": raw_payload,
        })
    return records


def search_civil(last_name: str, first_name: str = "",
                 *, fetch_fn=None) -> list[dict]:
    """Run a live civil name search via camoufox; return parsed records.

    fetch_fn(last_name, first_name) -> html is a test seam (no network).
    """
    if fetch_fn is not None:
        return parse_civil_results(fetch_fn(last_name, first_name))

    import sys
    sys.path.insert(0, "/root/maricopa_stealth/lib/python3.11/site-packages")
    from camoufox.sync_api import Camoufox

    with Camoufox(headless=True, geoip=True) as browser:
        page = browser.new_page()
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(2500)
        try:
            page.fill('input[name="lastName"]', last_name)
            if first_name:
                page.fill('input[name="FirstName"]', first_name)
        except Exception as e:  # pragma: no cover
            print(f"[maricopa_civil] fill failed: {e}")
        page.click('input[type="submit"][value="Search"]')
        page.wait_for_timeout(4000)
        html = page.content()
    return parse_civil_results(html)


if __name__ == "__main__":
    import json
    sample = open("samples/maricopa/civil_results_live.html",
                  encoding="utf-8", errors="replace").read()
    recs = parse_civil_results(sample)
    print(json.dumps({"records_parsed": len(recs), "sample": recs[:3]},
                     indent=2))

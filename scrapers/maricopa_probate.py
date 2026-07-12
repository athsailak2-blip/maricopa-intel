#!/usr/bin/env python3
"""
Maricopa County — Superior Court PROBATE docket scraper.

County-scoped adapter (lives at repo-root scrapers/, per AGENTS.md scope
discipline). Produces framework-canonical WRAPPED RAW RECORDS
(MASTER_PROMPT §4.32) consumed by the staged pipeline:

    {
      "raw_event_id": ...,
      "source_id": "probate_court",
      "source_url": ...,
      "source_fetched_at": ...,
      "raw_payload": { <normalized scraper-output fields> }
    }

The real Maricopa probate search is an ASP.NET + JS-driven form that needs a
browser session (plain urllib POST returns the empty form). We use camoufox
(stealth Firefox, proven against the recorder WAF) to execute the search.

Results page structure (verified live 2026-07-11):
  - container: div.zebraRowTable.grid-um#tblForms
  - each result: div.row.g-0  with two cells:
      * Case Number -> a[href*="caseInfo.asp?caseNumber=PBxxxx-xxxxxx"]
      * Party Name / Business Name -> text (decedent / estate party)
  - Note: "Addresses are not available via the Internet" — no situs from search.

Usage:
    from scrapers.maricopa_probate import search_probate
    records = search_probate(last_name="Smith")   # list of wrapped raw records

For testing without a live browser, pass html= open(...).read() to
parse_probate_results(html).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

SOURCE_ID = "probate_court"
SEARCH_URL = "https://www.superiorcourt.maricopa.gov/docket/ProbateCourtCases/caseSearch.asp"
RESULTS_URL = "https://www.superiorcourt.maricopa.gov/docket/ProbateCourtCases/caseSearchResults.asp"
CASEINFO_URL = "https://www.superiorcourt.maricopa.gov/docket/ProbateCourtCases/caseInfo.asp"
CASE_LINK_RE = re.compile(
    r'href="([^"]*caseInfo\.asp\?caseNumber=([^"&]+))"', re.I)
PARTY_RE = re.compile(
    r'caseInfo\.asp\?caseNumber=[^"]+">\s*([^<]+?)\s*</a>.*?'
    r'col-6 col-lg-9 bold-font">\s*(.*?)\s*</div>',
    re.I | re.S)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_probate_case_detail(html: str) -> dict:
    """Parse a verified probate caseInfo.asp detail page.

    Returns the REAL published party names (adults) + relationship + any
    published mailing address. Maricopa legally suppresses minor names
    ("Party is a minor: name not published") — we surface that verbatim and
    never fabricate a name for a suppressed party.

    Verified against samples/maricopa/probate_caseinfo_live.html (2026-07-11):
      - adult petitioner 'Dianne Woods' (Petitioner PPT) recovered
      - minor party -> 'Party is a minor: name not published' (suppressed)
    """
    parties = []
    # The detail page renders rows as: bold-font label cell + value cell.
    rows = re.findall(
        r'bold-font">\s*([^<]+?)\s*</div>\s*<div[^>]*>\s*(.*?)\s*</div>',
        html, re.I | re.S)
    rel = None
    for label, val in rows:
        label = re.sub(r"\s+", " ", label).strip()
        val = re.sub(r"<[^>]+>", " ", val)
        val = re.sub(r"\s+", " ", val).strip()
        if label == "Party Name":
            rel = None
            parties.append({"name": val, "relationship": None,
                            "suppressed": "minor" in val.lower()})
        elif label == "Relationship" and parties:
            parties[-1]["relationship"] = val
    # Recover the first PUBLISHED (non-suppressed) party name as the lead name.
    lead_name = None
    for p in parties:
        if p["name"] and not p["suppressed"]:
            lead_name = p["name"]
            break
    return {
        "case_detail_fetched": True,
        "parties": parties,
        "lead_party_name": lead_name,
        "all_names_suppressed": lead_name is None and bool(parties),
        "party_count": len(parties),
    }


def fetch_probate_case_detail(case_number: str, *, fetch_fn=None) -> dict:
    """Fetch + parse a single probate case detail page.

    fetch_fn, if provided, is a test seam: callable(case_number) -> html.
    Otherwise a real camoufox browser session is used.
    """
    if fetch_fn is not None:
        return parse_probate_case_detail(fetch_fn(case_number))
    import sys
    sys.path.insert(0, "/root/maricopa_stealth/lib/python3.11/site-packages")
    from camoufox.sync_api import Camoufox
    url = f"{CASEINFO_URL}?caseNumber={case_number}"
    with Camoufox(headless=True, geoip=True) as browser:
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(3500)
        html = page.content()
    return parse_probate_case_detail(html)


def parse_probate_results(html: str) -> list[dict]:
    """Parse the verified live results-grid HTML into wrapped raw records.

    Pure function (no network) — this is what the unit test exercises against
    the captured samples/maricopa/probate_results_live.html.
    """
    records: list[dict] = []
    # Walk each case link; grab the party name from the sibling cell.
    for m in CASE_LINK_RE.finditer(html):
        href, case_number = m.group(1), m.group(2)
        case_number = case_number.strip()
        # Find party cell: search forward from the link to the next
        # 'col-6 col-lg-9 bold-font' block's inner text.
        after = html[m.end():m.end() + 1200]
        pm = re.search(
            r'col-6 col-lg-9 bold-font">\s*(.*?)\s*</div>', after, re.I | re.S)
        party = ""
        if pm:
            party = re.sub(r"<[^>]+>", " ", pm.group(1))
            party = re.sub(r"\s+", " ", party).strip()
            party = party.replace("Addresses are not available via the Internet",
                                  "").strip(", -")
        # Normalize the case number into the canonical PB format.
        raw_payload = {
            "case_number": case_number,
            "party_name": party,
            "case_detail_url": "https://www.superiorcourt.maricopa.gov" + href,
            "doc_type": "PROBATE",
            "source_specific_doc_type": "probate_case",
        }
        records.append({
            "raw_event_id": f"raw_probate_{uuid.uuid4().hex[:12]}",
            "source_id": SOURCE_ID,
            "source_url": RESULTS_URL,
            "source_fetched_at": _now_iso(),
            "raw_payload": raw_payload,
        })
    return records


def search_probate(last_name: str, first_name: str = "",
                   *, fetch_fn=None) -> list[dict]:
    """Run a live probate name search via camoufox and return parsed records.

    fetch_fn, if provided, is a test seam: callable(last_name, first_name) ->
    html string. Otherwise a real camoufox browser session is used.
    """
    if fetch_fn is not None:
        html = fetch_fn(last_name, first_name)
        return parse_probate_results(html)

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
        except Exception as e:  # pragma: no cover — network dependent
            print(f"[maricopa_probate] fill failed: {e}")
        page.click('input[type="submit"][value="Search"]')
        page.wait_for_timeout(4000)
        html = page.content()
    return parse_probate_results(html)


if __name__ == "__main__":
    import json
    # Smoke test against the captured live sample (no network).
    sample = open("samples/maricopa/probate_results_live.html",
                  encoding="utf-8", errors="replace").read()
    recs = parse_probate_results(sample)
    print(json.dumps({
        "records_parsed": len(recs),
        "sample": recs[:2],
    }, indent=2))

#!/usr/bin/env python3
"""Maricopa County Superior Court FAMILY division DIVORCE / DISSOLUTION scraper.

Source: Maricopa County Superior Court -- Family Court Case Information
        https://www.superiorcourt.maricopa.gov/docket/familycourtcases/casesearch.asp
Lead type: Divorce / Dissolution of Marriage (owner-change / distress signal:
a divorcing couple often must sell or transfer the marital home; heirs/transfers
follow. Useful wholesaler signal when joined to a parcel.)

The search form posts lastName -> caseSearchResults.asp and returns real
DRxxxx case rows with party names + caseInfo.asp detail links. Driven via
TinyFish cloud browser (no local browser bundle needed).

Returns framework-canonical raw events.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scrapers" / "_refs"))

SOURCE_ID = "civil_court"  # dissolution cases carry property-transfer distress
SEARCH_URL = "https://www.superiorcourt.maricopa.gov/docket/familycourtcases/casesearch.asp"
RESULTS_URL = "https://www.superiorcourt.maricopa.gov/docket/familycourtcases/caseSearchResults.asp"

SAMPLE_DIR = ROOT / "samples" / "maricopa"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_divorce_search(last_name: str, fetch_fn=None) -> str:
    """Fetch divorce case-search results HTML for a last name."""
    if fetch_fn is not None:
        return fetch_fn(last_name)
    from tinyfish_browser import TinyFishBrowser

    with TinyFishBrowser(SEARCH_URL, timeout_seconds=240) as page:
        page.wait_for_timeout(3000)
        last = page.query_selector('input[name="lastName" i]')
        if last:
            last.fill(last_name)
        btn = page.query_selector('input[type="submit" i], input[value*="Search" i], input[value*="search" i]')
        if btn:
            btn.click()
        page.wait_for_timeout(5000)
        return page.content()


def parse_divorce_search(html: str) -> list[dict]:
    """Parse dissolution case-search results into canonical raw events."""
    events = []
    # Each result: caseNumber=DRxxxx link + party name "Last, First".
    pairs = re.findall(
        r'caseNumber=(DR\d{4}-\d{6})[^>]*>.*?(?:<[^>]+>)*\s*([A-Z][a-z]+,\s*[A-Z][a-z]+(?:\s*[A-Z]\.?)?)',
        html, re.S)
    seen = set()
    for case_number, party in pairs:
        if case_number in seen:
            continue
        seen.add(case_number)
        events.append(_make_event(
            canonical_doc_type="DIVORCE",
            party_name=party.strip(),
            case_number=case_number,
            instrument_number=None,
        ))
    return events


def _make_event(canonical_doc_type, party_name, case_number, instrument_number):
    return {
        "source_id": SOURCE_ID,
        "canonical_doc_type": canonical_doc_type,
        "raw_event_id": f"real_div_{case_number or party_name}",
        "event_date": None,
        "parties": [{"name": party_name, "name_type": "DF", "raw_role": "respondent"}],
        "property_refs": {"case_number": case_number},
        "instrument_number": instrument_number,
        "source_url": f"{RESULTS_URL}?caseNumber={case_number}" if case_number else RESULTS_URL,
        "fetched_at": _now_iso(),
        "evidence": [{"type": "web", "url": SEARCH_URL, "note": "Maricopa Family Court dissolution case search"}],
    }


def search_divorce(surnames, fetch_fn=None, limit_per=8) -> list[dict]:
    out = []
    for sname in surnames:
        try:
            html = fetch_divorce_search(sname, fetch_fn=fetch_fn)
        except Exception as e:
            print(f"  [warn] divorce search '{sname}' failed: {type(e).__name__}: {e}")
            continue
        for ev in parse_divorce_search(html):
            if len(out) >= limit_per:
                return out
            out.append(ev)
    return out


if __name__ == "__main__":
    sample = (SAMPLE_DIR / "divorce_results_live.html").read_text(encoding="utf-8", errors="replace")
    evs = parse_divorce_search(sample)
    print(f"parsed {len(evs)} divorce events (sample)")
    for e in evs[:3]:
        print("  ", e["canonical_doc_type"], e["parties"][0]["name"], e["property_refs"].get("case_number"))

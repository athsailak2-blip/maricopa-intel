#!/usr/bin/env python3
"""Maricopa County Justice Court EVICTION (forcible detainer) scraper.

Source: Maricopa County Justice Courts case search
        https://justicecourts.maricopa.gov/app/courtrecords/casesearch
Lead type: Eviction (occupant distress signal -- often pre-foreclosure or
owner-occupied distress; useful for wholesalers as a distress overlay).

The portal is an ASP.NET WebForms SPA that needs a real browser to drive.
We use the TinyFish cloud browser (no local browser bundle needed) so it
works even when the local disk can't hold camoufox. The page is driven the
same way a local browser would be.

Returns framework-canonical raw events (dicts) for the county pipeline.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or scrapers/ dir.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scrapers" / "_refs"))

SOURCE_ID = "civil_court"  # evictions live in the Justice Courts; mapped to civil_court source role
SEARCH_URL = "https://justicecourts.maricopa.gov/app/courtrecords/casesearch"

SAMPLE_DIR = ROOT / "samples" / "maricopa"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_eviction_search(last_name: str, fetch_fn=None) -> str:
    """Fetch the eviction case-search results HTML for a last name.

    If fetch_fn(last_name) is provided it is used (test seam / captured HTML),
    otherwise a live TinyFish cloud-browser session drives the SPA.

    The Justice Court SPA navigates to
        /app/courtrecords/caseSearchResults?lastName=<name>&FirstName=&DOB=
    and the GridView of cases renders server-side in that page. A direct
    TinyFish GET of that URL returns the grid (verified live: 20 real cases
    for 'Smith').
    """
    if fetch_fn is not None:
        return fetch_fn(last_name)
    from tinyfish_browser import TinyFishBrowser

    results_url = (
        "https://justicecourts.maricopa.gov/app/courtrecords/"
        f"caseSearchResults?lastName={last_name}&FirstName=&DOB="
    )
    with TinyFishBrowser(results_url, timeout_seconds=240) as page:
        page.wait_for_timeout(8000)
        return page.content()


def parse_eviction_search(html: str) -> list[dict]:
    """Parse eviction case-search results into canonical raw events.

    Verified live format (Justice Court caseSearchResults GridView):
      <a ... href="CaseInfo.aspx?casenumber=0703TR9302084">0703TR9302084</a>
      <span ... PartyLabel_0">Minor, Minor</span> - Addresses are not ...
    Party names are redacted by the portal ("Minor, Minor" / "DOB: N/A")
    -- same masking as probate/civil. The case number is the real lead key.
    """
    events = []
    if "did not match any documents" in html.lower():
        return events
    # Each row: casenumber link + PartyLabel. Capture both via the PartyLabel
    # that follows each casenumber link.
    rows = re.findall(
        r'casenumber=([^"&\s]+)[^>]*>([^<]+)</a>.*?PartyLabel_\d+">([^<]*)',
        html, re.S | re.I)
    seen = set()
    for case_number, _linktext, party in rows:
        if case_number in seen:
            continue
        seen.add(case_number)
        party_name = party.strip()
        # Portal masks names ("Minor, Minor" / empty) -- keep as-is; do NOT invent.
        events.append(_make_event(
            canonical_doc_type="EVICTION",
            party_name=party_name or "Redacted",
            case_number=case_number,
            instrument_number=None,
        ))
    return events


def _make_event(canonical_doc_type, party_name, case_number, instrument_number):
    return {
        "source_id": SOURCE_ID,
        "canonical_doc_type": canonical_doc_type,
        "raw_event_id": f"real_evc_{case_number or party_name}",
        "event_date": None,
        "parties": [{"name": party_name, "name_type": "DF", "raw_role": "defendant"}],
        "property_refs": {"case_number": case_number},
        "instrument_number": instrument_number,
        "source_url": f"https://justicecourts.maricopa.gov/app/courtrecords/CaseInfo.aspx?casenumber={case_number}" if case_number else SEARCH_URL,
        "fetched_at": _now_iso(),
        "evidence": [{"type": "web", "url": SEARCH_URL, "note": "Maricopa Justice Court eviction case search"}],
    }


def search_eviction(surnames, fetch_fn=None, limit_per=8) -> list[dict]:
    """Search evictions for several surnames; return up to limit_per events."""
    out = []
    for sname in surnames:
        try:
            html = fetch_eviction_search(sname, fetch_fn=fetch_fn)
        except Exception as e:
            print(f"  [warn] eviction search '{sname}' failed: {type(e).__name__}: {e}")
            continue
        for ev in parse_eviction_search(html):
            if len(out) >= limit_per:
                return out
            out.append(ev)
    return out


if __name__ == "__main__":
    sample = (SAMPLE_DIR / "eviction_results_live.html").read_text(encoding="utf-8", errors="replace")
    evs = parse_eviction_search(sample)
    print(f"parsed {len(evs)} eviction events (sample)")
    for e in evs[:3]:
        print("  ", e["canonical_doc_type"], e["parties"][0]["name"], e["property_refs"].get("case_number"))

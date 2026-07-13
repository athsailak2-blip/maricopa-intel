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

    Verified live: the Justice Court caseSearchResults GridView lists
    cases by casenumber. Party names on the GRID are masked ("Minor,
    Minor"), but the CaseInfo detail page shows the REAL defendant name
    (verified: "Aaron Garcia"). We capture the casenumber here and enrich
    name + type + file date from the CaseInfo detail page in
    search_eviction(). Only FORCIBLE DETAINER cases are kept (the grid also
    returns Civil Traffic / Small Claims which are NOT evictions).
    """
    events = []
    if "did not match any documents" in html.lower():
        return events
    case_numbers = re.findall(r'casenumber=([A-Z0-9]+)', html)
    seen = set()
    for case_number in case_numbers:
        if case_number in seen:
            continue
        seen.add(case_number)
        # Do NOT pre-filter by prefix here: the Justice Court mixes Traffic /
        # Criminal / Forcible Detainer under the same surname search. We keep
        # every case and let search_eviction() confirm the real Case Type from
        # the CaseInfo detail page before keeping it as an eviction lead.
        events.append(_make_event(
            canonical_doc_type="EVICTION",
            party_name="",
            case_number=case_number,
            instrument_number=None,
        ))
    return events


def fetch_eviction_detail(case_number: str, fetch_fn=None) -> dict:
    """Fetch the CaseInfo detail page and extract real defendant + file date.

    The detail page is NOT masked -- it shows the actual party name
    (verified live: 'Defendant: Aaron Garcia'). Returns
    {party_name, file_date, case_type, address}.
    """
    url = f"https://justicecourts.maricopa.gov/app/courtrecords/CaseInfo.aspx?casenumber={case_number}"
    if fetch_fn is not None:
        html = fetch_fn(case_number)
    else:
        from tinyfish_browser import TinyFishBrowser
        try:
            with TinyFishBrowser(url, timeout_seconds=120) as page:
                page.wait_for_timeout(5000)
                html = page.content()
        except Exception as e:
            return {"party_name": "", "file_date": "", "case_type": "", "address": ""}
    party = ""
    m = re.search(r'jc-case-info-header">\s*Party Name\s*</div>\s*<div[^>]*>([^<]+)</div>',
                  html, re.S | re.I)
    if not m:
        m = re.search(r"Party Name</th>\s*<td[^>]*>([^<]+)</td>", html, re.S | re.I)
    if m:
        party = m.group(1).strip()
    filedate = ""
    m = re.search(r'jc-case-info-header">\s*File Date:\s*</div>\s*<div[^>]*>([^<]+)</div>',
                  html, re.S | re.I)
    if not m:
        m = re.search(r"File Date:</th>\s*<td[^>]*>([^<]+)</td>", html, re.S | re.I)
    if m:
        filedate = m.group(1).strip()
    ctype = ""
    # Justice Court CaseInfo does not print a literal "Case Type" label for
    # traffic/criminal; forcible-detainer cases show an ARSCode / description of
    # "Forcible Detainer" / "Eviction". Detect eviction from the description.
    if re.search(r"forcible detainer|eviction", html, re.I):
        ctype = "Forcible Detainer"
    else:
        # non-eviction (traffic/criminal/civil) -> mark so caller can drop
        m = re.search(r'jc-case-info-header">\s*(Case Type|Case Category)\s*</div>\s*<div[^>]*>([^<]+)</div>', html, re.S | re.I)
        if m:
            ctype = m.group(2).strip()
    return {"party_name": party, "file_date": filedate,
            "case_type": ctype, "address": ""}


def _make_event(canonical_doc_type, party_name, case_number, instrument_number,
                file_date="", case_type=""):
    return {
        "source_id": SOURCE_ID,
        "canonical_doc_type": canonical_doc_type,
        "raw_event_id": f"real_evc_{case_number or party_name}",
        "event_date": file_date or None,
        "parties": [{"name": party_name or "Unknown", "name_type": "DF",
                     "raw_role": "defendant"}] if party_name else [],
        "property_refs": {"case_number": case_number},
        "instrument_number": instrument_number,
        "source_url": f"https://justicecourts.maricopa.gov/app/courtrecords/CaseInfo.aspx?casenumber={case_number}" if case_number else SEARCH_URL,
        "fetched_at": _now_iso(),
        "evidence": [{"type": "web", "url": SEARCH_URL,
                      "note": "Maricopa Justice Court eviction case search"}],
    }


def search_eviction(surnames, fetch_fn=None, limit_per=8) -> list[dict]:
    """Search forcible-detainer (eviction) cases; enrich with real party name.

    Skips Civil Traffic / Small Claims (prefix TR/SC). For each kept
    forcible-detainer case, fetches the CaseInfo detail page to capture the
    REAL defendant name + file date (the grid masks names; the detail page
    does not).
    """
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
            cn = ev["property_refs"]["case_number"]
            try:
                det = fetch_eviction_detail(cn, fetch_fn=fetch_fn)
                if det.get("party_name"):
                    ev["parties"] = [{"name": det["party_name"], "name_type": "DF",
                                      "raw_role": "defendant"}]
                if det.get("file_date"):
                    ev["event_date"] = det["file_date"]
                # Keep ONLY forcible-detainer / eviction cases. The Justice
                # Court surname search returns Traffic / Criminal / Civil too;
                # the detail page tells us the real type. Drop everything else.
                ct = (det.get("case_type") or "").lower()
                if "forcible" not in ct and "eviction" not in ct and "detainer" not in ct:
                    continue
                ev["canonical_doc_type"] = "EVICTION"
            except Exception as e:
                print(f"  [warn] eviction detail {cn} failed: {e}")
                continue
            out.append(ev)
    return out


if __name__ == "__main__":
    sample = (SAMPLE_DIR / "eviction_results_live.html").read_text(encoding="utf-8", errors="replace")
    evs = parse_eviction_search(sample)
    print(f"parsed {len(evs)} eviction events (sample)")
    for e in evs[:3]:
        print("  ", e["canonical_doc_type"], e["parties"][0]["name"], e["property_refs"].get("case_number"))

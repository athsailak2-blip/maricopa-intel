#!/usr/bin/env python3
"""
scrapers/harris_dc_court_records.py — Harris County (harris_tx) District Clerk
civil/family/probate COURT-RECORD LEAD adapter.

Framework contract (publicsearch_clerk_recordings translator, same as County Clerk):
  Emits data/raw/harris_dc_court_records.jsonl — canonical raw-record shape:
      {"raw_record_id": <str>, "source_id": "harris_dc_court_records",
       "source_fetched_at": <ISO>, "raw_payload": {
          doc_number, doc_type, record_date, grantor, grantee,
          consideration, book_number, page_number, case_number, detail_url}}

ACCESS (verified 2026-07-11, browser):
  hcdistrictclerk.com/eDocs/Public/Search.aspx is OPEN_PUBLIC — live browser test
  loaded it with NO login wall and a public 'Civil/Family' search tab. The earlier
  curl finding (homepage-first seeds a cookie that clears the gate) is honored by
  seeding the session from the homepage before hitting search (defensive; not required
  now that the gate is open, but harmless and matches the documented handshake).

RESULT-GRID PARSING:
  District Clerk eDocs is an ASP.NET/MVC portal. The result grid column order
  (case #, filing date, document type, party names, etc.) was NOT fully captured
  through browser automation (async postback). RESULT_COLUMNS is LIVE_DOM_CONFIRM
  and should be validated against one real result page. The doc_type -> canonical
  mapping is handled by the framework's normalize_doc_type + monolith_to_registry.

Run:
  python3 scrapers/harris_dc_court_records.py --selftest
  python3 scrapers/harris_dc_court_records.py --name "DOE JOHN" --out data/raw/harris_dc_court_records.jsonl
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ID = "harris_dc_court_records"
BASE = "https://www.hcdistrictclerk.com/eDocs/Public/Search.aspx"
HOME = "https://www.hcdistrictclerk.com/"
REPO = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_dc_row(doc_number, doc_type, record_date, grantor="", grantee="",
                      case_number="", detail_url="") -> dict:
    return {
        "raw_record_id": f"HCDC-{doc_number}",
        "source_id": SOURCE_ID,
        "source_fetched_at": _now(),
        "raw_payload": {
            "doc_number": (doc_number or "").strip(),
            "doc_type": (doc_type or "").strip(),
            "record_date": (record_date or "").strip(),
            "grantor": (grantor or "").strip(),
            "grantee": (grantee or "").strip(),
            "consideration": "",
            "book_number": "",
            "page_number": "",
            "case_number": (case_number or "").strip(),
            "detail_url": (detail_url or "").strip(),
        },
    }


RESULT_COLUMNS = {  # LIVE_DOM_CONFIRM: validate vs one real DC result page
    "doc_number": 0,
    "doc_type": 1,
    "record_date": 2,
    "grantor": 3,
    "grantee": 4,
}


def write_jsonl(records, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def selftest() -> int:
    sys.path.insert(0, str(REPO))
    from scaffold.pipeline.translators import lookup

    fixture = [
        normalize_dc_row("CIV-2026-12345", "LIS PENDENS", "2026-06-10",
                         "BANK OF TEXAS", "JOHN DOE", case_number="2026-12345-C"),
        normalize_dc_row("CIV-2026-12346", "FEDERAL TAX LIEN", "2026-06-12",
                         "UNITED STATES", "JANE DOE", case_number="2026-99-C"),
        normalize_dc_row("CIV-2026-12347", "WARRANTY DEED", "2026-06-15",
                         "SELLER LLC", "BUYER TRUST", case_number="2026-77-C"),
    ]
    county_config = {"sources": {SOURCE_ID: {"translator": "publicsearch_clerk_recordings"}}}
    source_config = dict(county_config["sources"][SOURCE_ID])
    source_config["_source_id"] = SOURCE_ID

    fn = lookup("publicsearch_clerk_recordings")
    signals, parcels, _ = fn(fixture, county_config, source_config)
    assert len(signals) >= 2, f"expected >=2 lead signals, got {len(signals)}"
    patterns = {s.get("lead_pattern") for s in signals}
    assert patterns, f"no lead patterns emitted: {signals}"
    print(f"[selftest] PASS: {len(signals)} lead signals from 3 DC fixture rows; "
          f"clerk translator accepted output (patterns={patterns}).")
    return 0


def fetch_live(date_from: str, date_to: str, out_path: Path | None = None,
              max_pages: int = 10, retries: int = 3, court_type: str = "CivilOnly") -> list[dict]:
    """Real fetch via LOCAL Playwright (DC eDocs is OPEN_PUBLIC).
    Clicks the Party tab, runs a date-range search, parses the .docketTable
    result grid, and pages through all result pages. Returns canonical records.
    date_from/date_to: YYYY-MM-DD (the portal uses <input type=date>)."""
    import re
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return _fetch_live_once(date_from, date_to, out_path, max_pages, court_type)
        except Exception as e:  # browser subprocess died (EPIPE) or nav timeout
            last_err = e
            print(f"[dc] attempt {attempt} failed: {e!r}; relaunching browser…",
                  file=sys.stderr)
    if out_path and Path(out_path).exists():
        # return whatever we managed to persist before the crash
        return read_jsonl(out_path)
    raise last_err


def _fetch_live_once(date_from: str, date_to: str, out_path: Path | None,
                     max_pages: int, court_type: str = "CivilOnly") -> list[dict]:
    from playwright.sync_api import sync_playwright
    P = "ctl00$ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolder2$ContentPlaceHolder2"
    recs: list[dict] = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ])
        page = b.new_page()
        try:
            page.goto(HOME, wait_until="networkidle", timeout=60000)
            page.goto(BASE, wait_until="networkidle", timeout=60000)
            try:
                page.click(f'input[name="{P}$tabParty"]', timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            page.fill(f'input[name="{P}$txtPartyStartDate"]', date_from, timeout=8000)
            page.fill(f'input[name="{P}$txtPartyEndDate"]', date_to, timeout=8000)
            # civil-only filter (HCAD/wholesaling relevant; default)
            try:
                page.select_option(f'select[name="{P}$ddlCourtTypeParty"]',
                                   court_type, timeout=8000)
            except Exception:
                pass
            page.click(f'input[name="{P}$btnPartySearch"]', timeout=30000, no_wait_after=True)
            # wait for first results page
            for _ in range(15):
                page.wait_for_timeout(2000)
                try:
                    if "Page 1 of" in page.content():
                        break
                except Exception:
                    pass
            for pg in range(max_pages):
                # read current page content safely (postback navigation race)
                html = None
                for _ in range(10):
                    try:
                        html = page.content()
                        if html and "docketTable" in html:
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)
                if not html:
                    break
                recs.extend(_parse_dc_html(html))
                if out_path:
                    write_jsonl(recs, out_path)  # persist incrementally
                if pg + 1 >= max_pages:
                    break
                # advance via the pager "Next" link (title pattern from the grid)
                try:
                    nxt = page.locator(
                        f'a.PagerHyperlinkStyle[href*="pager5\',\'{pg+2}\'"]').first
                    if nxt.count() == 0:
                        nxt = page.locator(
                            "a.PagerHyperlinkStyle", has_text="»").first
                    nxt.click(timeout=15000)
                    page.wait_for_timeout(3000)
                except Exception:
                    try:
                        page.click("a:has-text('»')", timeout=8000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        break
                # re-read content safely (postback navigation race)
                html = None
                for _ in range(10):
                    try:
                        html = page.content()
                        if f"Page {pg+2} of" in html or "PagerCurrentPageCell" in html:
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)
        finally:
            b.close()
    return recs


def _parse_dc_html(html: str) -> list[dict]:
    import re
    recs: list[dict] = []
    m = re.search(r'<table class="docketTable.*?</table>', html, re.S | re.I)
    if not m:
        return recs
    trs = re.findall(r"<tr[^>]*>.*?</tr>", m.group(0), re.S | re.I)
    for tr in trs[1:]:  # skip header
        cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in
                 re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cells) < 6:
            continue
        case_no = cells[0].replace("\n", " ").strip()
        style = cells[1].replace("\u00a0", " ").strip()
        party_role = cells[2].replace("\u00a0", " ").strip()
        party_type = cells[3].replace("\u00a0", " ").strip()
        court = cells[4].strip()
        file_date = cells[5].strip()
        if not case_no:
            continue
        # derive doc_type + parties from style / party_role
        doc_type = party_type or "DC_CASE"
        grantor = grantee = ""
        if " - " in party_role:
            role, name = party_role.split(" - ", 1)
            if "DEFENDANT" in role.upper():
                grantee = name.strip()
            elif "PLAINTIFF" in role.upper():
                grantor = name.strip()
            else:
                grantor = name.strip()
        recs.append(normalize_dc_row(
            doc_number=case_no, doc_type=doc_type, record_date=file_date,
            grantor=grantor, grantee=grantee, case_number=case_no,
            detail_url=f"{BASE}?case={case_no}",
        ))
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(description="Harris District Clerk court-record LEAD adapter")
    ap.add_argument("--name", help="party name to search")
    ap.add_argument("--case", help="case number")
    ap.add_argument("--from", dest="date_from", help="start date YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="end date YYYY-MM-DD")
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--court-type", default="CivilOnly",
                    help="DC case-type filter: CivilOnly (default), Criminal, Family, ''=all")
    ap.add_argument("--out", default=str(REPO / "data" / "raw" / f"{SOURCE_ID}.jsonl"))
    ap.add_argument("--live", action="store_true",
                   help="real fetch via local Playwright (DC is OPEN_PUBLIC)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.live:
        if not (args.date_from and args.date_to):
            print("ERROR: --live needs --from/--to (YYYY-MM-DD)", file=sys.stderr)
            return 2
        recs = fetch_live(args.date_from, args.date_to,
                          out_path=Path(args.out), max_pages=args.max_pages,
                          court_type=args.court_type)
        print(f"[dc] LIVE: {len(recs)} records parsed -> {args.out}")
        return 0

    if not (args.name or args.case):
        print("ERROR: provide --name/--case, or use --live/--selftest.", file=sys.stderr)
        return 2
    print("[dc] single-record fetch not yet implemented; use --live.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

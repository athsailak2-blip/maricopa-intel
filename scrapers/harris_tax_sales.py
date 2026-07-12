#!/usr/bin/env python3
"""
scrapers/harris_tax_sales.py — Harris County (harris_tx) Tax Office delinquent
tax-sale / tax-deed auction listing LEAD adapter.

Framework contract (tax_deed_auction_listing translator):
  Emits data/raw/harris_tax_sales.jsonl — canonical raw-record shape:
      {"raw_record_id": <str>, "source_id": "harris_tax_sales",
       "source_fetched_at": <ISO>, "source_url": <url>,
       "raw_payload": {
           parcel_id,      # HCAD account number (e.g. "1212420010001")
           address,        # full street address (inline on listing page)
           opening_bid,    # minimum bid string ("$41,205.46")
           sale_status,    # "For Sale" / "scheduled"
           cause_number,   # Cause# from listing
           precinct,       # Constable precinct 1-8
           sale_type,      # EXE / EOS / SALE ...
       }}

ACCESS (verified 2026-07-12, web_extract):
  https://www.hctax.net/Property/listings/taxsalelisting is OPEN_PUBLIC — no
  login, no Cloudflare. Each listing card exposes:
      - Account#  (== HCAD acct, clean bridge to parcels)
      - Cause#
      - Precinct / Type (EXE, EOS, SALE ...)
      - Adjudged Value / Minimum Bid
      - FULL STREET ADDRESS inline (e.g. "1627 W DONOVAN ST HOUSTON TX 77091")
  => This source yields ADDRESSED leads directly, no HCAD round-trip needed.

The listing page is server-rendered HTML (not a JS app that hides data), so a
plain requests GET + regex parse works WITHOUT a browser. A --live Playwright
path is provided for completeness but the default path is direct HTTP.

Run:
  python3 scrapers/harris_tax_sales.py --selftest
  python3 scrapers/harris_tax_sales.py --out data/raw/harris_tax_sales.jsonl
  python3 scrapers/harris_tax_sales.py --live --out data/raw/harris_tax_sales.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ID = "harris_tax_sales"
LISTING_URL = "https://www.hctax.net/Property/listings/taxsalelisting"
REPO = Path(__file__).resolve().parents[1]

# Match the framework translator's expected raw_payload shape exactly.
REQUIRED_FIELDS = ("parcel_id", "address", "opening_bid", "sale_status")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)          # strip tags
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_tax_row(
    parcel_id: str,
    address: str = "",
    opening_bid: str = "",
    sale_status: str = "For Sale",
    cause_number: str = "",
    precinct: str = "",
    sale_type: str = "",
    source_url: str = LISTING_URL,
) -> dict:
    """Canonical raw-record shape consumed by tax_deed_auction_listing."""
    parcel_id = (parcel_id or "").strip()
    raw = {
        "parcel_id": parcel_id,
        "address": _clean_text(address or ""),
        "opening_bid": (opening_bid or "").strip(),
        "sale_status": (sale_status or "For Sale").strip(),
        "cause_number": (cause_number or "").strip(),
        "precinct": (precinct or "").strip(),
        "sale_type": (sale_type or "").strip(),
    }
    return {
        "raw_record_id": f"{SOURCE_ID}:{parcel_id}:{cause_number}",
        "source_id": SOURCE_ID,
        "source_fetched_at": _now(),
        "source_url": source_url,
        "raw_payload": raw,
    }


def parse_listing_html(html: str) -> list[dict]:
    """Parse the server-rendered tax-sale listing page.

    Verified 2026-07-12 against the LIVE hctax.net HTML (3.9 MB). Card layout:
      <h4><strong class="precinct">Precinct 1</strong> / Type: <strong>EXE 1</strong></h4>
      <div class='For Sale-small'><strong>For Sale</strong></div>
      <div class="account ...">Account#: <strong>1212420010001</strong></div>
      <div class="SuitNumber ...">Cause#: <strong>202543566</strong></div>
      <h3 ...><span class="address">1627 W DONOVAN ST</span><span class="city">HOUSTON</span>...</h3>
      Adjudged Value: $ X  Minimum Bid: $ Y
      View Details

    Account# == HCAD acct (clean parcel bridge); the inline address gives us a
    directly-addressed lead (no HCAD round-trip needed).
    """
    recs: list[dict] = []

    # Segment the page by the Precinct/Type <h4> header.
    header_re = re.compile(
        r"<h4>\s*<strong[^>]*class=\"precinct\"[^>]*>(.*?)</strong>.*?"
        r"Type:\s*<strong[^>]*>(.*?)</strong>",
        re.S | re.I,
    )
    headers = list(header_re.finditer(html))
    if not headers:
        # Fallback: just scan for account blocks.
        headers = []

    # Build card segments: split on each <h4> precinct header found, else whole doc.
    if headers:
        segments = []
        for i, h in enumerate(headers):
            start = h.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(html)
            segments.append(html[start:end])
    else:
        # No h4 headers (unlikely live): split on `Account#:` block markers.
        segments = [html]

    for seg in segments:
        prec_m = re.search(r"class=\"precinct\"[^>]*>(.*?)</strong>", seg, re.S | re.I)
        type_m = re.search(r"Type:\s*<strong[^>]*>(.*?)</strong>", seg, re.S | re.I)
        acct_m = re.search(r"class=\"account[^\"]*\"[^>]*>.*?Account#:\s*<strong>(.*?)</strong>", seg, re.S | re.I)
        if not acct_m:
            # try without the <strong> wrapper
            acct_m = re.search(r"Account#:\s*<strong>(.*?)</strong>", seg, re.S | re.I)
        if not acct_m:
            continue
        parcel_id = re.sub(r"<[^>]+>", "", acct_m.group(1)).strip()

        cause_m = re.search(r"Cause#:\s*<strong>(.*?)</strong>", seg, re.S | re.I)
        cause = re.sub(r"<[^>]+>", "", cause_m.group(1)).strip() if cause_m else ""

        # Inline address: <span class="address">STREET</span><span class="city">CITY</span>
        #                 <span class="state">TX</span><span class="zip">77091</span>
        addr_m = re.search(
            r"class=\"address\"[^>]*>(.*?)</span>\s*"
            r"<span[^>]*class=\"city\"[^>]*>(.*?)</span>\s*"
            r"<span[^>]*class=\"state\"[^>]*>(.*?)</span>\s*"
            r"<span[^>]*class=\"zip\"[^>]*>(.*?)</span>",
            seg, re.S | re.I,
        )
        if addr_m:
            street = re.sub(r"<[^>]+>", " ", addr_m.group(1)).strip()
            city = addr_m.group(2).strip()
            state = addr_m.group(3).strip()
            zipc = addr_m.group(4).strip()
            address = f"{street} {city} {state} {zipc}".strip()
        else:
            address = ""

        bid_m = re.search(r"Minimum Bid\**\s*[:#]?\s*\**\s*\$?\s*([\d,]+\.\d{2})", seg, re.I)
        adj_m = re.search(r"Adjudged Value\**\s*[:#]?\s*\**\s*\$?\s*([\d,]+\.\d{2})", seg, re.I)
        opening_bid = (f"${bid_m.group(1)}" if bid_m else (f"${adj_m.group(1)}" if adj_m else ""))

        sale_status = "For Sale" if re.search(r"For Sale", seg, re.I) else "scheduled"
        precinct = re.sub(r"<[^>]+>", "", prec_m.group(1)).strip() if prec_m else ""
        sale_type = re.sub(r"<[^>]+>", "", type_m.group(1)).strip() if type_m else ""

        recs.append(normalize_tax_row(
            parcel_id=parcel_id, address=address, opening_bid=opening_bid,
            sale_status=sale_status, cause_number=cause, precinct=precinct,
            sale_type=sale_type,
        ))
    return recs


def _fetch_html(url: str, use_browser: bool = False) -> str:
    if use_browser:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            pg = b.new_page()
            pg.goto(url, wait_until="networkidle", timeout=60000)
            html = pg.content()
            b.close()
            return html
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Xcerebro bot)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def write_jsonl(records: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def selftest() -> int:
    """Prove the adapter normalizes into the translator's expected shape."""
    sys.path.insert(0, str(REPO))
    from scaffold.pipeline.translators import lookup

    fixture_html = """
    <h4><strong class="precinct">Precinct 1</strong> / Type: <strong>SALE 1</strong></h4>
    <div class='For Sale-small'><strong>For Sale</strong></div>
    <div class="row">
      <div class="account text-nowrap col-12 col-lg-6">Account#: <strong>0985300000015</strong></div>
      <div class="SuitNumber text-nowrap col-xs-12 col-sm-12 col-lg-6 ">Cause#: <strong>202132139</strong></div>
    </div>
    <h3><span class="address">5605 KASHMERE ST</span><span class="city">HOUSTON</span><span class="state">TX</span><span class="zip">77026-2319</span></h3>
    Adjudged Value: $ 102,401.00 Minimum Bid: $ 41,205.46
    View Details
    """
    recs = parse_listing_html(fixture_html)
    assert recs, "selftest: no records parsed"
    r0 = recs[0]
    payload = r0["raw_payload"]
    for fld in REQUIRED_FIELDS:
        assert payload.get(fld) != "" or fld in ("address",), f"selftest missing {fld}"
    assert payload["parcel_id"] == "0985300000015"
    assert payload["address"] == "5605 KASHMERE ST HOUSTON TX 77026-2319", payload["address"]
    assert payload["opening_bid"] == "$41,205.46", payload["opening_bid"]

    # Confirm the framework translator accepts it.
    fn = lookup("tax_deed_auction_listing")
    sigs, parcels, _ = fn([r0], {}, {"_source_id": SOURCE_ID})
    assert sigs and sigs[0]["doc_type"] == "tax_deed", "translator rejected shape"
    assert parcels and parcels[0]["situs_address"], "parcel missing address"
    print(f"selftest OK: {len(recs)} parsed; translator -> {len(sigs)} signal(s), "
          f"{len(parcels)} parcel(s); address={parcels[0]['situs_address']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Harris County Tax Office tax-sale adapter")
    ap.add_argument("--out", default="data/raw/harris_tax_sales.jsonl")
    ap.add_argument("--live", action="store_true", help="fetch live via HTTP (default) / browser")
    ap.add_argument("--browser", action="store_true", help="use Playwright instead of requests")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    html = _fetch_html(LISTING_URL, use_browser=args.browser)
    recs = parse_listing_html(html)
    n = write_jsonl(recs, Path(args.out))
    print(f"[tax] {'LIVE ' if args.live or args.browser else ''}parsed {n} tax-sale listings -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

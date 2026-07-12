#!/usr/bin/env python3
"""
Maricopa County -- Assessor Parcel Master (enrichment) scraper.

County-scoped adapter (repo-root scrapers/, per AGENTS.md). Produces framework-
canonical WRAPPED RAW RECORDS (MASTER_PROMPT 4.32).

VERIFIED FACTS (live recon 2026-07-11):
  - The Maricopa Assessor publishes parcel/owner/valuation data as OPEN DATA
    (no auth, no Cloudflare, no API key) via the county Open Data portal:
        https://data-maricopa.opendata.arcgis.com  (MaricopaAssessorGIS)
    Datasets include "Residential Master", "Apartment Master", "Commercial
    Master", "Personal Property", etc. Each is a CSV-Collection whose /data
    endpoint returns a ZIP containing a pipe-delimited .txt (1.4M+ rows for
    Residential Master) + a File Spec .docx.
  - Residential Master item id (verified): e22983d41d91490d90965544b718a120
    Direct download: https://www.arcgis.com/sharing/rest/content/items/
        e22983d41d91490d90965544b718a120/data
  - File is PIPE-DELIMITED (|), 39 columns. Real sample row:
       10101020|1.00|CLASS R3|1|RF - REFRIGERATION|Yes|6|FS - FRAME STUCCO|
       CT - CONCRETE TILE|N/A|2010|1446|1446|0|0|0|G2-380|CV-120 ; CV-120|0|
       111574|2010-08-01|0|0|0131|SILLIVAN LAURA M|706 S 114TH LN||AVONDALE|
       AZ|85323|USA|706|S|114TH|LN|||AVONDALE|85323
    Column positions (verified from real data):
       0  parcel_number          20 class
       1  acreage_or_units        21 improvement_value
       2  class_code             22 land_value
       3  ??? (1)                23 ??? (0131 - maybe subdivision/tax-area)
       4  ??? (cooling)          24 OWNER_NAME
       5  ??? (Yes)              25 SITUS_ADDRESS (house+st)
       6  ??? (6)                26 situs_address2
       7  ??? (exterior)         27 SITUS_CITY
       8  ??? (roof)             28 SITUS_STATE
       9  ??? (N/A)              29 SITUS_ZIP
       10 year_built             30 SITUS_COUNTRY
       11 living_area            31 mail_house_no
       12 building_area          32 mail_dir
       13 ???                    33 mail_street
       14 ???                    34 mail_street_type
       15 ???                    35 mail_unit
       16 parking_code           36 mail_unit2
       17 patio_code             37 MAIL_CITY
       18 ???                    38 MAIL_ZIP
       19 ??? (111574 - maybe assessor value)
  Only fields confirmed present in real data are mapped; unknown positions are
  carried as raw_column_N (never invented). Enrichment only -- never a lead.

USAGE:
    from scrapers.maricopa_parcel_master import fetch_parcel_master, parse_parcel_lines
    records = fetch_parcel_master()           # downloads + parses open data
    records = parse_parcel_lines(open("fixture.txt").read().splitlines())
"""
from __future__ import annotations

import io
import json
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone

SOURCE_ID = "parcel_master"

# Verified open-data item ids (MaricopaAssessorGIS, ArcGIS Online).
# Residential Master covers most single-family parcels; Apartment/Commercial
# cover the rest. Default to Residential Master.
OPEN_DATA_ITEMS = {
    "residential": "e22983d41d91490d90965544b718a120",
    "apartment":   "0b5770a1b73f4637b8f92f088465890b",
}
DEFAULT_ITEM = OPEN_DATA_ITEMS["residential"]
DOWNLOAD_URL = "https://www.arcgis.com/sharing/rest/content/items/{item}/data"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _map_row(cols: list[str]) -> dict:
    """Map the 39 pipe-delimited columns to a canonical raw_payload.

    Only fields verified present in real data are named; unknowns are kept as
    raw_column_N so nothing is fabricated.
    """
    def g(i):
        return cols[i].strip() if i < len(cols) else ""
    return {
        "parcel_number": g(0),
        "acreage_or_units": g(1) or None,
        "class_code": g(2) or None,
        "year_built": g(10) or None,
        "living_area": g(11) or None,
        "building_area": g(12) or None,
        "parking_code": g(16) or None,
        "patio_code": g(17) or None,
        "improvement_value": g(21) or None,
        "land_value": g(22) or None,
        "owner_name": g(24) or None,
        "situs_address": g(25) or None,
        "situs_address2": g(26) or None,
        "situs_city": g(27) or None,
        "situs_state": g(28) or None,
        "situs_zip": g(29) or None,
        "situs_country": g(30) or None,
        "mail_house_no": g(31) or None,
        "mail_dir": g(32) or None,
        "mail_street": g(33) or None,
        "mail_street_type": g(34) or None,
        "mail_unit": g(35) or None,
        "mail_city": g(37) or None,
        "mail_zip": g(38) or None,
        # unverified positions carried without fabrication
        "raw_column_3": g(3) or None,
        "raw_column_4": g(4) or None,
        "raw_column_5": g(5) or None,
        "raw_column_6": g(6) or None,
        "raw_column_7": g(7) or None,
        "raw_column_8": g(8) or None,
        "raw_column_9": g(9) or None,
        "raw_column_13": g(13) or None,
        "raw_column_14": g(14) or None,
        "raw_column_15": g(15) or None,
        "raw_column_18": g(18) or None,
        "raw_column_19": g(19) or None,
        "raw_column_20": g(20) or None,
        "raw_column_23": g(23) or None,
        "raw_column_26": g(26) or None,
        "raw_column_35": g(35) or None,
        "raw_column_36": g(36) or None,
        "source_specific_doc_type": "assessor_parcel_master",
    }


def parse_parcel_lines(lines, *, limit: int | None = None) -> list[dict]:
    """Parse pipe-delimited parcel-master lines into wrapped raw records.

    `lines` is an iterable of strings (the .txt content split by newline).
    The first line is treated as a header only if it does not start with a
    digit (parcel numbers start with digits, so a non-digit first line is a
    header). Verified data has no header row.
    """
    records: list[dict] = []
    started = False
    for ln in lines:
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        # skip a literal header line if present
        if not started:
            if not ln[0].isdigit():
                continue
            started = True
        cols = ln.split("|")
        if len(cols) < 25:
            # not a parcel row (too few columns) -- skip silently
            continue
        raw = _map_row(cols)
        if not raw["parcel_number"]:
            continue
        records.append({
            "raw_event_id": f"raw_parcel_{uuid.uuid4().hex[:12]}",
            "source_id": SOURCE_ID,
            "source_url": DOWNLOAD_URL.format(item=DEFAULT_ITEM),
            "source_fetched_at": _now_iso(),
            "raw_payload": raw,
        })
        if limit and len(records) >= limit:
            break
    return records


def fetch_parcel_master(*, item: str = DEFAULT_ITEM,
                        fetch_fn=None, limit: int | None = None) -> list[dict]:
    """Download + parse the open-data parcel master.

    fetch_fn(item_id) -> bytes (ZIP) is a test seam. Otherwise downloads the
    real ArcGIS Open Data ZIP (auth-free).
    """
    if fetch_fn is not None:
        data = fetch_fn(item)
    else:
        url = DOWNLOAD_URL.format(item=item)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    z = zipfile.ZipFile(io.BytesIO(data))
    txt = [n for n in z.namelist() if n.endswith(".txt")]
    if not txt:
        return []
    content = z.read(txt[0]).decode("utf-8", "replace").splitlines()
    return parse_parcel_lines(content, limit=limit)


if __name__ == "__main__":
    recs = fetch_parcel_master(limit=3)
    print(json.dumps({"records": len(recs), "sample": recs[:1]}, indent=2))

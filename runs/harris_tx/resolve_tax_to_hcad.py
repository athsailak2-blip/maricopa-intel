"""Harris County: resolve Tax Office account# -> HCAD parcel owner / valuation / address.

COUNTY-SCOPED (runs/harris_tx/). Does NOT modify universal framework code.

VERIFIED JOIN CHAIN:
  Tax Office listing  parcel_id (Account#)  e.g. "0032490000007"
      -> HCAD real_acct.txt  acct column (exact match)
      -> owner name + site_addr_1 (street) + legal + assessed value

The Tax Office listing already carries an inline street address (190/272 of them),
but HCAD adds OWNER NAME + ASSESSED VALUE + legal description + exemption flags —
richer enrichment for the tax-deed leads. No fuzzy matching: the Account# IS the
native HCAD acct.

OPTIMIZED: streams real_acct.txt and keeps ONLY the keys we need (the input
account numbers), so it runs in seconds. County-side script only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # runs/harris_tx/ -> .. -> repo root
REAL_ACCT = Path("/tmp/hcad/tsv/real_acct.txt")
TAX_RAW = REPO / "data" / "raw" / "harris_tax_sales.jsonl"
OUT = REPO / "data" / "raw" / "harris_tax_hcad_resolved.jsonl"


def _acct_keys(tax_jsonl: Path) -> set:
    keys = set()
    with open(tax_jsonl) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            acct = rec.get("raw_payload", {}).get("parcel_id", "").strip()
            if acct:
                keys.add(acct)
    return keys


def _parse_real_acct(stream, wanted: set) -> dict:
    """real_acct.txt is tab-separated, header row first.
    Columns (Harris/HCAD): acct, yr, ... site_addr_1, site_addr_2, site_addr_3,
    site_city, site_zip, lgl_1..4, owner..., val_..."""
    out = {}
    header = None
    for line in stream:
        line = line.rstrip("\n")
        if not line:
            continue
        cols = line.split("\t")
        if header is None:
            header = cols
            # find key column indexes
            idx = {name.lower(): i for i, name in enumerate(header)}
            i_acct = idx.get("acct")
            i_addr1 = idx.get("site_addr_1")
            i_addr2 = idx.get("site_addr_2")
            i_addr3 = idx.get("site_addr_3")
            i_city = idx.get("site_city")
            i_zip = idx.get("site_zip")
            i_owner = idx.get("owner_name") or idx.get("owner")
            i_legal = idx.get("lgl_1")
            i_val = idx.get("val_tx_assessed") or idx.get("assessed") or idx.get("tot_appr_val")
            continue
        if i_acct is None or len(cols) <= i_acct:
            continue
        acct = cols[i_acct].strip()
        if acct not in wanted:
            continue
        addr_parts = [cols[i] for i in (i_addr1, i_addr2, i_addr3) if i is not None and i < len(cols) and cols[i].strip()]
        addr = " ".join(p.strip() for p in addr_parts if p.strip())
        city = cols[i_city].strip() if i_city is not None and i_city < len(cols) else ""
        zipc = cols[i_zip].strip() if i_zip is not None and i_zip < len(cols) else ""
        owner = cols[i_owner].strip() if i_owner is not None and i_owner < len(cols) else ""
        legal = cols[i_legal].strip() if i_legal is not None and i_legal < len(cols) else ""
        val = cols[i_val].strip() if i_val is not None and i_val < len(cols) else ""
        out[acct] = {
            "account": acct,
            "owner_name": owner,
            "situs_address": f"{addr} {city} {zipc}".strip(),
            "legal_description": legal,
            "assessed_value": val,
        }
    return out


def main() -> int:
    if not REAL_ACCT.exists():
        print(f"[tax->hcad] missing HCAD bulk: {REAL_ACCT}", file=sys.stderr)
        return 2
    wanted = _acct_keys(TAX_RAW)
    print(f"[tax->hcad] {len(wanted)} tax accounts to resolve against HCAD")
    with open(REAL_ACCT, encoding="utf-8", errors="replace") as fh:
        resolved = _parse_real_acct(fh, wanted)
    print(f"[tax->hcad] resolved {len(resolved)}/{len(wanted)} to HCAD parcels")

    # Write a resolved file: account -> HCAD owner/value/address
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for acct, info in resolved.items():
            f.write(json.dumps({"account": acct, **info}, ensure_ascii=False) + "\n")
    print(f"[tax->hcad] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

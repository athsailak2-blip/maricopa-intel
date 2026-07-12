"""County-scoped: build the public dashboard payload (data/leads.json) from the
ENRICHED scored leads, surfacing every REAL field the build produced and clearing
the stale REVIEW_REQUIRED flag for leads that were actually enriched.

Does NOT touch universal framework code. Maps the enriched scored_leads.json ->
the dashboard record display fields the front-end renders:
  parcel_display / primary_parcel_id -> display_parcel (PARCEL column)
  parcel_display (street)            -> display_address
  attributes[situs_address]          -> display_address (fallback)
  attributes[assessed_value]         -> display_assessed_value
  attributes[legal_description]      -> display_attributes (so it shows on board)
  owner_name (real)                  -> display_owner
  primary_source_urls                -> mapped from source_ids
For ENRICHED leads: clear review_flags + set display_lead_status=CONFIRMED.

Honesty rule: do NOT invent owner names or vary scores. Where the source has no
owner (tax-deed sales list no owner), show "Owner not listed" — never the raw
"tax_deed against unidentified party" placeholder, never a fabricated name.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DASHBOARD = REPO / "data" / "dashboard.json"
ENRICHED = REPO / "data" / "scored_leads.json"
OUT = REPO / "data" / "leads.json"

TAX_SOURCE_URL = "https://www.hctax.net/Property/TaxSales/Index"
CLERK_SOURCE_URL = "https://cclerk.hctx.net/applications/websearch/FRCL_R.aspx"

PLACEHOLDER_OWNER = "tax_deed against unidentified party"


def attr_get(rec, key):
    for a in rec.get("attributes", []):
        if a.get("key") == key:
            return a.get("value")
    return None


def main():
    dash = json.loads(DASHBOARD.read_text())
    enriched = {r["lead_id"]: r for r in json.loads(ENRICHED.read_text())}
    records = dash["records"]
    patched = 0
    for r in records:
        e = enriched.get(r.get("lead_id"))
        if not e:
            continue
        # address (street)
        addr = e.get("parcel_display") or attr_get(e, "situs_address") or ""
        if addr.strip():
            r["display_address"] = addr.strip()
        # parcel id (account number)
        pid = e.get("primary_parcel_id") or ""
        r["display_parcel"] = pid.strip()
        # owner — only if a REAL name exists (never "against unidentified party")
        owner = e.get("owner_name") or ""
        if owner.strip() and "against unidentified party" not in owner:
            r["display_owner"] = owner.strip()
        else:
            r["display_owner"] = "Owner not listed"
        # assessed value
        val = attr_get(e, "assessed_value")
        if val not in (None, ""):
            try:
                r["display_assessed_value"] = int(float(val))
            except (ValueError, TypeError):
                pass
        # attributes: surface legal_description on the board
        attrs = []
        legal = attr_get(e, "legal_description")
        if legal:
            attrs.append(legal)
        if attrs:
            r["display_attributes"] = attrs
        # source URL(s)
        srcs = e.get("source_ids") or []
        urls = []
        if "harris_tax_sales" in srcs:
            urls.append(TAX_SOURCE_URL)
        if "harris_clerk_real_property" in srcs:
            urls.append(CLERK_SOURCE_URL)
        if urls:
            r["primary_source_urls"] = urls
        # clear stale review flag for enriched leads
        if e.get("enrichment_status") == "ENRICHED":
            r["review_flags"] = []
            if r.get("display_lead_status") == "REVIEW_REQUIRED":
                r["display_lead_status"] = "CONFIRMED"
            patched += 1
    dash["records"] = records
    OUT.write_text(json.dumps(dash, indent=1))
    total = len(records)
    with_addr = sum(1 for r in records if (r.get("display_address") or "").strip())
    with_owner = sum(1 for r in records if (r.get("display_owner") or "") not in ("", "Owner not listed"))
    print(f"wrote {OUT}")
    print(f"records: {total} | enriched/patched: {patched} | with address: {with_addr} | with real owner: {with_owner}")


if __name__ == "__main__":
    main()

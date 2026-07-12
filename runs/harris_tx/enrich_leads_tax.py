"""Harris County: post-build enrichment of scored leads with Tax Office addresses.

COUNTY-SCOPED (runs/harris_tx/). Does NOT modify universal framework code.

The Xcerebro matcher joins signals<->parcels by ADDRESS, so the tax source's
inline situs addresses (190 of 272 listings) are not surfaced on the scored
leads automatically. This script decorates scored leads with the tax parcel's
street address by joining on the Tax Office account# (= HCAD acct = parcel_id).

Run AFTER a production build:
  python3 runs/harris_tx/enrich_leads_tax.py
Reads: data/raw/harris_tax_sales.jsonl (parcel_id + address), data/scored_leads.json
Writes: data/scored_leads.json (in place) with situs_address injected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TAX_RAW = REPO / "data" / "raw" / "harris_tax_sales.jsonl"
SCORED = REPO / "data" / "scored_leads.json"
MATCHED = REPO / "data" / "matched_leads.json"


def _account_from_lead(lead: dict) -> str:
    """Extract the tax account# / parcel id from a scored lead."""
    # primary_parcel_id may hold the account (e.g. 0032490000007)
    pid = lead.get("primary_parcel_id") or ""
    m = re.search(r"(\d{6,13})", pid)
    if m:
        return m.group(1)
    # fall back: search source_ids + lead_id
    if "harris_tax_sales" in (lead.get("source_ids") or []):
        m = re.search(r"(\d{6,13})", lead.get("lead_id", ""))
        if m:
            return m.group(1)
    return ""


def main() -> int:
    # Build account -> address map from the tax raw listings.
    acct_addr: dict[str, str] = {}
    if TAX_RAW.exists():
        for line in TAX_RAW.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            p = r.get("raw_payload", {})
            acct = (p.get("parcel_id") or "").strip()
            addr = (p.get("address") or "").strip()
            if acct and addr:
                acct_addr[acct] = addr

    if not acct_addr:
        print("[enrich_tax] no tax addresses found; nothing to do")
        return 0

    if not SCORED.exists():
        print("[enrich_tax] scored_leads.json not found; run a build first")
        return 1

    leads = json.loads(SCORED.read_text(encoding="utf-8"))
    enriched = 0
    for lead in leads:
        if "harris_tax_sales" not in (lead.get("source_ids") or []):
            continue
        acct = _account_from_lead(lead)
        addr = acct_addr.get(acct)
        if not addr:
            continue
        # Inject address into the lead (decorate, don't break framework shape).
        if not lead.get("parcel_display"):
            lead["parcel_display"] = addr
        if lead.get("primary_parcel_id") in (None, "", "None"):
            lead["primary_parcel_id"] = acct
        # record as an attribute too
        attrs = lead.get("attributes") or []
        if isinstance(attrs, list):
            if not any(a.get("key") == "situs_address" for a in attrs if isinstance(a, dict)):
                attrs.append({"key": "situs_address", "value": addr, "source": "harris_tax_sales"})
            lead["attributes"] = attrs
        lead["enrichment_status"] = "ENRICHED"
        enriched += 1

    SCORED.write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[enrich_tax] leads={len(leads)} tax_leads_enriched_with_address={enriched} -> {SCORED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

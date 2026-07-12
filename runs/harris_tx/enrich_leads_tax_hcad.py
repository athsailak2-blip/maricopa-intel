"""Harris County: fold HCAD owner/value/address into tax-deed leads (post-build).

COUNTY-SCOPED (runs/harris_tx/). Does NOT modify universal framework code.

Companion to enrich_leads_tax.py (which injects the Tax Office's inline address).
This step adds the HCAD-derived OWNER NAME + ASSESSED VALUE + legal description for
the tax leads whose account# resolved against HCAD's bulk (real_acct.txt).

Join key: Tax Office parcel_id (Account#) == HCAD acct == resolved account in
data/raw/harris_tax_hcad_resolved.jsonl.

Run AFTER:
  - a production build (data/scored_leads.json exists)
  - resolve_tax_to_hcad.py (data/raw/harris_tax_hcad_resolved.jsonl exists)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESOLVED = REPO / "data" / "raw" / "harris_tax_hcad_resolved.jsonl"
SCORED = REPO / "data" / "scored_leads.json"


def _account_from_lead(lead: dict) -> str:
    pid = lead.get("primary_parcel_id") or ""
    m = re.search(r"(\d{6,13})", pid)
    if m:
        return m.group(1)
    if "harris_tax_sales" in (lead.get("source_ids") or []):
        m = re.search(r"(\d{6,13})", lead.get("lead_id", ""))
        if m:
            return m.group(1)
    return ""


def main() -> int:
    if not RESOLVED.exists():
        print("[enrich_tax_hcad] no HCAD resolution file; run resolve_tax_to_hcad.py first")
        return 0
    hcad: dict[str, dict] = {}
    for line in RESOLVED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        hcad[r.get("account", "").strip()] = r

    if not hcad:
        print("[enrich_tax_hcad] HCAD resolution empty; nothing to do")
        return 0
    if not SCORED.exists():
        print("[enrich_tax_hcad] scored_leads.json missing; run a build first")
        return 1

    leads = json.loads(SCORED.read_text(encoding="utf-8"))
    enriched = 0
    for lead in leads:
        if "harris_tax_sales" not in (lead.get("source_ids") or []):
            continue
        acct = _account_from_lead(lead)
        info = hcad.get(acct)
        if not info:
            continue
        attrs = lead.get("attributes") or []
        if not isinstance(attrs, list):
            attrs = []
        existing = {a.get("key") for a in attrs if isinstance(a, dict)}
        for key in ("owner_name", "assessed_value", "legal_description", "situs_address"):
            val = info.get(key)
            if val and key not in existing:
                attrs.append({"key": key, "value": val, "source": "harris_hcad_parcel"})
                existing.add(key)
        lead["attributes"] = attrs
        # upgrade owner_name on the lead itself if still generic
        if (lead.get("owner_name") or "").startswith("tax_deed against"):
            if info.get("owner_name"):
                lead["owner_name"] = info["owner_name"]
        enriched += 1

    SCORED.write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[enrich_tax_hcad] leads={len(leads)} tax_leads_enriched_with_hcad={enriched} -> {SCORED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

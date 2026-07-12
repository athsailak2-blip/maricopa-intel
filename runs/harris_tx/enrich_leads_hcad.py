"""Harris County: post-build enrichment of scored leads with HCAD situs addresses.

COUNTY-SCOPED (runs/harris_tx/). Does NOT modify universal framework code.

WHY: The Xcerebro Clerk translator hard-sets parcel situs_address="" and the
matcher joins signals<->parcels by address (Clerk signals carry no address), so
the Clerk->HCAD bridge (resolve_clerk_to_hcad.py) cannot inject addresses into
the build directly. This script runs AFTER build_leads.py and decorates the
already-built scored leads with the resolved HCAD street address + owner + acct,
exactly per the framework rule "enrichment sources decorate event-originated
leads" (they never create lead rows).

JOIN KEY: lead.primary_parcel_id  ==  "harris_clerk_real_property" + <doc_number>
          bridge record raw_record_id == "HCDC-..."? NO. Bridge records keep the
          Clerk adapter's raw_record_id, which is "HARRIS-CLERK-<doc_number>".
          We re-derive the doc_number from raw_payload.doc_number and match on it.

INPUTS:
  data/harris_real/scored_leads.json   (build output)
  data/raw/harris_clerk_*_resolved.jsonl  (bridge output, any; merged)
OUTPUT:
  overwrites data/harris_real/scored_leads.json with enrichment fields added:
    - attributes.situs_address / owner_name / account / legal_description
    - parcel_display  (human string)
    - enrichment_status  ("ENRICHED_HCAD" if resolved else unchanged)
"""
from __future__ import annotations
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
OUT_DIR = REPO / "data" / "harris_real"
BRIDGE_GLOB = "harris_clerk_*_resolved.jsonl"

SOURCE_PREFIX = "harris_clerk_real_property"


def _doc_of(rec: dict) -> str:
    rp = rec.get("raw_payload", {})
    d = (rp.get("doc_number") or rec.get("doc_number") or "").strip()
    m = re.search(r"(RP-\d{4}-\d+)", d, re.I)
    return m.group(1).upper() if m else d.upper()


def load_bridge() -> dict:
    """doc_number -> resolved parcel info (first hit wins)."""
    out: dict = {}
    for f in sorted(RAW.glob(BRIDGE_GLOB)):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            doc = _doc_of(rec)
            if not doc:
                continue
            addr = rec.get("_resolved_address", "").strip()
            if addr and doc not in out:
                out[doc] = {
                    "situs_address": addr,
                    "owner_name": rec.get("_resolved_owner", "").strip(),
                    "account": rec.get("_resolved_acct", "").strip(),
                    "legal_description": rec.get("_resolved_legal", "").strip(),
                }
    return out


def main() -> int:
    bridge = load_bridge()
    scored = OUT_DIR / "scored_leads.json"
    if not scored.exists():
        print(f"ERROR: {scored} not found — run build_leads.py first", flush=True)
        return 2
    leads = json.loads(scored.read_text())
    total = len(leads)
    enriched = 0
    for lead in leads:
        # doc number lives in lead_id ("lead_unresolved_RP-2026-261507")
        # or primary_parcel_id ("harris_clerk_real_propertyRP-..."); try both
        hay = " ".join(str(x) for x in [lead.get("lead_id", ""),
                                        lead.get("primary_parcel_id", "")])
        m = re.search(r"(RP-\d{4}-\d+)", hay, re.I)
        doc = m.group(1).upper() if m else ""
        info = bridge.get(doc)
        if not info:
            continue
        attrs = lead.setdefault("attributes", {})
        attrs["situs_address"] = info["situs_address"]
        if info["owner_name"]:
            attrs["owner_name_hcad"] = info["owner_name"]
        if info["account"]:
            attrs["hcad_account"] = info["account"]
        if info["legal_description"]:
            attrs["legal_description"] = info["legal_description"]
        lead["parcel_display"] = info["situs_address"]
        lead["enrichment_status"] = "ENRICHED_HCAD"
        enriched += 1
    scored.write_text(json.dumps(leads, indent=2))
    print(f"[enrich] leads={total} enriched_with_hcad_address={enriched} -> {scored}",
          flush=True)
    # show a few
    for lead in leads[:0]:
        pass
    shown = 0
    for lead in leads:
        if lead.get("enrichment_status") == "ENRICHED_HCAD" and shown < 5:
            print("   ", lead.get("primary_parcel_id"), "->",
                  lead.get("parcel_display"), "| acct:",
                  lead.get("attributes", {}).get("hcad_account"))
            shown += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

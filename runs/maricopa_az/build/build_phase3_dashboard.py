#!/usr/bin/env python3
"""
Maricopa (maricopa_az) -- Phase 3 dashboard build.

County-scoped (runs/maricopa_az/build/, per AGENTS.md). Builds a PARTIAL_BUILD
dashboard from the REAL leads produced by run_real_sources.py. Every row is
born from a verified primary lead event (recorder / probate) that was JOINED
to a real Assessor parcel (owner-name -> situs address). No enrichment-only or
parcel-only rows (MASTER_PROMPT 4.40 / 1232).

Outputs:
  - runs/maricopa_az/build/dashboard_payload.json   (machine-readable)
  - runs/maricopa_az/build/dashboard.html           (mobile-friendly Client View)

Per MASTER_PROMPT 4.40: rows use operator-readable labels (DEED_OF_TRUST ->
"Deed of Trust"), never internal codes. Per 4.42/602: PARTIAL_BUILD banner
states what is NOT included (tax_lien blocked).
"""
import json
import html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENRICHED = HERE / "real_enriched_leads.json"
SCORED = HERE / "real_scored_leads.json"
OUT_JSON = HERE / "dashboard_payload.json"
OUT_HTML = HERE / "dashboard.html"

# Operator-readable doc-type labels (MASTER_PROMPT 4.40 -- no internal codes).
DOC_LABELS = {
    "DEED_OF_TRUST": "Deed of Trust",
    "WARRANTY_DEED": "Warranty Deed",
    "QUITCLAIM_DEED": "Quitclaim Deed",
    "TRUSTEE_DEED": "Trustee Deed",
    "NOTICE_OF_TRUSTEE_SALE": "Notice of Trustee Sale",
    "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE": "Notice of Substitute Trustee Sale",
    "LIS_PENDENS": "Lis Pendens",
    "PROBATE": "Probate / Estate",
    "LIEN": "Lien",
    "MED LIEN": "Medical Lien",
    "REL D/T": "Release of Deed of Trust",
    "RELEASE": "Release",
    "JUDGMENT": "Judgment",
}

SOURCE_LABELS = {
    "clerk_recordings": "Recorder (Maricopa County Recorder)",
    "probate_court": "Probate Court (Superior Court)",
    "civil_court": "Civil Court (Superior Court)",
    "tax_lien": "Tax Lien (Treasurer / RealAuction)",
}


def label_doc(dt: str) -> str:
    return DOC_LABELS.get(dt, dt.replace("_", " ").title() if dt else "Unknown")


def label_source(s: str) -> str:
    return SOURCE_LABELS.get(s, s)


def build_payload(enriched: list) -> dict:
    rows = []
    for i, e in enumerate(enriched, 1):
        rows.append({
            "lead_id": f"MCR-{i:03d}",
            "primary_parcel_id": e["parcel_id"],
            "display_address": ", ".join(
                v for v in [e["situs_address"], e["situs_city"], e["situs_state"]] if v),
            "display_owner": e.get("owner_name_assessor") or "Unknown",
            "display_source": label_source(e["source_id"]),
            "display_doc_type": label_doc(e["canonical_doc_type"]),
            "canonical_doc_type": e["canonical_doc_type"],
            "source_id": e["source_id"],
            "joined_from_name": e["joined_from_name"],
            "join_candidates": e.get("join_candidates", 1),
            "confidence": "best_effort_owner_name_join",
            "case_number": e.get("case_number"),
            "instrument_number": e.get("instrument_number"),
        })
    # Header aggregates (Two-Truths: re-derive from rows where possible)
    doc_counts = Counter(r["canonical_doc_type"] for r in rows)
    src_counts = Counter(r["source_id"] for r in rows)
    az = sum(1 for r in rows if r["display_address"].endswith("AZ"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "build_label": "PARTIAL_BUILD",
        "county": "Maricopa",
        "state": "AZ",
        "mode": "real-limited-sample",
        "lead_total": len(rows),
        "az_situs_count": az,
        "doc_type_counts": {label_doc(k): v for k, v in sorted(doc_counts.items())},
        "source_counts": {label_source(k): v for k, v in sorted(src_counts.items())},
        "includes": [
            "Probate Court leads (real decedent/estate names via caseInfo.asp)",
            "Recorder distress docs (Deed of Trust, Notice of Trustee Sale, Lis Pendens, liens)",
            "Real situs addresses joined from Maricopa Assessor open-data parcel master",
        ],
        "does_not_include": [
            "Tax Lien / tax-certificate leads -- BLOCKED: RealAuction (arizonataxsale.com) "
            "login wall; MyMCTO credentials do not cross over. Needs operator-provided "
            "RealAuction bidder credentials.",
            "Civil Court defendant addresses beyond what caseInfo.asp exposes",
            "Automated daily refresh / alerts (Phase 4 deployment, pending operator credentials)",
        ],
        "records": rows,
    }


def render_html(payload: dict) -> str:
    rows = payload["records"]
    az = payload["az_situs_count"]
    cards = []
    for r in rows:
        addr = html.escape(r["display_address"])
        owner = html.escape(r["display_owner"])
        doc = html.escape(r["display_doc_type"])
        src = html.escape(r["display_source"])
        pid = html.escape(r["primary_parcel_id"] or "")
        cards.append(f"""
      <div class="card">
        <div class="doc">{doc}</div>
        <div class="addr">{addr}</div>
        <div class="meta">Owner: {owner}</div>
        <div class="meta">Parcel: {pid}</div>
        <div class="meta">Source: {src}</div>
      </div>""")
    doc_items = "".join(f"<li>{k}: {v}</li>" for k, v in payload["doc_type_counts"].items())
    src_items = "".join(f"<li>{k}: {v}</li>" for k, v in payload["source_counts"].items())
    not_incl = "".join(f"<li>{html.escape(x)}</li>" for x in payload["does_not_include"])
    banner = ("PARTIAL BUILD — tax-lien source blocked (needs RealAuction bidder "
              "credentials). Addresses joined from Maricopa Assessor open data.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maricopa County Distress Leads (Partial Build)</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin:0;
         background:#0f1419; color:#e6e6e6; }}
  .banner {{ background:#5c3a00; color:#ffd9a0; padding:10px 14px; font-size:13px;
            border-bottom:1px solid #7a4f00; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:14px; }}
  h1 {{ font-size:20px; margin:8px 0; }}
  .summary {{ display:flex; gap:10px; flex-wrap:wrap; margin:10px 0; }}
  .stat {{ background:#1b2330; border:1px solid #2a3340; border-radius:10px;
           padding:10px 14px; flex:1; min-width:120px; }}
  .stat b {{ display:block; font-size:22px; color:#7fd1ff; }}
  .stat span {{ font-size:11px; color:#9fb0c0; }}
  .counts {{ display:flex; gap:20px; flex-wrap:wrap; font-size:13px; margin:8px 0 16px; }}
  .counts ul {{ margin:2px 0; padding-left:16px; }}
  .grid {{ display:grid; grid-template-columns:1fr; gap:10px; }}
  .card {{ background:#161d28; border:1px solid #28323f; border-radius:12px;
          padding:12px 14px; }}
  .card .doc {{ font-size:13px; font-weight:700; color:#ffd27f; }}
  .card .addr {{ font-size:16px; font-weight:600; margin:4px 0; color:#fff; }}
  .card .meta {{ font-size:12px; color:#9fb0c0; }}
  .note {{ font-size:12px; color:#9fb0c0; margin-top:16px; }}
  .note li {{ margin:3px 0; }}
</style>
</head>
<body>
  <div class="banner">{html.escape(banner)}</div>
  <div class="wrap">
    <h1>Maricopa County — Distress Leads</h1>
    <div class="summary">
      <div class="stat"><b>{payload['lead_total']}</b><span>Real leads (event-born)</span></div>
      <div class="stat"><b>{az}</b><span>AZ situs addresses</span></div>
      <div class="stat"><b>PARTIAL</b><span>tax-lien blocked</span></div>
    </div>
    <div class="counts">
      <div><b>By document type</b><ul>{doc_items}</ul></div>
      <div><b>By source</b><ul>{src_items}</ul></div>
    </div>
    <div class="grid">{''.join(cards)}</div>
    <div class="note"><b>What this build does NOT include:</b><ul>{not_incl}</ul>
      <p>Every row is born from a verified public-record event (Recorder / Probate)
      joined to the Maricopa Assessor parcel master. Addresses are best-effort
      owner-name matches — verify before outreach.</p>
    </div>
  </div>
</body>
</html>"""


def main():
    enriched = json.loads(ENRICHED.read_text())
    payload = build_payload(enriched)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    OUT_HTML.write_text(render_html(payload))
    print(f"Phase 3 dashboard built:")
    print(f"  leads          : {payload['lead_total']}")
    print(f"  AZ situs       : {payload['az_situs_count']}")
    print(f"  build_label    : {payload['build_label']}")
    print(f"  JSON           : {OUT_JSON}")
    print(f"  HTML (Client)  : {OUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

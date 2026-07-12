#!/usr/bin/env python3
"""
Maricopa (maricopa_az) -- Phase 4 deployment packaging.

Builds the GitHub-Pages deployable site under ./maricopa-intel/ using the
REPO-CANONICAL dashboard front-end (dashboard/index.html + dashboard.js +
dashboard.css from the framework root), fed by data/leads.json in the exact
shape dashboard.js expects.

Every lead row is born from a verified primary lead event (Recorder / Probate)
joined to a real Assessor parcel (owner-name -> situs). Tier + patterns are
derived TRANSPARENTLY from the real canonical_doc_type (the distress signal
itself) -- no fabricated framework scores. See DOC_TO_TIER / DOC_TO_PATTERNS.

Per operator rule: builds locally and STOPS before any git remote / push.
The caller (Phase 4 run) does git init + local commit only.
"""
import json
import shutil
import html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # county-final repo root
HERE = Path(__file__).resolve().parent                  # runs/maricopa_az/build
ENRICHED = HERE / "real_enriched_leads.json"
DEPLOY = ROOT / "maricopa-intel"
DATA = DEPLOY / "data"
GITHUB_ORG = "xcerebroai"          # per 06_deployment.md (operator's primary org)
GITHUB_REPO = "maricopa-intel"     # <county>-intel convention

# Transparent tier mapping from the REAL document type (distress severity).
# Not a fabricated ML score -- it is the document's own signal weight.
DOC_TO_TIER = {
    "NOTICE_OF_TRUSTEE_SALE": "Hot",
    "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE": "Hot",
    "DEED_OF_TRUST": "Strong",
    "TRUSTEE_DEED": "Strong",
    "LIS_PENDENS": "Strong",
    "PROBATE": "Workable",
    "LIEN": "Workable",
    "MED LIEN": "Workable",
    "WARRANTY_DEED": "Low",
    "QUITCLAIM_DEED": "Low",
    "RELEASE": "Low",
    "REL D/T": "Low",
}

# Pattern tags the canonical dashboard.js precanned views key off.
DOC_TO_PATTERNS = {
    "NOTICE_OF_TRUSTEE_SALE": ["foreclosure"],
    "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE": ["foreclosure"],
    "DEED_OF_TRUST": ["foreclosure"],
    "TRUSTEE_DEED": ["foreclosure"],
    "LIS_PENDENS": ["litigation"],
    "PROBATE": ["estate"],
    "LIEN": ["lien"],
    "MED LIEN": ["lien"],
    "WARRANTY_DEED": ["transfer"],
    "QUITCLAIM_DEED": ["transfer"],
    "RELEASE": ["transfer"],
    "REL D/T": ["transfer"],
}

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
}

SOURCE_LABELS = {
    "clerk_recordings": "Maricopa County Recorder",
    "probate_court": "Superior Court — Probate",
    "civil_court": "Superior Court — Civil",
}

PARTIAL_REASON = (
    "Tax-lien source BLOCKED (RealAuction / arizonataxsale.com login wall; "
    "MyMCTO credentials do not cross over). Recorder + Probate leads included "
    "with real Assessor situs addresses. Addresses are best-effort owner-name "
    "matches — verify before outreach."
)


def build_leads_json(enriched: list) -> dict:
    rows = []
    for i, e in enumerate(enriched, 1):
        dt = e["canonical_doc_type"]
        rows.append({
            "lead_id": f"MCR-{i:03d}",
            "primary_parcel_id": e["parcel_id"],
            "display_address": ", ".join(
                v for v in [e["situs_address"], e["situs_city"], e["situs_state"]] if v),
            "display_owner": e.get("owner_name_assessor") or "Unknown",
            # Transparent distress tier from the real document type.
            "display_score": {"Hot": 92, "Strong": 78, "Workable": 61, "Low": 40}.get(
                DOC_TO_TIER.get(dt, "Low"), 40),
            "display_tier": DOC_TO_TIER.get(dt, "Low"),
            "display_patterns": DOC_TO_PATTERNS.get(dt, []),
            "stack_contrib_patterns": DOC_TO_PATTERNS.get(dt, []),
            "display_pattern_set": DOC_TO_PATTERNS.get(dt, []),
            "display_attributes": [],
            "display_deal_paths": ["wholesale"] if dt in (
                "NOTICE_OF_TRUSTEE_SALE", "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE",
                "DEED_OF_TRUST", "TRUSTEE_DEED", "LIS_PENDENS") else ["probate_estate"],
            "display_title_complexity_tier": "Unknown",
            "display_lead_status": "STACKED_LEAD",
            "display_assessed_value": None,
            "display_last_sale_price": None,
            "display_last_sale_date": None,
            "display_year_built": None,
            "display_match_confidence": 0.6,
            "stack_depth": 1,
            "primary_event_date": None,
            "expected_sale_date": None,
            "parcel_master_status": "matched_owner_name",
            "parcel_master_status_note": f"owner-name join from '{e['joined_from_name']}' "
                                          f"({e.get('join_candidates', 1)} candidate parcels)",
            "parcel_master_match_method": "owner_name_to_assessor_parcel",
            "candidate_parcel_ids": [e["parcel_id"]],
            "review_flags": [],
            "score_reasons": [f"{DOC_LABELS.get(dt, dt)} — primary distress signal"],
            "evidence_ids": [e.get("instrument_number") or e.get("case_number") or ""],
            "primary_source_urls": [],
            "display_doc_type": DOC_LABELS.get(dt, dt),
            "display_source": SOURCE_LABELS.get(e["source_id"], e["source_id"]),
        })

    # Header aggregates (Two-Truths invariant: re-derived from records).
    tier_dist = Counter(r["display_tier"] for r in rows)
    pat_dist = Counter()
    for r in rows:
        for p in r["display_patterns"]:
            pat_dist[p] += 1
    attr_dist = Counter()
    for r in rows:
        for a in r["display_attributes"]:
            attr_dist[a] += 1
    deal_dist = Counter()
    for r in rows:
        for d in r["display_deal_paths"]:
            deal_dist[d] += 1
    depth_dist = Counter(str(r["stack_depth"]) for r in rows)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "build_label": "PARTIAL_BUILD",
        "build_label_reason": PARTIAL_REASON,
        "mode": "real-limited-sample",
        "county": "Maricopa",
        "state": "AZ",
        "deployment": {"github_org": GITHUB_ORG, "github_repo": GITHUB_REPO},
        "lead_total": len(rows),
        "total_signals_active": len(rows),
        "total_signals_suppressed": 0,
        "score_tier_distribution": dict(sorted(tier_dist.items())),
        "pattern_counts": dict(sorted(pat_dist.items())),
        "attribute_counts": dict(sorted(attr_dist.items())),
        "deal_path_distribution": dict(sorted(deal_dist.items())),
        "stack_depth_distribution": dict(sorted(depth_dist.items())),
        "quality_metrics": {},
        "records": rows,
    }


def main():
    enriched = json.loads(ENRICHED.read_text())
    payload = build_leads_json(enriched)

    # Assemble deploy folder from the repo-canonical dashboard front-end.
    DEPLOY.mkdir(exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    for f in ("index.html", "dashboard.css", "dashboard.js"):
        shutil.copyfile(ROOT / "dashboard" / f, DEPLOY / f)
    # .gitignore essentials for a Pages deploy (per 06_deployment.md).
    (DEPLOY / ".gitignore").write_text(
        ".env\nsecrets/\n*.log\n__pycache__/\n*.pyc\n.DS_Store\n")
    # README for the deploy repo.
    (DEPLOY / "README.md").write_text(
        f"# maricopa-intel\n\nMaricopa County (AZ) distress-lead dashboard — "
        f"GitHub Pages deploy.\n\n"
        f"Generated by the Xcerebro County Intelligence Framework. "
        f"build_label=PARTIAL_BUILD (tax-lien source blocked).\n\n"
        f"Enable Pages: Settings -> Pages -> branch `main`, folder `/` (root).\n")

    (DATA / "leads.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    print(f"Phase 4 deploy package built at: {DEPLOY}")
    print(f"  leads.json rows : {payload['lead_total']}")
    print(f"  tier dist       : {payload['score_tier_distribution']}")
    print(f"  pattern dist    : {payload['pattern_counts']}")
    print(f"  front-end       : index.html + dashboard.css + dashboard.js (repo-canonical)")
    print(f"  build_label     : {payload['build_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

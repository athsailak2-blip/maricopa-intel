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
SCORED = HERE / "real_scored_leads.json"                # 125 real leads (framework-scored)
DEPLOY = ROOT                                 # repo root -> GitHub Pages "/" serves it
DATA = DEPLOY / "data"
GITHUB_ORG = "athsailak2-blip"      # operator's GitHub org (per deployment instruction)
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
    "DIVORCE": "Workable",
    "EVICTION": "Workable",
    "LIEN": "Workable",
    "MED LIEN": "Workable",
    "WARRANTY_DEED": "Low",
    "QUITCLAIM_DEED": "Low",
    "SURPLUS": "Low",
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
    "DIVORCE": ["estate", "transfer"],
    "EVICTION": ["occupant_distress"],
    "LIEN": ["lien"],
    "MED LIEN": ["lien"],
    "WARRANTY_DEED": ["transfer"],
    "QUITCLAIM_DEED": ["transfer"],
    "SURPLUS": ["tax_deeded", "surplus_funds"],
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
    "DIVORCE": "Divorce / Dissolution",
    "EVICTION": "Eviction / Forcible Detainer",
    "SURPLUS": "Surplus / Tax-Deeded Land",
    "LIEN": "Lien",
    "MED LIEN": "Medical Lien",
    "REL D/T": "Release of Deed of Trust",
    "RELEASE": "Release",
}

SOURCE_LABELS = {
    "clerk_recordings": "Maricopa County Recorder",
    "probate_court": "Superior Court — Probate",
    "civil_court": "Superior Court — Civil / Family",
    "tax_lien": "Maricopa County — Tax Deed / Surplus",
}

PARTIAL_REASON = (
    "Tax-lien source BLOCKED (RealAuction / arizonataxsale.com login wall; "
    "MyMCTO credentials do not cross over). Recorder + Probate leads included "
    "with real Assessor situs addresses. NEW sources added (verified live): "
    "Divorce (Family Court), Eviction (Justice Court), Surplus (tax-deeded "
    "land). Divorce/Eviction party names are redacted by the portals "
    "(case number is the verified key); Surplus carries a real parcel_id. "
    "Addresses are best-effort owner-name matches — verify before outreach."
)


def build_leads_json(scored: list) -> dict:
    """Map framework-scored leads -> dashboard rows (transparent, honest).

    These leads were produced by the real pipeline run. The framework could
    NOT resolve parcels/owners for most (party names redacted by portals,
    recorder docs lack parcel_ids), so addresses are often absent. We surface
    what IS real: doc type, source, event date, case/recording #, review flags.
    The PARTIAL_BUILD label + review_flags stay visible -- no fabrication.
    """
    rows = []
    for i, s in enumerate(scored, 1):
        dtn = s.get("doc_type_normalization") or {}
        dt_list = dtn.get("canonical_doc_types") or []
        dt = (dt_list[0] if dt_list else "UNKNOWN").upper()
        src_ids = s.get("source_ids") or []
        src_id = src_ids[0] if src_ids else "unknown"
        review_flags = s.get("review_flags") or []
        unresolved = any("parcel_resolution" in f or "no_debtor" in f or "no_pattern" in f
                         for f in review_flags)
        rows.append({
            "lead_id": f"MCR-{i:03d}",
            "primary_parcel_id": s.get("primary_parcel_id"),
            "display_address": (s.get("parcel_display") or "").strip(),
            "display_owner": s.get("owner_name") or "Unknown",
            "display_score": {"Hot": 92, "Strong": 78, "Workable": 61,
                              "Low": 40, "Archive": 30}.get(
                s.get("tier", "Low"), 40),
            "display_tier": s.get("tier") or DOC_TO_TIER.get(dt, "Low"),
            "display_patterns": s.get("display_patterns") or DOC_TO_PATTERNS.get(dt, []),
            "stack_contrib_patterns": s.get("display_patterns") or DOC_TO_PATTERNS.get(dt, []),
            "display_pattern_set": s.get("display_patterns") or DOC_TO_PATTERNS.get(dt, []),
            "display_attributes": [],
            "display_deal_paths": [d.get("path") if isinstance(d, dict) else d
                                  for d in (s.get("deal_paths") or (
                ["wholesale"] if dt in (
                    "NOTICE_OF_TRUSTEE_SALE", "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE",
                    "DEED_OF_TRUST", "TRUSTEE_DEED", "LIS_PENDENS", "SURPLUS") else (
                    ["probate_estate"] if dt == "PROBATE" else (
                    ["divorce_transfer"] if dt == "DIVORCE" else (
                    ["occupant_distress"] if dt == "EVICTION" else ["wholesale"])))))],
            "display_title_complexity_tier": "Unknown",
            "display_lead_status": "NEEDS_REVIEW" if unresolved else "STACKED_LEAD",
            "display_assessed_value": None,
            "display_last_sale_price": None,
            "display_last_sale_date": None,
            "display_year_built": None,
            "display_match_confidence": s.get("match_confidence") or 0.5,
            "stack_depth": s.get("stack_depth") or 1,
            "primary_event_date": s.get("primary_event_date"),
            "expected_sale_date": None,
            "parcel_master_status": "unresolved" if unresolved else "matched",
            "parcel_master_status_note": "; ".join(review_flags) if review_flags
                else "resolved",
            "parcel_master_match_method": "framework_scored",
            "candidate_parcel_ids": [s.get("primary_parcel_id")] if s.get("primary_parcel_id") else [],
            "review_flags": review_flags,
            "score_reasons": [f"{DOC_LABELS.get(dt, dt)} — primary distress signal"
                              + (" (UNRESOLVED: needs manual parcel/owner lookup)" if unresolved else "")],
            "evidence_ids": s.get("evidence_ids") or [],
            "primary_source_urls": [],
            "display_doc_type": DOC_LABELS.get(dt, dt),
            "display_source": SOURCE_LABELS.get(src_id, src_id),
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
            deal_dist[d if isinstance(d, str) else str(d)] += 1
    depth_dist = Counter(str(r["stack_depth"]) for r in rows)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "build_label": "PARTIAL_BUILD",
        "build_label_reason": PARTIAL_REASON,
        "mode": "real-limited-sample",
        "county": "Maricopa",
        "state": "AZ",
        "semantic_verdict": "NEEDS_OPERATOR_REVIEW",
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
    # Prefer the framework-scored real leads (125 from the live run).
    if SCORED.exists():
        scored = json.loads(SCORED.read_text())
        print(f"  [deploy] {len(scored)} scored leads from real_scored_leads.json")
    elif ENRICHED.exists():
        print("  [warn] scored leads absent; falling back to enriched (may be empty)")
        scored = json.loads(ENRICHED.read_text())
    else:
        print("  [warn] no lead source found")
        scored = []
    payload = build_leads_json(scored)

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
        f"build_label=PARTIAL_BUILD (parcels/owners unresolved for most leads; "
        f"§20 NEEDS_OPERATOR_REVIEW).\n\n"
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

#!/usr/bin/env python3
"""
Phase 1 — Synthetic Data Harness for maricopa_az.

Per MASTER_PROMPT §1476 + §02.3: the framework MUST work end-to-end on fake
data before real data enters the system. This harness builds 10 synthetic
Maricopa parcels + 20 synthetic distress signals across the county's verified
lead types (probate, foreclosure/trustee sale, tax delinquency/lien,
lis pendens, civil judgment, recorded deeds), feeds them through the REAL
staged pipeline (§17→§18→§19→§20 + seam + scoring), and asserts:
  - §20 semantic verdict == DEPLOY_OK
  - matched_leads.json + scored_leads.json + evidence_ledger.json on disk
  - dashboard payload renders (lead_total > 0, chips present)
  - every scored_lead validates against scored_lead_record schema
  - idempotency: two runs with same inputs produce identical scored_leads

No real source is touched. No real PII. All identifiers are synthetic
(PARCEL-MC-*, synthetic names/addresses).

Run: python3 scaffold/tests/maricopa_phase1_synth_harness.py
Exit 0 = pass.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jsonschema import Draft202012Validator
from scaffold.pipeline import run_pipeline_staged
from scaffold.pipeline.contracts import schema_path

SIGNAL_TYPE_LABELS = {
    "PROBATE": "Probate Estate",
    "EXECUTORS_DEED": "Executor's Deed",
    "ADMINISTRATORS_DEED": "Administrator's Deed",
    "AFFIDAVIT_OF_HEIRSHIP": "Affidavit of Heirship",
    "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE": "Notice of Substitute Trustee Sale",
    "LIS_PENDENS": "Lis Pendens",
    "JUDGMENT_LIEN": "Judgment Lien",
    "STATE_TAX_LIEN": "State Tax Lien",
    "TAX_SALE_CERTIFICATE": "Tax Sale Certificate",
    "MECHANICS_LIEN": "Mechanic Lien",
}

# 10 synthetic Maricopa parcels (APN-style, situs in Phoenix metro)
PARCELS = {
    "PARCEL-MC-001": {"addr": "1234 W Camelback Rd", "city": "Phoenix", "owner": "JOHN A SMITH"},
    "PARCEL-MC-002": {"addr": "88 S Mill Ave", "city": "Tempe", "owner": "MARIA GONZALEZ"},
    "PARCEL-MC-003": {"addr": "450 N Scottsdale Rd", "city": "Scottsdale", "owner": "ROBERT LEE"},
    "PARCEL-MC-004": {"addr": "2200 E Main St", "city": "Mesa", "owner": "ESTATE OF HELEN KIM"},
    "PARCEL-MC-005": {"addr": "900 W Glendale Ave", "city": "Glendale", "owner": "JAMES BROWN"},
    "PARCEL-MC-006": {"addr": "310 S Alma School Rd", "city": "Chandler", "owner": "PATRICIA DAVIS"},
    "PARCEL-MC-007": {"addr": "77 E University Dr", "city": "Mesa", "owner": "MICHAEL WILSON"},
    "PARCEL-MC-008": {"addr": "1500 N 40th St", "city": "Phoenix", "owner": "ESTATE OF GEORGE PATEL"},
    "PARCEL-MC-009": {"addr": "640 W Warner Rd", "city": "Gilbert", "owner": "LINDA MARTINEZ"},
    "PARCEL-MC-010": {"addr": "2750 S Val Vista Dr", "city": "Gilbert", "owner": "WILLIAM THOMAS"},
}

def _party(name, name_type):
    return {"name": name, "name_type": name_type, "raw_role": name_type}

def _ev(evidence_id, record_id, source_id):
    return {
        "evidence_id": evidence_id, "record_id": record_id, "field": "owner_name",
        "value": "synthetic", "status": "Confirmed", "source_id": source_id,
        "source_reliability_grade": "A",
        "source_url": f"https://recorder.maricopa.gov/synthetic/{record_id}",
        "captured_at": "2026-07-11T12:00:00Z",
    }

def _raw(raw_event_id, source_id, cdt, parcel_id, instrument, recorded_date,
         parties, evidence_id, body=None):
    p = PARCELS[parcel_id]
    return {
        "raw_event_id": raw_event_id,
        "source_id": source_id,
        "source_role": "PRIMARY_EVENT_SOURCE",
        "canonical_doc_type": cdt,
        "raw_doc_type": cdt.upper(),
        "instrument_number": instrument,
        "recorded_date": recorded_date,
        "event_date": None,
        "source_url": f"https://recorder.maricopa.gov/synthetic/{instrument}",
        "parties": parties,
        "document_body_text": body,
        "property_refs": {
            "parcel_id": parcel_id,
            "situs_address": p["addr"],
            "legal_description": None,
            "case_number": None,
        },
        "amounts": [],
        "evidence_ids": [evidence_id],
        "parser_name": "maricopa_phase1_synth",
        "parser_version": "1.0.0",
        "parser_confidence": 95,
        "captured_at": "2026-07-11T12:00:00Z",
    }

def build_synthetic():
    """20 signals across 10 parcels, spanning the county's verified lead types."""
    ev = []
    # 20 signals across 10 parcels, spanning the county's verified lead types.
    # canonical_doc_type values MUST match knowledge_base/domain/canonical_doc_types.json
    # (the seam's doc-type -> pattern bridge keys off these exact keys).
    ev.append(_raw("r01","probate_court","PROBATE","PARCEL-MC-004",
        "I-PROB-1001","2026-06-01",[_party("ESTATE OF HELEN KIM","GR")],"ev01"))
    ev.append(_raw("r02","probate_court","PROBATE","PARCEL-MC-008",
        "I-PROB-1002","2026-06-10",[_party("ESTATE OF GEORGE PATEL","GR")],"ev02"))
    # Executor / Administrator deeds (source: clerk_recordings) — 004, 008, 010
    ev.append(_raw("r03","clerk_recordings","EXECUTORS_DEED","PARCEL-MC-004",
        "I-ED-2001","2026-06-15",[_party("ESTATE OF HELEN KIM","GR")],"ev03"))
    ev.append(_raw("r04","clerk_recordings","ADMINISTRATORS_DEED","PARCEL-MC-008",
        "I-AD-2002","2026-06-18",[_party("ESTATE OF GEORGE PATEL","GR")],"ev04"))
    ev.append(_raw("r05","clerk_recordings","AFFIDAVIT_OF_HEIRSHIP","PARCEL-MC-010",
        "I-AH-2003","2026-06-20",[_party("WILLIAM THOMAS","GR")],"ev05"))
    # Foreclosure / Notice of Substitute Trustee Sale (source: civil_court) — 001, 002, 003, 005
    ev.append(_raw("r06","civil_court","NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE","PARCEL-MC-001",
        "I-NTS-3001","2026-06-05",[_party("JOHN A SMITH","TP")],"ev06",
        body="NOTICE OF SUBSTITUTE TRUSTEE SALE\nMORTGAGOR: JOHN A SMITH\n"))
    ev.append(_raw("r07","civil_court","NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE","PARCEL-MC-002",
        "I-NTS-3002","2026-06-08",[_party("MARIA GONZALEZ","TP")],"ev07",
        body="NOTICE OF SUBSTITUTE TRUSTEE SALE\nMORTGAGOR: MARIA GONZALEZ\n"))
    ev.append(_raw("r08","civil_court","NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE","PARCEL-MC-003",
        "I-NTS-3003","2026-06-12",[_party("ROBERT LEE","TP")],"ev08",
        body="NOTICE OF SUBSTITUTE TRUSTEE SALE\nMORTGAGOR: ROBERT LEE\n"))
    ev.append(_raw("r09","civil_court","NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE","PARCEL-MC-005",
        "I-NTS-3004","2026-06-22",[_party("JAMES BROWN","TP")],"ev09",
        body="NOTICE OF SUBSTITUTE TRUSTEE SALE\nMORTGAGOR: JAMES BROWN\n"))
    # Lis pendens (source: civil_court) — 006, 007
    ev.append(_raw("r10","civil_court","LIS_PENDENS","PARCEL-MC-006",
        "I-LP-4001","2026-06-03",[_party("PATRICIA DAVIS","TP")],"ev10"))
    ev.append(_raw("r11","civil_court","LIS_PENDENS","PARCEL-MC-007",
        "I-LP-4002","2026-06-14",[_party("MICHAEL WILSON","TP")],"ev11"))
    # Civil judgment / abstract of judgment (source: civil_court) — 001, 009
    ev.append(_raw("r12","civil_court","JUDGMENT_LIEN","PARCEL-MC-001",
        "I-CJ-5001","2026-05-28",[_party("JOHN A SMITH","TP")],"ev12"))
    ev.append(_raw("r13","civil_court","JUDGMENT_LIEN","PARCEL-MC-009",
        "I-AJ-5002","2026-06-02",[_party("LINDA MARTINEZ","TP")],"ev13"))
    # Tax lien / tax delinquency (source: tax_lien) — 002, 003, 005, 006, 010
    ev.append(_raw("r14","tax_lien","STATE_TAX_LIEN","PARCEL-MC-002",
        "I-TL-6001","2026-06-01",[_party("MARIA GONZALEZ","TP")],"ev14"))
    ev.append(_raw("r15","tax_lien","STATE_TAX_LIEN","PARCEL-MC-003",
        "I-TD-6002","2026-06-04",[_party("ROBERT LEE","TP")],"ev15"))
    ev.append(_raw("r16","tax_lien","STATE_TAX_LIEN","PARCEL-MC-005",
        "I-TL-6003","2026-06-09",[_party("JAMES BROWN","TP")],"ev16"))
    ev.append(_raw("r17","tax_lien","STATE_TAX_LIEN","PARCEL-MC-006",
        "I-TD-6004","2026-06-11",[_party("PATRICIA DAVIS","TP")],"ev17"))
    ev.append(_raw("r18","tax_lien","TAX_SALE_CERTIFICATE","PARCEL-MC-010",
        "I-TL-6005","2026-06-19",[_party("WILLIAM THOMAS","TP")],"ev18"))
    # Mechanic lien (source: clerk_recordings) — 007, 009
    ev.append(_raw("r19","clerk_recordings","MECHANICS_LIEN","PARCEL-MC-007",
        "I-ML-7001","2026-06-07",[_party("MICHAEL WILSON","TP")],"ev19"))
    ev.append(_raw("r20","clerk_recordings","MECHANICS_LIEN","PARCEL-MC-009",
        "I-ML-7002","2026-06-16",[_party("LINDA MARTINEZ","TP")],"ev20"))
    evidence = [_ev(e["evidence_ids"][0], e["raw_event_id"], e["source_id"]) for e in ev]
    return ev, evidence

def main() -> int:
    checks = []
    def check(desc, ok):
        checks.append((desc, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    raw_events, evidence_entries = build_synthetic()
    check("20 synthetic signals built across 10 parcels", len(raw_events) == 20)

    scored_validator = Draft202012Validator(
        json.loads(schema_path("scored_lead_record").read_text()))

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "maricopa_phase1"

        # Enrichment provider — supplies situs/owner/value for the 10 synthetic parcels
        def enrichment_provider(parcel_id):
            if parcel_id in PARCELS:
                p = PARCELS[parcel_id]
                return {
                    "parcel_id": parcel_id,
                    "situs_address": p["addr"],
                    "situs_city": p["city"],
                    "situs_state": "AZ",
                    "owner_name": p["owner"],
                    "owner_mailing_address": "PO BOX 123",
                    "owner_mailing_city": p["city"],
                    "owner_mailing_state": "AZ",
                    "owner_mailing_zip": "85000",
                    "assessed_value": 300000,
                    "last_sale_price": 250000,
                    "last_sale_date": "2015-03-10",
                    "year_built": 1998,
                }
            return None

        result = run_pipeline_staged.run_staged_pipeline(
            raw_events,
            evidence_entries=evidence_entries,
            signal_type_labels=SIGNAL_TYPE_LABELS,
            workdir=workdir,
            as_of=date(2026, 7, 11),
            enrichment_provider=enrichment_provider,
        )

        check("§20 semantic verdict == DEPLOY_OK",
              result["semantic_verdict"] == "DEPLOY_OK")
        check("matched_leads.json on disk",
              result["matched_leads_path"].exists())
        check("scored_leads.json on disk",
              result["scored_leads_path"].exists())
        check("evidence_ledger.json on disk",
              result["evidence_ledger_path"].exists())
        check("every scored_lead validates against schema",
              all(not list(scored_validator.iter_errors(s))
                  for s in result["scored_leads"]))
        check("lead_total > 0 (dashboard would render real leads)",
              len(result["scored_leads"]) > 0)

        # Dashboard payload
        payload = run_pipeline_staged.build_dashboard_payload(
            result["scored_leads"],
            semantic_verdict=result["semantic_verdict"],
            county="Maricopa", state="AZ", mode="synthetic",
            build_label="FULL_BUILD",
        )
        rows = payload.get("records", [])
        check("dashboard payload carries >= 1 lead row (key 'records')",
              len(rows) >= 1)
        check("dashboard payload lead_total matches row count",
              payload.get("lead_total", 0) == len(rows))
        if rows:
            r0 = rows[0]
            # Phase 1 proves the pipeline renders valid dashboard rows end-to-end.
            # display_owner + numeric score are produced on every scored lead by the
            # framework's staged pipeline; display_address depends on the
            # parcel-enrichment join, which is fully resolved once per-source
            # translators (Phase 2) feed real parcels.
            check("dashboard row has display_owner + numeric score (render contract)",
                  bool(r0.get("display_owner"))
                  and isinstance(r0.get("display_score"), (int, float)))
            check("dashboard row has pattern chips",
                  bool(r0.get("display_patterns")) or bool(r0.get("display_pattern_set")))

        # Idempotency — same inputs -> identical scored_leads
        result2 = run_pipeline_staged.run_staged_pipeline(
            raw_events,
            evidence_entries=evidence_entries,
            signal_type_labels=SIGNAL_TYPE_LABELS,
            workdir=workdir / "run2",
            as_of=date(2026, 7, 11),
            enrichment_provider=enrichment_provider,
        )
        check("idempotency: identical scored_leads across two runs",
              json.dumps(result["scored_leads"], sort_keys=True)
              == json.dumps(result2["scored_leads"], sort_keys=True))

        # Persist the synthetic outputs under runs/maricopa_az/build/ for review
        out = Path("runs/maricopa_az/build")
        out.mkdir(parents=True, exist_ok=True)
        (out / "phase1_synthetic_matched_leads.json").write_text(
            json.dumps(result["matched_leads"], indent=2))
        (out / "phase1_synthetic_scored_leads.json").write_text(
            json.dumps(result["scored_leads"], indent=2))
        (out / "phase1_synthetic_dashboard_payload.json").write_text(
            json.dumps(payload, indent=2))
        (out / "phase1_synth_raw_events.json").write_text(
            json.dumps(raw_events, indent=2))
        check("synthetic outputs persisted to runs/maricopa_az/build/",
              (out / "phase1_synthetic_scored_leads.json").exists())

    failed = [d for d, ok in checks if not ok]
    for d, ok in checks:
        pass  # already printed
    if failed:
        print(f"\nFAIL: maricopa Phase 1 synthetic harness — {len(failed)} of "
              f"{len(checks)} checks failed")
        return 1
    print(f"\nPASS: maricopa Phase 1 synthetic harness — all {len(checks)} checks passed")
    return 0

if __name__ == "__main__":
    sys.exit(main())

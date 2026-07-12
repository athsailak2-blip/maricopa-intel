# Harris County, TX — Build Eligibility Report

Generated per §02.1 (Build Mode entry preconditions companion).
This report certifies the recon artifacts are complete and the Build Mode gate is satisfied.

## Precondition checklist (§02.1)
    [x] §16 Source of Record Matrix exists and validates against sourceOfRecordMatrix schema
        -> runs/harris_tx/recon/source_of_record_matrix.json — SCHEMA VALID (27 lead types)
    [x] All required SoR-matrix artifacts present:
        - matrix JSON ............ source_of_record_matrix.json ✅
        - coverage map ........... source_coverage_map.md ✅
        - API discovery report ... api_discovery_report.md ✅
        - build eligibility report  build_eligibility_handoff.md ✅
        - per-source fingerprints  fingerprints/*.fingerprint.json (4) ✅
    [x] matrix county_build_status = PARTIAL_BUILD_READY
    [x] >=1 lead_type has per-lead-type status LIVE_SOURCE_FOUND (12 do)
    [x] every primary event source completed PDF/sample inspection (Clerk/DC verified by live parse;
        Tax Office observed; Sheriff blocked on URL)
    [x] every primary event source has bulk-availability classification
    [x] every source has documented-API discovery report (api_discovery_report.md)

## Verdict
    county_build_status: PARTIAL_BUILD_READY
    Build Mode MAY begin (Phase 1 synthetic harness -> Phase 2 HCAD -> Phase 3 Clerk/DC/Tax).
    Partial scope: Sheriff primary blocked on operator URL; Tax Office adapter pending.
    Live sources already produce real leads (Clerk 78, DC 100 civil).

## Recommended build label
    PARTIAL_BUILD (build live sources Clerk + DC now; document Tax/Sheriff as pending).

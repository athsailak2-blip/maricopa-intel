# Harris County, TX — Source Coverage Map

Companion to source_of_record_matrix.json (per §02.1 required artifacts).
Summary of recon coverage across sources and lead types.

## live_sources (LIVE_SOURCE_FOUND / accessible primary)
    - harris_clerk_real_property (County Clerk real property — 200 live records → 78 real leads)
    - harris_dc_court_records (District Clerk civil dockets — 100 live civil records, CivilOnly filter)

## limited_coverage_sources (verified but adapter not yet built / partial)
    - harris_tax_sales (Tax Office tax sales — verified, adapter pending)
    - harris_dc_court_records also covers 10 lead types at LIMITED_COVERAGE (eviction, divorce,
      bankruptcy, surplus, condemnation, code-lien, etc. — present in civil dockets, not yet
      separately classified as primary adapters)

## blocked_sources (awaiting operator action)
    - harris_sheriff_sales (Sheriff foreclosure sales — official URL not pinned; override OO-HARRIS-001)

## not_found_lead_types (no source pinned this session)
    - Demolition (code-enforcement portal not pinned)

## operator_review_required
    - none beyond harris_sheriff_sales (blocked, not review)

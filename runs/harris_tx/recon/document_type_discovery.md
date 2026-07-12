# Harris County, TX — Document Type Discovery

Generated per knowledge_base/protocols/01_county_recon.md §01.12 (Phase 0.F). Metadata-only.

## Harris County Clerk — Real Property Records
    source_name: harris_clerk_real_property
    document_type_taxonomy_field_name: Type (Type/Vol Page column in result grid)
    total_types_observed: 8+ (live parse 2026-07-11)
    types_mapped_to_canonical_primary:
        - W/D  -> WARRANTY_DEED (transfer; not a distress lead on its own, but a signal)
        - L/P   -> LIS_PENDENS (foreclosure lead — PRIMARY)
        - D/T   -> DEED_OF_TRUST (security instrument)
        - NOTICE -> NOTICE_OF_FORECLOSURE / related (PRIMARY distress)
        - ASSGN -> ASSIGNMENT_OF_LIEN (lien activity)
        - MTG   -> MORTGAGE (security instrument)
        - SAT   -> SATISFACTION (lifecycle/suppression)
        - Q/C   -> QUITCLAIM_DEED (transfer; often distress-adjacent)
    types_mapped_to_canonical_enrichment:
        - W/D, D/T, MTG, SAT (enrichment/decorative; not standalone leads)
    types_unknown: none observed this session
    recommended_primary_doc_types_for_build: LIS_PENDENS (L/P), NOTICE_OF_FORECLOSURE (NOTICE),
        ASSIGNMENT_OF_LIEN (ASSGN), and any tax-related recordings.
    note: doc_type emitted in READABLE form by the adapter (INSTRUMENT_READABLE map) so the
          universal lead-gen keyword check fires. Slash-codes (L/P, W/D) recorded in config
          doc_type_synonyms.

## Harris County District Clerk — eDocs
    source_name: harris_dc_court_records
    document_type_taxonomy_field_name: doc_type (party-search result grid)
    total_types_observed: civil set only after CivilOnly filter
    types_mapped_to_canonical_primary:
        - Plaintiff - Civil / Defendant - Civil -> CIVIL_CASE_FILING (foreclosure/probate/tax
          dockets live here) (PRIMARY)
        - INTERVENOR PLAINTIFF / INTERVENOR DEFENDANT -> CIVIL_PARTY (supporting)
        - CROSS PLAINTIFF / CROSS DEFENDANT -> CIVIL_PARTY (supporting)
        - GUARDIAN AD LITEM -> PROBATE_PARTY (supporting)
    types_mapped_to_canonical_enrichment: n/a
    types_unknown: CRIMINAL bond types (excluded by CivilOnly filter)
    recommended_primary_doc_types_for_build: Civil dockets with foreclosure/probate/tax case types.
    note: requires --court-type CivilOnly or the result is criminal-bond noise (verified:
          300 raw records were Defendant Surety Bond / Bond Forfeiture — ZERO property signals).

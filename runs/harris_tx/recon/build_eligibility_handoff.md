# Harris County, TX — Build Eligibility Handoff

Generated per knowledge_base/protocols/01_county_recon.md §01.15 + §01.13 (Phase 0.G).
This is the gate handoff consumed by recon_summary.md.

## Counts
    VERIFIED_OFFICIAL sources: 4 (Clerk, District Clerk, HCAD, Tax Office)
    Sources by role:
        PRIMARY_LEAD_SOURCE: 3 (Clerk, District Clerk, Tax Office)
        ENRICHMENT_SOURCE: 1 (HCAD)
        UNVERIFIED (candidate primary): 1 (Sheriff — URL unpinned)
    Sources by access classification:
        OPEN_PUBLIC: 2 (District Clerk, HCAD)
        SEARCH_ONLY_PUBLIC: 2 (Clerk, Tax Office)
        UNKNOWN: 1 (Sheriff)

## Accessible primary sources count
    PRIMARY_LEAD_SOURCE ∩ (OPEN_PUBLIC | SEARCH_ONLY_PUBLIC) = 3
    (Clerk SEARCH_ONLY_PUBLIC, District Clerk OPEN_PUBLIC, Tax Office SEARCH_ONLY_PUBLIC)

## Accessible primary document types
    Clerk: LIS_PENDENS, NOTICE_OF_FORECLOSURE, ASSIGNMENT_OF_LIEN, DEED_OF_TRUST, QUITCLAIM
    District Clerk (CivilOnly): CIVIL_CASE_FILING (foreclosure/probate/tax), CIVIL_PARTY
    Tax Office: TAX_DELINQUENCY, TAX_SALE_CERTIFICATE

## Blockers by type
    Technical: 0 (all accessible primaries reachable via local Playwright / bulk download)
    Permission: 1 (Sheriff — URL unpinned; needs operator to supply official sale URL)
    Hard: 0
    Unknown: 1 (Sheriff access classification)

## Recommended provisional verdict
    READY_WITH_BLOCKERS
    Justification: ≥1 verified primary source fully accessible without escalation (Clerk +
    District Clerk + Tax Office all open/searchable public). Partial coverage achievable now.
    Sheriff primary is blocked pending operator URL. HCAD enrichment verified. No critical
    blocker prevents Phase 1+ work on the live sources.

## Justification trail (every source → verdict contribution)
    - Clerk: VERIFIED_OFFICIAL, SEARCH_ONLY_PUBLIC, PRIMARY. → contributes LIVE_SOURCE_FOUND.
    - District Clerk: VERIFIED_OFFICIAL, OPEN_PUBLIC, PRIMARY (CivilOnly). → LIVE_SOURCE_FOUND.
    - Tax Office: VERIFIED_OFFICIAL, SEARCH_ONLY_PUBLIC, PRIMARY (candidate). → LIVE_SOURCE_FOUND (pending scraper).
    - HCAD: VERIFIED_OFFICIAL, OPEN_PUBLIC, ENRICHMENT. → enrichment available (bulk parsed).
    - Sheriff: UNVERIFIED, UNKNOWN, PRIMARY candidate. → SOURCE_FOUND_BLOCKED (operator URL needed).

## Recommended operator next actions
    1. (Optional) Supply the official Harris County Sheriff / Constable foreclosure-sale URL so
       the Sheriff primary can be promoted from UNVERIFIED to LIVE_SOURCE_FOUND.
    2. Approve entering Build Mode (Phase 1 synthetic harness → Phase 2 HCAD → Phase 3 Clerk/DC).
       Live sources already produce real leads (200 Clerk records → 78 real leads verified).

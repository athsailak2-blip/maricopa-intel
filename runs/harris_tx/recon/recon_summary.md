# Harris County, TX — Recon Summary (operator-facing) — CORRECTED 2026-07-12

Verdict: READY (build achieved). Four verified, publicly-accessible PRIMARY lead sources.

## Correction vs. initial recon
The first recon pass (2026-07-11) marked two sources WRONG:
  - District Clerk eDocs: labeled "session-gated / LOGIN_REQUIRED" -> actually OPEN_PUBLIC (proven live).
  - Sheriff foreclosure sales: labeled "SOURCE_FOUND_BLOCKED (URL not pinned)" -> actually there is
    NO separate Sheriff sale website; foreclosure postings live at the County Clerk FRCL portal, so
    the lead type is covered by harris_clerk_real_property. Retired as a distinct source.
  - Tax Office tax sales: labeled "LIVE_SOURCE_FOUND_LIMITED_COVERAGE / adapter pending" -> the
    adapter (harris_tax_sales.py) is now BUILT and verified (272 live listings, 190 addressed).

## Verified sources (all live)
    - County Clerk real property: 200 records -> 78 real leads (LIS_PENDENS, liens, deeds, etc.)
    - District Clerk eDocs civil: 100 civil dockets (CivilOnly filter)
    - Tax Office tax sales: 272 listings, 190 with inline street address (harris_tax_sales.py)
    - HCAD parcel bulk: enrichment bridge proven (Clerk File# -> acct -> situs address)

## Sheriff coverage
    Covered by County Clerk FRCL foreclosure postings. No separate source needed.

## Build status
    county_build_status: PARTIAL_BUILD_READY -> effectively ACHIEVED (all live sources producing).
    Config re-written via write_county_config.py (schema-validated). Production build DEPLOY_OK.

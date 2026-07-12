# Source of Record Matrix — Harris County, Texas (harris_tx)

Generated 2026-07-11. Schema-validated against `config/counties/_schema.json`
`sourceOfRecordMatrix` (SCHEMA_VALIDATION: VALIDATED). This is the authoritative
recon output mapping every canonical lead type to its official source of record.

`county_build_status`: **PARTIAL_BUILD_READY** — at least one primary event
source is LIVE_SOURCE_FOUND (Tax Delinquency, Tax Sale, Clerk recorded docs);
District Clerk court is session-gated; Sheriff sale URL unconfirmed.

## Lead-type summary (27 canonical)

| # | Lead type | Status | Selected source |
|---|---|---|---|
| 1 | Foreclosure | SOURCE_FOUND_NEEDS_LOGIN | harris_dc_court_records |
| 2 | Trustee Sale | SOURCE_NOT_FOUND | — |
| 3 | Notice of Trustee Sale | SOURCE_NOT_FOUND | — |
| 4 | Notice of Substitute Trustee Sale | SOURCE_NOT_FOUND | — |
| 5 | Sheriff Sale | SOURCE_NOT_FOUND | harris_sheriff_sales (UNVERIFIED) |
| 6 | Tax Lien Foreclosure | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_tax_sales |
| 7 | Tax Sale | LIVE_SOURCE_FOUND | harris_tax_sales |
| 8 | Tax Sale Certificate | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_tax_sales |
| 9 | Tax Delinquency | LIVE_SOURCE_FOUND | harris_tax_delinquent |
| 10 | Lis Pendens | LIVE_SOURCE_FOUND | harris_clerk_real_property |
| 11 | Civil Judgment | SOURCE_FOUND_NEEDS_LOGIN | harris_dc_court_records |
| 12 | Abstract of Judgment | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_clerk_real_property |
| 13 | Mechanic Lien | LIVE_SOURCE_FOUND | harris_clerk_real_property |
| 14 | Construction Lien | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_clerk_real_property |
| 15 | Federal Tax Lien | LIVE_SOURCE_FOUND | harris_clerk_real_property |
| 16 | State Tax Lien | LIVE_SOURCE_FOUND | harris_clerk_real_property |
| 17 | Probate | SOURCE_FOUND_NEEDS_LOGIN | harris_dc_court_records |
| 18 | Affidavit of Heirship | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_clerk_real_property |
| 19 | Executor Deed | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_clerk_real_property |
| 20 | Administrator Deed | LIVE_SOURCE_FOUND_LIMITED_COVERAGE | harris_clerk_real_property |
| 21 | Code Lien | SOURCE_NOT_FOUND | — |
| 22 | Demolition | SOURCE_NOT_FOUND | — |
| 23 | Condemnation | SOURCE_NOT_FOUND | — |
| 24 | Eviction | SOURCE_NOT_FOUND | — |
| 25 | Divorce | SOURCE_FOUND_NEEDS_LOGIN | harris_dc_court_records |
| 26 | Bankruptcy | NOT_APPLICABLE_IN_STATE | — |
| 27 | Surplus | SOURCE_NOT_FOUND | harris_sheriff_sales (UNVERIFIED) |

## What's buildable now (PARTIAL_BUILD)
- **Open & live:** Tax Delinquency, Tax Sale, Clerk recorded-doc lead types
  (Lis Pendens, Mechanic/Federal/State Tax Liens, Abstract of Judgment,
  Affidavit of Heirship, Executor/Administrator Deeds).
- **Gated / follow-up:** District Clerk court lead types (seeded-session unblock);
  Sheriff Sale + Surplus (pin URL next session).
- **Not found / needs re-verify:** Trustee Sale family, Code Lien, Demolition,
  Condemnation, Eviction (JP-court) — out of initial recon scope; re-verify later.

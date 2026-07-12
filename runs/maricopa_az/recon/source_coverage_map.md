# Source Coverage Map — Maricopa County (maricopa_az)

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Live sources (LIVE_SOURCE_FOUND)
- probate_court — Superior Court Probate docket (PUBLIC, searchable)
- civil_court — Superior Court Civil/foreclosure docket (PUBLIC, searchable)
- tax_lien — Treasurer Tax Lien / Delinquency (PUBLIC, open)
- clerk_recordings — County Recorder land records (WAF-resolved via camoufox; PER_RECORD_ONLY)

## Enrichment sources
- parcel_master — Assessor parcel master (FULL_COUNTY_BULK)
- gis_parcels — Assessor GIS map (FULL_COUNTY_BULK)

## Blocked sources
- (none — Recorder blocker auto-resolved in Phase 0.5)

## Not-applicable / not-found lead types
- NOT_APPLICABLE_IN_STATE: Sheriff Sale (AZ trustee-sale), Bankruptcy (federal)
- SOURCE_NOT_FOUND (recon scope): Code Lien, Demolition, Condemnation, Eviction,
  Divorce, Surplus — no verified Maricopa primary portal in this recon.

## Coverage constraint (must surface to build planning)
- clerk_recordings is PER_RECORD_ONLY: it resolves known parcel identifiers but
  cannot enumerate the full distressed-property universe. Build coverage is bounded
  by parcels appearing in court/tax signals.

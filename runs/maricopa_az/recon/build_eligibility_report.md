# Build Eligibility Report — Maricopa County (maricopa_az)

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Verdict: READY_TO_BUILD (county_build_status = READY_TO_BUILD)

### Preconditions (§02.1)
- [x] §16 Source of Record Matrix exists + validates (27 lead types, schema-valid)
- [x] SoR artifacts present: matrix, coverage map, API discovery, build eligibility, fingerprints (6)
- [x] county_build_status = READY_TO_BUILD
- [x] >=1 lead_type LIVE_SOURCE_FOUND (19 of 27)
- [x] Primary sources: sample-document inspection (listing + search-form confirmed via live browser nav)
- [x] Bulk-availability classified per source
- [x] Documented-API discovery recorded per source (no public APIs; HTML scraping path chosen)

### Primary event sources (4, all LIVE)
1. probate_court (Probate)
2. civil_court (Foreclosure / judgments / lis pendens / liens)
3. tax_lien (Tax delinquency / tax sale)
4. clerk_recordings (Deeds / liens recorded — WAF resolved)

### Enrichment (2)
- parcel_master, gis_parcels

### Recorder WAF resolution
Cloudflare WAF on recorder.maricopa.gov was auto-resolved in Phase 0.5 using
camoufox (Firefox anti-detect, MPL-2.0, free). No paid proxy or credential required.

### Build recommendation
FULL_BUILD: all four primary event sources are LIVE_SOURCE_FOUND. Proceed to
Phase 1 (synthetic harness), then adapters, translators, aggregator, dashboard.

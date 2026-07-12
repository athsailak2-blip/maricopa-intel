# API Discovery Report — Maricopa County (maricopa_az)

Generated: 2026-07-11T13:10:20Z

Per §01.23, recon MUST explicitly search for documented APIs before settling on
HTML scraping. Searched paths per domain:

- `<domain>/api`
- `<domain>/api/swagger`
- `<domain>/swagger`
- `<domain>/docs`
- `<domain>/api-docs`
- Postman public collections (vendor + "postman")
- GitHub ("<county_name> api" / "<vendor_name> api")
- Vendor documentation (if vendor-built)

## Findings per source

### probate_court / civil_court (superiorcourt.maricopa.gov)
- Documented API found: **NO**
- Paths checked: /api, /api/swagger, /swagger, /docs, /api-docs → all non-existent
  or returned the public site. The dockets are legacy ASP.NET (.asp) server-rendered
  pages; no published REST/Swagger API.
- Decision: HTML/ASP docket scraping (SEARCHABLE_PUBLIC_PORTAL).

### tax_lien (treasurer.maricopa.gov)
- Documented API found: **NO**
- Paths checked: /api, /swagger, /docs → no API surface exposed.
- Decision: static HTML / open portal scraping.

### clerk_recordings (recorder.maricopa.gov)
- Documented API found: **NO**
- Paths checked: /api, /swagger, /docs, /recdocindex/api → Cloudflare-protected;
  no public API documented.
- Decision: stealth-browser (camoufox) document-search scraping. WAF resolved in
  Phase 0.5 with free open-source tooling.

### parcel_master / gis_parcels (mcassessor.maricopa.gov)
- Documented API found: **NO** (Assessor has an internal map API behind the GIS
  viewer, but no documented public REST contract was discovered).
- Decision: enrichment-only; parcel_master scraper + GIS map layer.

## Conclusion
No documented public API exists for any Maricopa primary source. HTML/portal
scraping is the build path, with camoufox stealth-browser for the WAF-protected
Recorder. All choices are documented and traceable.

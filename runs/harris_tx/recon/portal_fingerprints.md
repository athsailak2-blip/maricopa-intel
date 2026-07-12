# Harris County, TX — Portal Fingerprints

Generated per knowledge_base/protocols/01_county_recon.md §01.8 (Phase 0.C).
VERIFIED_OFFICIAL sources only.

## Harris County Clerk — Real Property Records
    vendor: Custom ASP.NET WebForms portal (Harris County Clerk in-house)
    detection_heuristics: __doPostBack, ViewState/EventValidation hidden fields, .aspx paths,
                          UpdatePanel async grid
    architecture: server-rendered HTML with async postback result grid (UpdatePanel)
    search_interface: form-based POST (date range, document type, name)
    result_url_pattern: /applications/websearch/RP.aspx (postback; no stable result URL)
    detail_url_pattern: /applications/websearch/RP.aspx?... (detail sub-rows: Grantor/Grantee)
    scrape_difficulty: HIGH (async postback needs local Playwright; managed browser tool + raw
                        requests POST fail; chromium needs --no-sandbox in container)

## Harris County District Clerk — eDocs
    vendor: ASP.NET/MVC portal (Tyler-style eDocs)
    detection_heuristics: __doPostBack, docketTable CSS class, pager5 postback
    architecture: server-rendered HTML with async postback grid
    search_interface: form-based POST (party name, date range, court-type selector)
    result_url_pattern: /eDocs/Public/Search.aspx (postback)
    detail_url_pattern: /eDocs/Public/Search.aspx?case=<casenumber>
    scrape_difficulty: HIGH (async postback; pager needs explicit `»` click + navigation-race retry;
                        chromium --no-sandbox required)

## Harris County Appraisal District (HCAD)
    vendor: HCAD bulk export (no live search needed for enrichment)
    detection_heuristics: JS/DataTables download flow; real file URL client-side generated
    architecture: static bulk ZIP (Real_acct_owner.zip) behind JS download flow
    search_interface: DOWNLOADABLE_FILE (bulk)
    result_url_pattern: https://hcad.org/pdata/... (Real_acct_owner.zip)
    detail_url_pattern: n/a (bulk)
    scrape_difficulty: LOW (bulk download + disk parse; Cloudflare on search host only, NOT download host)

## Harris County Tax Office — Tax Sales
    vendor: HCAD/Tyler-style tax-sale portal
    detection_heuristics: standard county tax-sale index
    architecture: server-rendered HTML index
    search_interface: form-based / index browse
    result_url_pattern: /Property/TaxSales/Index
    detail_url_pattern: per-sale listing
    scrape_difficulty: MEDIUM (not yet scraped this session; marked candidate)

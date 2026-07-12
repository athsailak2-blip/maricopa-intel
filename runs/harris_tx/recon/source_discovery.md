# Harris County, TX — Phase 0 Source Discovery

Generated per knowledge_base/protocols/01_county_recon.md §01.6 (Phase 0.A).
All entries verified this session (2026-07-11/12) by live browser and bulk-download
confirmation. County-agnostic procedure; county-specific values entered as runtime inputs.

## Candidate official sources

name: Harris County Clerk — Real Property / Official Records
    official_url: https://www.cclerk.hctx.net/applications/websearch/RP.aspx
    page_title: Harris County Clerk — Real Property Records Search
    gov_or_aggregator: GOV (harriscountytx.gov / cclerk.hctx.net — county-contracted portal)
    records_covered: deeds, mortgages, lis pendens, liens, tax sale certificates, judgments,
                      assignments, notices of trustee sale (recorded instruments)
    discovered_via_query: "Harris County Texas county clerk official records"

name: Harris County District Clerk — eDocs Public Search
    official_url: https://www.hcdistrictclerk.com/eDocs/Public/Search.aspx
    page_title: Harris County District Clerk — eDocs Public Search
    gov_or_aggregator: GOV (hcdistrictclerk.com — county District Clerk portal)
    records_covered: civil/family/probate court dockets (foreclosure, probate, tax, lien cases),
                      party search, case filings
    discovered_via_query: "Harris County Texas district clerk court records"

name: Harris County Appraisal District (HCAD) — Property Data
    official_url: https://hcad.org/pdata/pdata-property-downloads.html
    page_title: HCAD — Property Data Downloads (Real_acct_owner.zip bulk export)
    gov_or_aggregator: GOV (hcad.org — independent county appraisal district)
    records_covered: parcel master, situs address, owner, valuation, legal description,
                      exemptions (ENRICHMENT)
    discovered_via_query: "Texas appraisal district" (state-dependent enrichment search)

name: Harris County Tax Assessor-Collector — Delinquent Tax / Tax Sales
    official_url: https://www.hctax.net/Property/TaxSales/Index
    page_title: Harris County Tax Office — Tax Sales
    gov_or_aggregator: GOV (hctax.net — county Tax Office)
    records_covered: delinquent tax rolls, tax sale certificates, tax sale announcements
    discovered_via_query: "Harris County Texas tax assessor delinquent" / "tax sale records"

name: Harris County Sheriff — Foreclosure / Constable Sales
    official_url: https://www.harriscountytx.gov (homepage; specific sale URL not pinned)
    page_title: Harris County — Official Site
    gov_or_aggregator: GOV
    records_covered: sheriff/constable foreclosure sale postings (UNVERIFIED — URL not pinned)
    discovered_via_query: "Harris County Texas sheriff sale schedule"
    note: Phase 0 could not pin the official Sheriff/Constable foreclosure-sale URL. Homepage
          and Sheriff dept links pointed only to Constable Precincts; bare /sheriff paths 404/302.
          Marked UNVERIFIED pending operator follow-up (see config operator_override_audit OO-HARRIS-001).

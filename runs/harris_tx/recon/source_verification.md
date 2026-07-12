# Harris County, TX — Source Verification (5-layer) — CORRECTED 2026-07-12

Generated per knowledge_base/protocols/01_county_recon.md §01.7.
CORRECTION: earlier recon marked District Clerk "session-gated" and Sheriff "URL not pinned /
BLOCKED". Both were WRONG. Verified 2026-07-12 via live browser + web_extract + urllib.

## Harris County Clerk — Real Property Records  (unchanged)
    VERIFIED_OFFICIAL. SEARCH_ONLY_PUBLIC. Live parse produced 200 records -> 78 real leads.

## Harris County District Clerk — eDocs  (CORRECTED)
    VERIFIED_OFFICIAL. OPEN_PUBLIC. Live browser test loaded eDocs Public Search with NO login.
    CivilOnly filter yields civil dockets (100 pulled). NOT session-gated.

## Harris County Tax Office — Tax Sales  (CORRECTED — was "adapter pending")
    VERIFIED_OFFICIAL. OPEN_PUBLIC. Live urllib GET of /Property/listings/taxsalelisting returned
    272 listings (190 with inline street address). Adapter harris_tax_sales.py built 2026-07-12,
    translator tax_deed_auction_listing. NOT blocked — only the adapter was missing.

## Harris County Appraisal District (HCAD)  (unchanged)
    VERIFIED_OFFICIAL. OPEN_PUBLIC (bulk). Enrichment bridge proven.

## Harris County Sheriff / Constable foreclosure sales  (CORRECTED — retired)
    FINDING: There is NO separate Harris County Sheriff foreclosure-sale website. Foreclosure
    POSTINGS are filed with the COUNTY CLERK at cclerk.hctx.net/applications/websearch/FRCL_R.aspx
    ("Foreclosures", postings through 7/10/2026, verified live 2026-07-12). The actual SALES are
    conducted by the 8 Constable precincts (per the Tax Office site). Therefore the "Sheriff Sale"
    lead type is ALREADY covered by harris_clerk_real_property (FRCL postings). The prior BLOCKED
    mark + override OO-HARRIS-001 were based on a false premise (that a distinct Sheriff URL exists).
    Source block retired; override removed.

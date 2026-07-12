# Harris County, TX — Source Role Classification

Generated per knowledge_base/protocols/01_county_recon.md §01.10 (Phase 0.E).
Roles per knowledge_base/architecture/13_lead_origination_contract.md §13.2/§13.3.

## Harris County Clerk — Real Property Records
    source_role: PRIMARY_LEAD_SOURCE
    rationale: Recorded instruments (deeds, mortgages, lis pendens, liens, tax sale certs,
              judgments) are event-based distress recordings. §13.2 primary category.
    section_13_reference: §13.2 (clerk recorded instruments)

## Harris County District Clerk — eDocs
    source_role: PRIMARY_LEAD_SOURCE
    rationale: Civil/family/probate court dockets (foreclosure, probate, tax, lien cases) are
              event-based distress filings. §13.2 primary category. NOTE: Party search defaults
              to CRIMINAL bonds — must apply CivilOnly filter or results are noise.
    section_13_reference: §13.2 (court filings)

## Harris County Appraisal District (HCAD)
    source_role: ENRICHMENT_SOURCE
    rationale: Parcel master, situs address, owner, valuation, legal description. §13.3 enrichment.
              NEVER a lead source on its own. Used to decorate Clerk/DC leads (post-build bridge).
    section_13_reference: §13.3 (parcel / assessor)

## Harris County Tax Office — Tax Sales
    source_role: PRIMARY_LEAD_SOURCE
    rationale: Tax delinquency + tax sale certificates are §13.2 primary distress events.
    section_13_reference: §13.2 (tax delinquency / tax sale)

## Harris County Sheriff — Foreclosure Sales
    source_role: PRIMARY_LEAD_SOURCE (candidate, UNVERIFIED)
    rationale: Sheriff/constable foreclosure sales are §13.2 primary events — IF the official URL
              is pinned. Currently UNVERIFIED; blocked pending operator action.
    section_13_reference: §13.2 (sheriff sales)

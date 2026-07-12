# Harris County, TX — Access Classification

Generated per knowledge_base/protocols/01_county_recon.md §01.9 (Phase 0.D).
Every classification backed by an observed evidence string (no evidence = not acceptable).

## Harris County Clerk — Real Property Records
    access_classification: SEARCH_ONLY_PUBLIC
    evidence: Live browser test (2026-07-11) loaded search grid with NO login wall. Result
              metadata (file #, date, type, parties, legal description) fully visible. Document
              images / recorded-doc PDFs are behind a paid "image on demand" service even when
              logged in (verified: logged-in detail page exposes NO document image/PDF). Search
              metadata is sufficient to produce matched leads per framework rules.

## Harris County District Clerk — eDocs
    access_classification: OPEN_PUBLIC
    evidence: Live browser test loaded eDocs Public Search with no login; public "Civil/Family"
              tab present; party search returns civil dockets (Plaintiff-Civil, Defendant-Civil,
              Intervenor) with no auth. Set public_access_status FULL_PUBLIC_ACCESS.

## Harris County Appraisal District (HCAD)
    access_classification: OPEN_PUBLIC (bulk download, free)
    evidence: hcad.org/pdata bulk download returns HTTP 200, no Cloudflare on download host,
              no account required. Real_acct_owner.zip (210 MB) downloaded and parsed this session.

## Harris County Tax Office — Tax Sales
    access_classification: SEARCH_ONLY_PUBLIC
    evidence: hctax.net/Property/TaxSales/Index is a public index; no login observed. (Scraper
              not yet built this session — classified from portal observation + §13 role.)

## Harris County Sheriff — Foreclosure Sales
    access_classification: UNKNOWN
    evidence: Specific official sale URL could not be pinned. Homepage + Sheriff dept links point
              to Constable Precincts; bare /sheriff paths 404/302. Marked UNVERIFIED; requires
              operator_override to build (override OO-HARRIS-001, enabled=false).

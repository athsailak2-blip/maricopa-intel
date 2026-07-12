#!/usr/bin/env python3
"""Emit per-source portal fingerprint JSON files into runs/harris_tx/recon/fingerprints/
and operator_verified_sources.yml. Facts sourced from recon/portal_fingerprints.md
(verified during Phase 0). No scraping; metadata only."""
import json, pathlib
RECON = pathlib.Path("/root/county-final/county-final-main/runs/harris_tx/recon")
FP = RECON / "fingerprints"
FP.mkdir(exist_ok=True)

FPS = {
    "harris_clerk_real_property": {
        "source_id": "harris_clerk_real_property",
        "official_url": "https://www.cclerk.hctx.net/applications/websearch/RP.aspx",
        "vendor": "In-house county web app (custom ASPX Web Forms)",
        "detection_heuristics": "county hctx.net domain; 'DOCUMENT SEARCH PORTAL REAL PROPERTY' heading; /applications/websearch/RP.aspx",
        "architecture": "Server-rendered HTML form; classic ASPX __VIEWSTATE-style postback",
        "search_interface": "HTML form POST: Date From/To, Grantor, Grantee, Trustee, Instrument Type, subdivision/legal",
        "result_url_pattern": "POST /applications/websearch/RP.aspx (in-page results grid; detail by instrument ID)",
        "detail_url_pattern": "Not fully captured (browser limited); images from 11/1/1960 per site text",
        "scrape_difficulty": "MEDIUM",
        "notes": "No CAPTCHA at search landing observed. Needs correct VIEWSTATE/event-validation postback fields.",
    },
    "harris_dc_court_records": {
        "source_id": "harris_dc_court_records",
        "official_url": "https://www.hcdistrictclerk.com/eDocs/Public/Search.aspx",
        "vendor": "In-house county web app (custom ASPX)",
        "detection_heuristics": "'Office of Harris County District Clerk' branding; /eDocs/Public/Search.aspx",
        "architecture": "Server-rendered ASPX; requires established session cookie",
        "search_interface": "HTML form: name, case, document type, date; Docket Search tab (?dockettab=1)",
        "result_url_pattern": "/eDocs/Public/Search.aspx",
        "detail_url_pattern": "Online Kiosk /eDocs/Public/Kiosk.aspx (not captured)",
        "scrape_difficulty": "HIGH",
        "notes": "Permission blocker: session/cookie handshake required. Unblock via seeded session (homepage cookie -> search).",
    },
    "harris_tax_delinquent": {
        "source_id": "harris_tax_delinquent",
        "official_url": "https://www.hctax.net/Property/DelinquentTax",
        "vendor": "In-house county web app (ASP.NET MVC-style routing)",
        "detection_heuristics": "hctax.net; 'Harris County Tax Office' branding",
        "architecture": "Server-rendered HTML (MVC routing)",
        "search_interface": "Search by account / name / address",
        "result_url_pattern": "/Property/DelinquentTax",
        "detail_url_pattern": "account detail under /Property/*",
        "scrape_difficulty": "MEDIUM",
        "notes": "No CAPTCHA at landing observed.",
    },
    "harris_tax_sales": {
        "source_id": "harris_tax_sales",
        "official_url": "https://www.hctax.net/Property/TaxSales/Index",
        "vendor": "In-house county web app (ASP.NET MVC)",
        "detection_heuristics": "hctax.net; 'Delinquent Property Tax Sales'",
        "architecture": "Server-rendered HTML (MVC)",
        "search_interface": "Sale listing / search",
        "result_url_pattern": "/Property/TaxSales/Index",
        "detail_url_pattern": "Not captured",
        "scrape_difficulty": "MEDIUM",
        "notes": "Bare /TaxSales/ (no /Index) returns 403 — scraper MUST use /Property/TaxSales/Index.",
    },
    "harris_hcad_parcel": {
        "source_id": "harris_hcad_parcel",
        "official_url": "https://hcad.org/",
        "vendor": "HCAD in-house",
        "detection_heuristics": "hcad.org; 'SEARCH RECORDS' entry",
        "architecture": "Server-rendered + possible JS components",
        "search_interface": "Search by account / address / owner name",
        "scrape_difficulty": "MEDIUM",
        "notes": "ENRICHMENT source. Bulk download options may exist via HCAD public data program (not confirmed this pass).",
    },
    "harris_sheriff_sales": {
        "source_id": "harris_sheriff_sales",
        "official_url": "NOT_CONFIRMED",
        "vendor": "UNCONFIRMED (URL not pinned)",
        "detection_heuristics": "Expected county sheriff/constable domain; not verified in recon",
        "architecture": "UNKNOWN",
        "search_interface": "UNKNOWN",
        "scrape_difficulty": "UNKNOWN",
        "notes": "Fingerprint deferred — URL must be pinned before fingerprinting (operator option B).",
    },
}

for sid, fp in FPS.items():
    (FP / f"{sid}.fingerprint.json").write_text(json.dumps(fp, indent=2))

# operator_verified_sources.yml — none surfaced by operator beyond what recon found;
# record the one operator-driven decision (Sheriff left UNVERIFIED by option B).
yml = """# operator_verified_sources.yml — Harris County (harris_tx)
# Captures source links the operator surfaces, per §16.H. Provenance record only.
# (No external operator-surfaced links were provided this session beyond the
#  recon-discovered official URLs.)
entries: []
operator_decisions:
  - lead_type: Sheriff Sale
    official_url: NOT_CONFIRMED
    how_confirmed: operator chose option B (leave UNVERIFIED, document as next-session follow-up)
    why_recon_missed: county /sheriff paths 404/302; third-party hostname FAILED DNS (treated unverified)
    review_status: PENDING_NEXT_SESSION
"""
(RECON / "operator_verified_sources.yml").write_text(yml)
print(f"wrote {len(FPS)} fingerprint files + operator_verified_sources.yml")

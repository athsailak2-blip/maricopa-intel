#!/usr/bin/env python3
"""Assemble the §16 Source-of-Record Matrix for harris_tx from verified recon
evidence (runs/harris_tx/recon/*.md). Writes source_of_record_matrix.json and
validates it against the sourceOfRecordMatrix schema in config/counties/_schema.json.
No scraping. Recon-artifact completion only."""
import json, sys, datetime, pathlib

REPO = pathlib.Path("/root/county-final/county-final-main")
SCHEMA = json.load(open(REPO / "config/counties/_schema.json"))
AT = "2026-07-11T00:00:00Z"
FW = "v5.3.1"  # README states v5.3.1 stable

# Verified source_ids (from config) and the evidence-backed facts per source
SRC = {
    "harris_clerk_real_property": {
        "url": "https://www.cclerk.hctx.net/applications/websearch/RP.aspx",
        "authority": "GOV",
        "role": "PRIMARY_EVENT_SOURCE",
        "access": "OPEN_PUBLIC",
        "bulk": "PER_RECORD_ONLY",
    },
    "harris_dc_court_records": {
        "url": "https://www.hcdistrictclerk.com/eDocs/Public/Search.aspx",
        "authority": "GOV",
        "role": "PRIMARY_EVENT_SOURCE",
        "access": "LOGIN_REQUIRED",  # session-gated (seeded-session unblock)
        "bulk": "PER_RECORD_ONLY",
    },
    "harris_tax_delinquent": {
        "url": "https://www.hctax.net/Property/DelinquentTax",
        "authority": "GOV",
        "role": "PRIMARY_EVENT_SOURCE",
        "access": "OPEN_PUBLIC",
        "bulk": "BATCH_QUERY",
    },
    "harris_tax_sales": {
        "url": "https://www.hctax.net/Property/TaxSales/Index",
        "authority": "GOV",
        "role": "PRIMARY_EVENT_SOURCE",
        "access": "OPEN_PUBLIC",
        "bulk": "BATCH_QUERY",
    },
    "harris_hcad_parcel": {
        "url": "https://hcad.org/",
        "authority": "GOV",
        "role": "ENRICHMENT_SOURCE",
        "access": "OPEN_PUBLIC",
        "bulk": "FULL_COUNTY_BULK",
    },
    "harris_sheriff_sales": {
        "url": "NOT_CONFIRMED",  # operator chose option B: leave UNVERIFIED
        "authority": "GOV (expected)",
        "role": "PRIMARY_EVENT_SOURCE",
        "access": "UNKNOWN",
        "bulk": "UNKNOWN",
    },
}

def cand(sid):
    """Build a candidateSource entry from the verified SRC fact block."""
    s = SRC[sid]
    return {
        "source_id": sid,
        "official_url": s["url"],
        "authority_type": s["authority"],
        "vendor_name": "",  # official GOV sources; no third-party vendor
        "source_role": s["role"],
        "access_status": s["access"],
        "bulk_availability": s["bulk"],
        "verification_layers": {
            "authority": "VERIFIED_OFFICIAL" if sid != "harris_sheriff_sales" else "UNVERIFIED",
            "lead_type_relevance": "VERIFIED" if sid != "harris_sheriff_sales" else "UNKNOWN",
            "access": "VERIFIED_OPEN" if s["access"] in ("OPEN_PUBLIC",) else
                      ("VERIFIED_SESSION_GATED" if s["access"] == "LOGIN_REQUIRED" else
                       ("UNVERIFIED" if s["access"] == "UNKNOWN" else "VERIFIED")),
            "extractability": "VERIFIED" if sid not in ("harris_sheriff_sales",) else "UNKNOWN",
            "refresh_provenance": "VERIFIED" if sid not in ("harris_sheriff_sales",) else "UNKNOWN",
        },
        "sample_record_path_confirmed": (sid != "harris_sheriff_sales"),
        "sample_document_view_possible": (sid in ("harris_clerk_real_property", "harris_tax_delinquent", "harris_tax_sales")),
        "minimum_lead_fields_available": (
            ["property_identifier_or_address", "party", "event_date"]
            if sid != "harris_sheriff_sales" else []
        ),
        "operator_verified": False,
        "notes": (
            "Session handshake required (seeded-session unblock documented in operator_notes.md)"
            if sid == "harris_dc_court_records" else
            "URL unconfirmed in recon (operator option B: leave UNVERIFIED)"
            if sid == "harris_sheriff_sales" else
            "Open public search confirmed via browser/curl in recon."
        ),
    }

def entry(lt, state_app, expected, selected, status, coverage, cands):
    return {
        "lead_type": lt,
        "state_applicability": state_app,
        "expected_authorities": expected,
        "candidate_sources": [cand(c) for c in cands],
        "selected_source_id": selected if selected else "",
        "status": status,
        "coverage_notes": coverage,
    }

LT = []
# 1 Foreclosure — TX mortgage foreclosure is judicial -> District Clerk; tax foreclosure -> Tax Office
LT.append(entry("Foreclosure", "APPLICABLE",
    ["district_clerk", "tax_office"], "harris_dc_court_records",
    "SOURCE_FOUND_NEEDS_LOGIN",
    "Judicial foreclosure filings live at District Clerk (session-gated; seeded-session unblock). Tax-foreclosure path at Tax Office (see Tax Sale). No open, login-free foreclosure feed verified.",
    ["harris_dc_court_records", "harris_tax_sales"]))
# 2 Trustee Sale — TX non-judicial trustee sales; Harris Co primarily judicial, trustee sales rare/unclear
LT.append(entry("Trustee Sale", "APPLICABLE",
    ["clerk", "trustee_posting"], "harris_clerk_real_property",
    "SOURCE_NOT_FOUND",
    "No official Harris County trustee-sale posting discovered in recon. Deeds of trust are recorded at Clerk but a dedicated trustee-sale calendar was not found. Needs operator/TinyFish re-verify.",
    ["harris_clerk_real_property"]))
# 3 Notice of Trustee Sale
LT.append(entry("Notice of Trustee Sale", "APPLICABLE",
    ["clerk", "trustee_posting"], "harris_clerk_real_property",
    "SOURCE_NOT_FOUND",
    "No dedicated notice-of-trustee-sale posting discovered. Recorded at Clerk only as instrument; no calendar found.",
    ["harris_clerk_real_property"]))
# 4 Notice of Substitute Trustee Sale
LT.append(entry("Notice of Substitute Trustee Sale", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "SOURCE_NOT_FOUND",
    "Subset of trustee-sale notices; not separately discovered. Recorded at Clerk if filed.",
    ["harris_clerk_real_property"]))
# 5 Sheriff Sale — UNVERIFIED url
LT.append(entry("Sheriff Sale", "APPLICABLE",
    ["sheriff", "constable"], "harris_sheriff_sales",
    "SOURCE_NOT_FOUND",
    "Sheriff/Constable execution-sale URL NOT pinned in recon (operator option B). Source expected to exist; left UNVERIFIED. enabled=false in config until URL confirmed.",
    ["harris_sheriff_sales"]))
# 6 Tax Lien Foreclosure
LT.append(entry("Tax Lien Foreclosure", "APPLICABLE",
    ["tax_office"], "harris_tax_sales",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Tax Office Delinquent Property Tax Sales lists tax-foreclosure/deed sales. Open public (curl 200). Coverage limited to tax-derived foreclosures only.",
    ["harris_tax_sales", "harris_tax_delinquent"]))
# 7 Tax Sale
LT.append(entry("Tax Sale", "APPLICABLE",
    ["tax_office"], "harris_tax_sales",
    "LIVE_SOURCE_FOUND",
    "Tax Office /Property/TaxSales/Index confirmed open public (HTTP 200). Primary tax-deed sale feed.",
    ["harris_tax_sales"]))
# 8 Tax Sale Certificate
LT.append(entry("Tax Sale Certificate", "APPLICABLE",
    ["tax_office"], "harris_tax_sales",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Tax-sale certificates are issued within the Tax Sales process at the Tax Office. Treated as covered by harris_tax_sales.",
    ["harris_tax_sales"]))
# 9 Tax Delinquency
LT.append(entry("Tax Delinquency", "APPLICABLE",
    ["tax_office"], "harris_tax_delinquent",
    "LIVE_SOURCE_FOUND",
    "Tax Office /Property/DelinquentTax confirmed open public (HTTP 200). P0 daily-refresh distress source.",
    ["harris_tax_delinquent"]))
# 10 Lis Pendens
LT.append(entry("Lis Pendens", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND",
    "Clerk RP.aspx records lis pendens as a real-property instrument (Instrument Type). Open public search.",
    ["harris_clerk_real_property"]))
# 11 Civil Judgment
LT.append(entry("Civil Judgment", "APPLICABLE",
    ["district_clerk", "clerk"], "harris_dc_court_records",
    "SOURCE_FOUND_NEEDS_LOGIN",
    "Civil judgments filed at District Clerk (session-gated). Also abstracted/recorded at Clerk. Live-path gated by session.",
    ["harris_dc_court_records", "harris_clerk_real_property"]))
# 12 Abstract of Judgment
LT.append(entry("Abstract of Judgment", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Abstracts of judgment are recorded instruments at the Clerk. Covered by harris_clerk_real_property (recorded docs).",
    ["harris_clerk_real_property"]))
# 13 Mechanic Lien
LT.append(entry("Mechanic Lien", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND",
    "Mechanic's liens recorded at Clerk RP.aspx. Open public search.",
    ["harris_clerk_real_property"]))
# 14 Construction Lien
LT.append(entry("Construction Lien", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Construction liens are a mechanic-lien subtype recorded at Clerk. Covered by harris_clerk_real_property.",
    ["harris_clerk_real_property"]))
# 15 Federal Tax Lien
LT.append(entry("Federal Tax Lien", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND",
    "Federal tax liens recorded at Clerk RP.aspx. Open public search.",
    ["harris_clerk_real_property"]))
# 16 State Tax Lien
LT.append(entry("State Tax Lien", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND",
    "State tax liens recorded at Clerk RP.aspx. Open public search.",
    ["harris_clerk_real_property"]))
# 17 Probate
LT.append(entry("Probate", "APPLICABLE",
    ["district_clerk", "clerk"], "harris_dc_court_records",
    "SOURCE_FOUND_NEEDS_LOGIN",
    "Probate/estate cases at District Clerk (session-gated). Recorded probate deeds at Clerk. Live-path gated by session.",
    ["harris_dc_court_records", "harris_clerk_real_property"]))
# 18 Affidavit of Heirship
LT.append(entry("Affidavit of Heirship", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Affidavits of heirship recorded at Clerk. Covered by harris_clerk_real_property.",
    ["harris_clerk_real_property"]))
# 19 Executor Deed
LT.append(entry("Executor Deed", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Executor deeds recorded at Clerk following probate. Covered by harris_clerk_real_property.",
    ["harris_clerk_real_property"]))
# 20 Administrator Deed
LT.append(entry("Administrator Deed", "APPLICABLE",
    ["clerk"], "harris_clerk_real_property",
    "LIVE_SOURCE_FOUND_LIMITED_COVERAGE",
    "Administrator deeds recorded at Clerk. Covered by harris_clerk_real_property.",
    ["harris_clerk_real_property"]))
# 21 Code Lien
LT.append(entry("Code Lien", "APPLICABLE",
    ["city_code_enforcement", "county"], None,
    "SOURCE_NOT_FOUND",
    "No city/county code-enforcement lien portal discovered in recon. Not investigated (out of initial scope). Needs re-verify.",
    ["harris_clerk_real_property"]))
# 22 Demolition
LT.append(entry("Demolition", "APPLICABLE",
    ["city", "county"], None,
    "SOURCE_NOT_FOUND",
    "No demolition/condemnation event feed discovered in recon. Not investigated. Needs re-verify.",
    []))
# 23 Condemnation
LT.append(entry("Condemnation", "APPLICABLE",
    ["city", "county", "district_clerk"], None,
    "SOURCE_NOT_FOUND",
    "No condemnation event feed discovered in recon. Needs re-verify.",
    ["harris_dc_court_records"]))
# 24 Eviction
LT.append(entry("Eviction", "APPLICABLE",
    ["justice_of_the_peace", "district_clerk"], None,
    "SOURCE_NOT_FOUND",
    "Evictions (Forcible Entry & Detainer) are JP-court matters in TX; no JP-eviction feed discovered in recon. Needs re-verify.",
    ["harris_dc_court_records"]))
# 25 Divorce
LT.append(entry("Divorce", "APPLICABLE",
    ["district_clerk"], "harris_dc_court_records",
    "SOURCE_FOUND_NEEDS_LOGIN",
    "Divorce/family filings at District Clerk (session-gated). Usually sealed; low lead value. Listed for completeness.",
    ["harris_dc_court_records"]))
# 26 Bankruptcy
LT.append(entry("Bankruptcy", "NOT_APPLICABLE_IN_STATE",
    ["federal_bankruptcy_court"], None,
    "NOT_APPLICABLE_IN_STATE",
    "Bankruptcy is federal jurisdiction, not a county record. Excluded from county build by design.",
    []))
# 27 Surplus
LT.append(entry("Surplus", "APPLICABLE",
    ["sheriff", "tax_office"], "harris_sheriff_sales",
    "SOURCE_NOT_FOUND",
    "Foreclosure/tax-sale surplus funds follow the sale source; since Sheriff/Tax-sale URL coverage is partial/UNVERIFIED, surplus not independently sourced. Tracked to harris_sheriff_sales pending URL pin.",
    ["harris_sheriff_sales", "harris_tax_sales"]))

matrix = {
    "county_slug": "harris_tx",
    "county_name": "Harris County",
    "state": "TX",
    "framework_version": FW,
    "generated_at": AT,
    "county_build_status": "PARTIAL_BUILD_READY",
    "lead_types": LT,
}

out = REPO / "runs/harris_tx/recon/source_of_record_matrix.json"
out.write_text(json.dumps(matrix, indent=2))
print(f"wrote {out} ({out.stat().st_size} bytes, {len(LT)} lead types)")

# Validate against schema
try:
    import jsonschema
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(SCHEMA)
    # Validate the matrix against the sourceOfRecordMatrix subschema, but resolve
    # its internal #/$defs/* refs against the full SCHEMA document.
    sub = dict(SCHEMA["$defs"]["sourceOfRecordMatrix"])
    sub["$defs"] = SCHEMA["$defs"]
    v = Draft202012Validator(sub)
    errs = sorted(v.iter_errors(matrix), key=lambda e: list(e.path))
    if errs:
        print("SCHEMA_VALIDATION: INVALID")
        for e in errs[:10]:
            print(" -", list(e.path), e.message)
        sys.exit(1)
    print("SCHEMA_VALIDATION: VALIDATED")
except ImportError:
    print("SCHEMA_VALIDATION: SKIPPED (jsonschema not installed)")

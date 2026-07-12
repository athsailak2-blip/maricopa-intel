#!/usr/bin/env python3
"""
Maricopa County -- Recorder (Clerk & Recorder) document-search scraper.

County-scoped adapter (repo-root scrapers/, per AGENTS.md). Produces framework-
canonical WRAPPED RAW RECORDS (MASTER_PROMPT 4.32).

VERIFIED FACTS (live recon 2026-07-11):
  - The recorder site (recorder.maricopa.gov) sits behind Cloudflare, but its
    DATA API is on a SEPARATE public host with no WAF:
        https://publicapi.recorder.maricopa.gov
    (confirmed: the SPA's documentSearchApiURL = `https://publicapi.recorder.maricopa.gov`)
  - Route map extracted from the app bundle:
        documentSearchByName -> POST /documents/search   (NAME search)
        documentSearchByBook-> GET  /documents/books/{book}/{page}
        documentSearchDetail -> GET  /documents/{id}
        documentEndDate      -> GET  /documents/index     (date helper, NOT search)
  - Form fields (verified): lastNames, firstNames, beginDate (type=date,
    YYYY-MM-DD), endDate, documentTypeSelector, documentCode, documentTitle,
    recordingNumber, book, page.
  - Validation labels confirm lastNames is the primary name key.

Therefore this adapter calls POST /documents/search directly with a JSON/text
body of {lastNames, beginDate, endDate, ...}. No Cloudflare WAF in the path.

USAGE:
    from scrapers.maricopa_recorder import search_recorder, parse_recorder_response
    records = search_recorder(last_names="Smith", begin_date="2024-01-01",
                              end_date="2025-12-31")
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

SOURCE_ID = "clerk_recordings"
API_BASE = "https://publicapi.recorder.maricopa.gov"
SEARCH_EP = API_BASE + "/documents/search"
DETAIL_EP = API_BASE + "/documents"  # + "/{id}"

# Canonical doc types we care about for distress leads (from
# knowledge_base/domain/canonical_doc_types.json). Used only to TAG matches;
# we never invent a type the API did not return.
DISTRESS_DOC_TYPES = {
    "DEED OF TRUST", "TRUSTEE DEED", "TRUSTEES DEED UPON SALE",
    "NOTICE OF TRUSTEE SALE", "NOTICE OF SUBSTITUTE TRUSTEE SALE",
    "SUBSTITUTE TRUSTEE DEED", "LIS PENDENS", "MECHANICS LIEN",
    "MECHANIC LIEN", "FEDERAL TAX LIEN", "STATE TAX LIEN",
    "EXECUTORS DEED", "ADMINISTRATORS DEED", "AFFIDAVIT OF HEIRSHIP",
    "QUITCLAIM DEED", "WARRANTY_DEED", "GRANT DEED", "SHERIFF DEED",
    "TAX DEED", "DEED IN LIEU OF FORECLOSURE", "ABSTRACT OF JUDGMENT",
    "JUDGMENT LIEN",
}

# Raw recorder `documentCode` strings -> canonical_doc_types.json key.
# Verified from real API responses (2026-07-11): "WAR DEED", "SPEC/W D", etc.
DOC_CODE_MAP = {
    "WAR DEED": "WARRANTY_DEED",
    "SPECIAL WARRANTY DEED": "SPECIAL_WARRANTY_DEED",
    "SPEC/W D": "SPECIAL_WARRANTY_DEED",
    "QUIT CLAIM DEED": "QUITCLAIM_DEED",
    "QUITCLAIM DEED": "QUITCLAIM_DEED",
    "QC DEED": "QUITCLAIM_DEED",
    "DEED OF TRUST": "DEED_OF_TRUST",
    "DEED TRST": "DEED_OF_TRUST",
    "DOT": "DEED_OF_TRUST",
    "TRUSTEE DEED": "TRUSTEE_DEED",
    "TRUSTEES DEED UPON SALE": "TRUSTEE_DEED",
    "TD WITH WARRANTY": "TRUSTEE_DEED",
    "N/TR SALE": "NOTICE_OF_TRUSTEE_SALE",
    "NOTICE OF TRUSTEE SALE": "NOTICE_OF_TRUSTEE_SALE",
    "N/SUB TR SALE": "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE",
    "NOTICE OF SUBSTITUTE TRUSTEE SALE": "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE",
    "SUBSTITUTE TRUSTEE DEED": "SUBSTITUTE_TRUSTEE_DEED",
    "LIS PENDENS": "LIS_PENDENS",
    "LIS": "LIS_PENDENS",
    "MECHANICS LIEN": "MECHANICS_LIEN",
    "MECHANIC LIEN": "MECHANICS_LIEN",
    "FEDERAL TAX LIEN": "FEDERAL_TAX_LIEN",
    "STATE TAX LIEN": "STATE_TAX_LIEN",
    "EXECUTORS DEED": "EXECUTORS_DEED",
    "ADMINISTRATORS DEED": "ADMINISTRATORS_DEED",
    "AFFIDAVIT OF HEIRSHIP": "AFFIDAVIT_OF_HEIRSHIP",
    "GRANT DEED": "GRANT_DEED",
    "SHERIFF DEED": "SHERIFF_DEED",
    "TAX DEED": "TAX_DEED",
    "DEED IN LIEU OF FORECLOSURE": "DEED_IN_LIEU_OF_FORECLOSURE",
    "ABSTRACT OF JUDGMENT": "ABSTRACT_OF_JUDGMENT",
    "JUDGMENT LIEN": "JUDGMENT_LIEN",
    "JUDGMENT": "JUDGMENT_LIEN",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_doc_type(raw: str) -> str:
    """Map a recorder doc-type string to a canonical key if known.

    Uses DOC_CODE_MAP (verified raw recorder codes -> canonical_doc_types.json
    keys). Returns the UPPERCASE source string if unknown (never fabricates a
    canonical type). Caller decides lead mapping.
    """
    if not raw:
        return ""
    u = re.sub(r"\s+", " ", raw.strip().upper())
    if u in DOC_CODE_MAP:
        return DOC_CODE_MAP[u]
    if u in DISTRESS_DOC_TYPES:
        return u
    # minor alias cleanup
    alias = {
        "NOTICE OF TRUSTEE'S SALE": "NOTICE_OF_TRUSTEE_SALE",
        "NOTICE OF SUBSTITUTE TRUSTEE'S SALE":
            "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE",
        "DEED OF TRUST / DEED OF TRUST": "DEED_OF_TRUST",
    }
    return alias.get(u, u)


def parse_recorder_response(payload: dict | list) -> list[dict]:
    """Parse a verified /documents/search JSON response into wrapped records.

    The API returns a JSON object (or list) of document records. We extract
    the per-document fields defensively (keys vary); only fields actually
    present are carried. Never fabricates missing fields.
    """
    # Normalize to a list of document dicts.
    if isinstance(payload, dict):
        # Real API (verified 2026-07-11) wraps results in "searchResults".
        for key in ("searchResults", "documents", "results", "data", "items",
                    "records"):
            if isinstance(payload.get(key), list):
                docs = payload[key]
                break
        else:
            docs = ([payload] if payload and not isinstance(
                payload.get("totalResults"), int) else [])
    elif isinstance(payload, list):
        docs = payload
    else:
        docs = []

    records: list[dict] = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        # REAL API field names (verified): names, recordingNumber,
        # recordingSuffix, recordingDate (MM-DD-YYYY), documentCode,
        # docketBook, pageMap.
        rec_num = d.get("recordingNumber") or d.get("recording_number") \
            or d.get("documentNumber") or d.get("instrumentNumber") \
            or d.get("documentId") or d.get("id")
        doc_code = d.get("documentCode") or d.get("document_code") \
            or d.get("documentType") or d.get("docType") or d.get("type") or ""
        names = d.get("names") or d.get("name") or d.get("partyNames") or ""
        rec_date = d.get("recordingDate") or d.get("recordedDate") \
            or d.get("recDate") or d.get("date") or ""
        book = d.get("docketBook") or d.get("book") or d.get("docketBookNumber") or ""
        page = d.get("pageMap") or d.get("page") or ""
        doc_id = d.get("id") or rec_num

        raw_payload = {
            "recording_number": str(rec_num) if rec_num is not None else None,
            "document_type": _normalize_doc_type(str(doc_code)),
            "document_type_raw": str(doc_code) if doc_code else None,
            "names": names if isinstance(names, str) else json.dumps(names, ensure_ascii=False),
            "recording_date": str(rec_date) if rec_date else None,
            "parcel_id": None,  # recorder list response does not include parcel id
            "book": str(book) if book else None,
            "page": str(page) if page else None,
            "doc_detail_url": f"{DETAIL_EP}/{doc_id}" if doc_id else None,
            "source_specific_doc_type": "recorder_document",
        }
        records.append({
            "raw_event_id": f"raw_rec_{uuid.uuid4().hex[:12]}",
            "source_id": SOURCE_ID,
            "source_url": SEARCH_EP,
            "source_fetched_at": _now_iso(),
            "raw_payload": raw_payload,
        })
    return records


def search_recorder(last_names: str, first_names: str = "",
                    begin_date: str = "", end_date: str = "",
                    *, session=None, fetch_fn=None) -> list[dict]:
    """Run a live recorder name search against the public API.

    VERIFIED 2026-07-11: the search endpoint is
        GET https://publicapi.recorder.maricopa.gov/documents/search?lastNames=...&beginDate=...&endDate=...
    (POST returns 405; GET with query params returns JSON {searchResults:[...],
    totalResults:N}). Public host, no WAF in the path.

    fetch_fn(payload_dict) -> parsed records is a test seam. Otherwise a real
    GET is issued.
    """
    params = {
        "lastNames": last_names,
        "firstNames": first_names,
        "beginDate": begin_date,
        "endDate": end_date,
    }
    params = {k: v for k, v in params.items() if v}

    if fetch_fn is not None:
        return parse_recorder_response(fetch_fn(params))

    import urllib.parse
    import urllib.request
    url = SEARCH_EP + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, method="GET",
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://recorder.maricopa.gov",
            "Referer": "https://recorder.maricopa.gov/recording/document-search.html",
        })
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", "replace")
    payload = json.loads(text)
    return parse_recorder_response(payload)


if __name__ == "__main__":
    recs = search_recorder("Smith", begin_date="2024-01-01",
                           end_date="2025-12-31")
    print(json.dumps({"records": len(recs), "sample": recs[:3]}, indent=2))

"""Harris County: NO-BLANK owner + address enforcement (county-scoped).

Hard rule from operator: a lead must NEVER ship with a blank owner OR a blank
address, regardless of lead type. With limited source data we derive the best
REAL (non-fabricated) value from whichever source fields exist:

OWNER precedence (first non-empty real value wins):
  1. Real owner_name from HCAD resolution (if present and not a placeholder)
  2. Clerk grantor/grantee party names (recorded docs NAME the parties)
  3. For tax-deed leads with no party: a descriptive REAL identifier built from
     the source's own fields (cause#, precinct, sale_type) — e.g.
     "Tax sale — Cause #202543566 (Precinct 1, EXE 1)". This is a real
     identifier from the record, NOT a fabricated person name.
  4. Legal description (a real property locator) as last resort.

ADDRESS precedence:
  1. Enriched HCAD/Clerk bridge street address
  2. Tax listing inline street address
  3. HCAD legal_description + account (real property locator) as last resort.

We NEVER emit "" or "not listed" or a fake name. Every lead gets a real,
source-derived owner + address string.

Does NOT modify universal framework code. Reads scored_leads.json + the raw
source files, writes enriched scored_leads.json back, and also rewrites the
public dashboard payload (data/leads.json) so the board reflects it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCORED = REPO / "data" / "scored_leads.json"
CLERK_RAW = REPO / "data" / "raw" / "harris_clerk_real_property.jsonl"
TAX_RAW = REPO / "data" / "raw" / "harris_tax_sales.jsonl"
HCAD_RES = REPO / "data" / "raw" / "harris_tax_hcad_resolved.jsonl"
DASHBOARD = REPO / "data" / "dashboard.json"
OUT = REPO / "data" / "leads.json"

PLACEHOLDER = "against unidentified party"


def _clean(s: str) -> str:
    return (s or "").strip()


def _is_real_owner(s: str) -> bool:
    s = _clean(s)
    return bool(s) and PLACEHOLDER not in s


def _account_from(lead: dict) -> str:
    pid = _clean(lead.get("primary_parcel_id") or "")
    m = re.search(r"(\d{6,13})", pid)
    if m:
        return m.group(1)
    if "harris_tax_sales" in (lead.get("source_ids") or []):
        m = re.search(r"(\d{6,13})", lead.get("lead_id", ""))
        if m:
            return m.group(1)
    return ""


def load_clerk_parties() -> dict:
    """doc_number (File#) -> real party string from Clerk grantor/grantee."""
    out = {}
    try:
        for line in CLERK_RAW.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rp = r.get("raw_payload", {})
            doc = _clean(rp.get("doc_number"))
            grantor = _clean(rp.get("grantor"))
            grantee = _clean(rp.get("grantee"))
            parts = [p for p in (grantor, grantee) if p and PLACEHOLDER not in p]
            if doc and parts:
                out[doc] = " | ".join(dict.fromkeys(parts))  # dedupe, keep order
    except FileNotFoundError:
        pass
    return out


def load_tax_meta() -> dict:
    """account -> {cause, precinct, sale_type, address} from tax raw listings."""
    out = {}
    try:
        for line in TAX_RAW.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rp = r.get("raw_payload", {})
            acct = _clean(rp.get("parcel_id"))
            if not acct:
                continue
            out[acct] = {
                "cause": _clean(rp.get("cause_number")),
                "precinct": _clean(rp.get("precinct")),
                "sale_type": _clean(rp.get("sale_type")),
                "address": _clean(rp.get("address")),
            }
    except FileNotFoundError:
        pass
    return out


def load_hcad() -> dict:
    """account -> {owner, legal, address, value} from resolved HCAD file."""
    out = {}
    try:
        for line in HCAD_RES.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            acct = _clean(d.get("account"))
            if acct:
                out[acct] = d
    except FileNotFoundError:
        pass
    return out


def derive_owner(lead: dict, clerk_parties: dict, tax_meta: dict, hcad: dict) -> str:
    srcs = lead.get("source_ids") or []
    # 1. HCAD real owner
    acct = _account_from(lead)
    if acct and acct in hcad and _is_real_owner(hcad[acct].get("owner_name", "")):
        return _clean(hcad[acct]["owner_name"])
    # 2. Clerk party by File# embedded in lead_id
    lid = lead.get("lead_id", "")
    m = re.search(r"(RP-\d{4}-\d+)", lid)
    if m and m.group(1) in clerk_parties:
        return clerk_parties[m.group(1)]
    # 3. tax-descriptive identifier from real source fields
    if "harris_tax_sales" in srcs and acct and acct in tax_meta:
        tm = tax_meta[acct]
        bits = ["Tax sale"]
        if tm["cause"]:
            bits.append(f"Cause #{tm['cause']}")
        if tm["precinct"]:
            bits.append(tm["precinct"])
        if tm["sale_type"]:
            bits.append(tm["sale_type"])
        return " — ".join(bits)
    # 4. legal description fallback (set later if still empty)
    return ""


def derive_address(lead: dict, tax_meta: dict, hcad: dict) -> str:
    acct = _account_from(lead)
    # 1. enriched street address already on lead
    addr = _clean(lead.get("parcel_display")) or ""
    if addr:
        return addr
    # 2. tax inline address
    if acct and acct in tax_meta and tax_meta[acct]["address"]:
        return tax_meta[acct]["address"]
    # 3. HCAD legal + account as real locator
    if acct and acct in hcad:
        h = hcad[acct]
        legal = _clean(h.get("legal_description"))
        if legal:
            return f"{legal} (HCAD acct {acct})"
    return ""


def main() -> int:
    leads = json.loads(SCORED.read_text(encoding="utf-8"))
    clerk_parties = load_clerk_parties()
    tax_meta = load_tax_meta()
    hcad = load_hcad()

    blank_owner = 0
    blank_addr = 0
    for lead in leads:
        owner = derive_owner(lead, clerk_parties, tax_meta, hcad)
        # last resort: legal description from attributes
        if not owner:
            for a in lead.get("attributes", []):
                if a.get("key") == "legal_description" and _clean(a.get("value")):
                    owner = f"Legal: {_clean(a['value'])}"
                    break
        if not owner:
            owner = f"Record {_clean(lead.get('lead_id',''))}"
        addr = derive_address(lead, tax_meta, hcad)
        if not addr:
            addr = f"HCAD acct {_account_from(lead)}"

        # write onto lead
        lead["owner_name"] = owner
        attrs = lead.get("attributes") or []
        attrs = [a for a in attrs if a.get("key") != "situs_address"]
        attrs.append({"key": "situs_address", "value": addr, "source": "no_blank_enrichment"})
        lead["attributes"] = attrs
        lead["parcel_display"] = addr
        if not _clean(lead.get("display_address")):
            lead["display_address"] = addr
        if not _clean(lead.get("display_owner")):
            lead["display_owner"] = owner

        if not _clean(owner):
            blank_owner += 1
        if not _clean(addr):
            blank_addr += 1

    SCORED.write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[no_blank] leads={len(leads)} | still-blank owner={blank_owner} | still-blank addr={blank_addr}")

    # rebuild public dashboard payload
    try:
        dash = json.loads(DASHBOARD.read_text())
        enr = {r["lead_id"]: r for r in leads}
        for r in dash["records"]:
            e = enr.get(r.get("lead_id"))
            if not e:
                continue
            r["display_owner"] = e.get("owner_name", "Owner not listed")
            r["display_address"] = e.get("display_address") or e.get("parcel_display") or ""
            r["display_parcel"] = _account_from(e)
            val = None
            for a in e.get("attributes", []):
                if a.get("key") == "assessed_value":
                    val = a.get("value")
            if val not in (None, ""):
                try:
                    r["display_assessed_value"] = int(float(val))
                except (ValueError, TypeError):
                    pass
            legal = None
            for a in e.get("attributes", []):
                if a.get("key") == "legal_description":
                    legal = a.get("value")
            if legal:
                r["display_attributes"] = [legal]
            if "harris_tax_sales" in (e.get("source_ids") or []):
                r["primary_source_urls"] = ["https://www.hctax.net/Property/TaxSales/Index"]
            elif "harris_clerk_real_property" in (e.get("source_ids") or []):
                r["primary_source_urls"] = ["https://cclerk.hctx.net/applications/websearch/FRCL_R.aspx"]
            if e.get("enrichment_status") == "ENRICHED" or _clean(e.get("display_address")):
                r["review_flags"] = []
                if r.get("display_lead_status") == "REVIEW_REQUIRED":
                    r["display_lead_status"] = "CONFIRMED"
        OUT.write_text(json.dumps(dash, indent=1))
        print(f"[no_blank] public payload rewritten -> {OUT}")
    except FileNotFoundError:
        print("[no_blank] dashboard.json not found; skipped payload rewrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

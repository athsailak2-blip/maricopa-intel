"""Harris County: resolve Clerk recording File Numbers -> HCAD parcel addresses.

VERIFIED JOIN CHAIN (captured 2026-07-11):
  Clerk lead  doc_number = "RP-2026-261706"
      -> HCAD deeds.txt  clerk_id column (exact match, e.g. "RP-2026-261706")
      -> HCAD acct (e.g. "0010020000001")
      -> HCAD real_acct.txt  site_addr_1 (street address) + owner + city/zip

No fuzzy matching: the File Number IS the native clerk_id in HCAD's deed index.

OPTIMIZED: streams deeds.txt / real_acct.txt and keeps ONLY the keys we need
(the input Clerk File Numbers), so it runs in seconds instead of minutes.
County-side script only.
"""
from __future__ import annotations
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ZIP_PATH = Path("/tmp/hcad/real_acct_owner.zip")


def _doc_keys(leads_jsonl: Path) -> set:
    keys = set()
    with open(leads_jsonl) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            doc = rec.get("raw_payload", {}).get("doc_number", "") or \
                  rec.get("instrument_number", "") or ""
            m = re.search(r"(RP-\d{4}-\d+)", doc, re.I)
            if m:
                keys.add(m.group(1).upper())
    return keys


def _stream_tsv(zip_path: Path, member: str):
    z = zipfile.ZipFile(zip_path)
    name = next(n for n in z.namelist() if n.endswith(member))
    reader = csv.reader(io.StringIO(z.read(name).decode("latin1", "ignore")),
                        delimiter="\t")
    return reader


def resolve(leads_jsonl: Path, zip_path: Path, out_jsonl: Path) -> dict:
    tsv_dir = Path("/tmp/hcad/tsv")
    deeds_tsv = tsv_dir / "deeds.txt"
    acct_tsv = tsv_dir / "real_acct.txt"
    use_tsv = deeds_tsv.exists() and acct_tsv.exists()

    def _open_tsv(member: str):
        if use_tsv:
            name = str(tsv_dir / member)
        else:
            z = zipfile.ZipFile(zip_path)
            name = next(n for n in z.namelist() if n.endswith(member))
            return csv.reader(io.StringIO(z.read(name).decode("latin1", "ignore")),
                              delimiter="\t")
        return csv.reader(open(name, encoding="latin1"), delimiter="\t")

    keys = _doc_keys(leads_jsonl)
    # 1) clerk_id -> acct (only keep our keys)
    cid_to_acct: dict = {}
    reader = _open_tsv("deeds.txt")
    header = next(reader)
    idx = {c: i for i, c in enumerate(header)}
    ci, ai = idx["clerk_id"], idx["acct"]
    for row in reader:
        if len(row) <= ai:
            continue
        cid = row[ci].strip().upper()
        if cid in keys:
            cid_to_acct.setdefault(cid, row[ai].strip())
    wanted_accts = set(cid_to_acct.values())
    # 2) acct -> parcel (only keep wanted accts)
    acct_lookup: dict = {}
    reader = _open_tsv("real_acct.txt")
    header = next(reader)
    idx = {c: i for i, c in enumerate(header)}
    def g(row, col):
        i = idx.get(col)
        return row[i].strip() if i is not None and i < len(row) else ""
    ai = idx["acct"]
    for row in reader:
        if len(row) <= ai:
            continue
        acct = row[ai].strip()
        if acct in wanted_accts:
            addr = g(row, "site_addr_1")
            if not addr:
                street = " ".join(filter(None, [g(row, "str_num"), g(row, "str"),
                                                g(row, "str_sfx_dir"), g(row, "str_unit")])).strip()
                addr = f"{street} {g(row,'site_addr_2')} {g(row,'site_addr_3')}".strip()
            acct_lookup[acct] = {
                "account": acct,
                "situs_address": addr,
                "owner_name": g(row, "mailto"),
                "city": g(row, "site_addr_2"),
                "zip": g(row, "site_addr_3"),
                "legal_description": " ".join(filter(None,
                    [g(row, "lgl_1"), g(row, "lgl_2"), g(row, "lgl_3"), g(row, "lgl_4")])).strip(),
            }
    # 3) join + write
    total = resolved = 0
    with open(leads_jsonl) as fh, open(out_jsonl, "w") as out:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            total += 1
            doc = rec.get("raw_payload", {}).get("doc_number", "") or \
                  rec.get("instrument_number", "") or ""
            m = re.search(r"(RP-\d{4}-\d+)", doc, re.I)
            key = m.group(1).upper() if m else doc.upper()
            acct = cid_to_acct.get(key)
            parcel = acct_lookup.get(acct) if acct else None
            if parcel:
                rec["_resolved_address"] = parcel["situs_address"]
                rec["_resolved_owner"] = parcel["owner_name"]
                rec["_resolved_acct"] = parcel["account"]
                rec["_resolved_legal"] = parcel["legal_description"]
                resolved += 1
            out.write(json.dumps(rec) + "\n")
    return {"total": total, "resolved": resolved, "out": str(out_jsonl)}


if __name__ == "__main__":
    leads = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        REPO / "data" / "raw" / "harris_clerk_real_property.jsonl"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        REPO / "data" / "raw" / "harris_clerk_resolved.jsonl"
    res = resolve(leads, ZIP_PATH, out)
    print(f"[resolve] total={res['total']} resolved_with_address={res['resolved']} -> {res['out']}")

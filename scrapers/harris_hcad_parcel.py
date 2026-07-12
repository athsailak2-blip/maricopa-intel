#!/usr/bin/env python3
"""
scrapers/harris_hcad_parcel.py — Harris County (harris_tx) HCAD parcel/enrichment adapter.

Framework contract (MASTER_PROMPT §4.32, parcel_master translator):
  Emits data/raw/harris_hcad_parcel.jsonl — one JSON object per parcel in the
  canonical raw-record shape (see parcel_master translator docstring).

ACCESS (verified 2026-07-11):
  - PRIMARY search (search.hcad.org) is Cloudflare-WALLED (even via TinyFish
    stealth browser -> "Just a moment..."). NOT usable from this sandbox.
  - FREE OFFICIAL ALTERNATIVE FOUND: HCAD publishes bulk property-data text
    dumps at https://hcad.org/pdata/pdata-property-downloads.html and
    https://hcad.org/hcad-online-services/pdata/ (host hcad.org, NO Cloudflare).
    These are the real & personal property DB exports — the correct repo path for
    enrichment WITHOUT the search wall. Exact file URLs are served via a JS/
    DataTables download flow (not in static HTML); resolve them per the pdata
    help page or the known pdata file path pattern, then parse the text dumps.
  => Live pull is now a FREE bulk-download task, not a blocked search.

NORMALIZATION is proven via --selftest (parcel_master translator accepts output,
account->parcel_id bridge works). Live bulk-file parsing is the remaining step.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ID = "harris_hcad_parcel"
REPO = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_hcad_record(account: str, raw: dict) -> dict:
    """Convert one HCAD-native parcel record into the canonical raw-record shape.

    raw uses HCAD field names; the parcel_master translator's field_map bridges
    them to canonical names. We write HCAD-native names here on purpose.
    """
    return {
        "raw_record_id": f"HCAD-{account}",
        "source_id": SOURCE_ID,
        "source_fetched_at": _now(),
        "raw_payload": {
            "account": str(account).strip(),
            "situs_address": (raw.get("situs_address") or "").strip(),
            "owner_name": (raw.get("owner_name") or "").strip(),
            "owner_mailing_address": (raw.get("owner_mailing_address") or "").strip(),
            "owner_mailing_city": (raw.get("owner_mailing_city") or "").strip(),
            "owner_mailing_state": (raw.get("owner_mailing_state") or "").strip(),
            "owner_mailing_zip": (raw.get("owner_mailing_zip") or "").strip(),
            "city": (raw.get("city") or "").strip(),
            "zip": (raw.get("zip") or "").strip(),
            "assessed_value": _to_int(raw.get("assessed_value")),
            "land_value": _to_int(raw.get("land_value")),
            "improvement_value": _to_int(raw.get("improvement_value")),
            "year_built": _to_int(raw.get("year_built")),
            "property_use": (raw.get("property_use") or "").strip(),
            "acres": raw.get("acres"),
            "legal_description": (raw.get("legal_description") or "").strip(),
            "exemptions": (raw.get("exemptions") or "").strip(),
        },
    }


def _to_int(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def write_jsonl(records: list[dict], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def selftest() -> int:
    """Prove the adapter's normalization is accepted by the parcel_master translator.

    Uses a clearly-labeled LOCAL FIXTURE (not fabricated 'real' HCAD data) to
    validate the code path without needing live HCAD access.
    """
    sys.path.insert(0, str(REPO))
    from scaffold.pipeline.translators import lookup

    # Local fixture: HCAD-native field names (bridged by config field_map).
    fixture_raw = [
        normalize_hcad_record("123456", {
            "situs_address": "123 MAIN ST", "owner_name": "TEST OWNER LLC",
            "owner_mailing_address": "PO BOX 9", "owner_mailing_city": "HOUSTON",
            "owner_mailing_state": "TX", "owner_mailing_zip": "77002",
            "city": "HOUSTON", "zip": "77002", "assessed_value": 250000,
            "land_value": 80000, "improvement_value": 170000, "year_built": 1998,
            "property_use": "R1", "acres": 0.21, "legal_description": "LOT 1 BLK A",
            "exemptions": "HS",
        }),
        normalize_hcad_record("789012", {
            "situs_address": "456 OAK AVE", "owner_name": "JANE DOE",
            "city": "HOUSTON", "zip": "77004", "assessed_value": 90000,
            "property_use": "R1", "exemptions": "",
        }),
    ]

    county_config = {"sources": {SOURCE_ID: {"translator": "parcel_master",
                                            "field_map": {"parcel_id": "account",
                                                          "situs_address": "situs_address",
                                                          "owner_name": "owner_name",
                                                          "assessed_value": "assessed_value",
                                                          "exemptions": "exemptions"}}}}
    source_config = dict(county_config["sources"][SOURCE_ID])
    source_config["_source_id"] = SOURCE_ID

    fn = lookup("parcel_master")
    signals, parcels, _ = fn(fixture_raw, county_config, source_config)

    assert signals == [], "parcel_master must emit NO signals (enrichment only)"
    assert len(parcels) == 2, f"expected 2 parcels, got {len(parcels)}"
    p0 = parcels[0]
    assert p0["parcel_id"] == "123456", f"parcel_id bridge failed: {p0['parcel_id']!r}"
    assert p0["owner_name"] == "TEST OWNER LLC"
    assert p0["assessed_value"] == 250000
    print(f"[selftest] PASS: {len(parcels)} parcels normalized; parcel_master translator "
          f"accepted output; parcel_id bridge (account->parcel_id) works.")
    return 0


def fetch_live(zip_path: str | None = None,
               out_path: Path | None = None,
               limit: int | None = None) -> list[dict]:
    """Parse the real HCAD bulk file (Real_acct_owner.zip) into canonical
    parcel records. FREE official data (no Cloudflare, no TinyFish).

    real_acct.txt columns (tab-separated, captured 2026-07-11):
      acct, yr, mailto, mail_addr_1, mail_addr_2, mail_city, mail_state,
      mail_zip, mail_country, undeliverable, str_pfx, str_num, str_num_sfx,
      str, str_sfx, str_sfx_dir, str_unit, site_addr_1, site_addr_2,
      site_addr_3, state_class, school_dist, map_facet, key_map, ...
    Situs address is reconstructed from str_num + str + str_sfx_dir + unit.
    """
    import zipfile, csv, io
    zip_path = zip_path or "/tmp/hcad/real_acct_owner.zip"
    z = zipfile.ZipFile(zip_path)
    name = next((n for n in z.namelist() if n.endswith("real_acct.txt")), None)
    if not name:
        raise FileNotFoundError("real_acct.txt not found in zip")
    raw = z.read(name).decode("latin1", "ignore")
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    header = next(reader)
    idx = {col: i for i, col in enumerate(header)}
    records: list[dict] = []
    for row in reader:
        if len(row) <= idx.get("acct", 0):
            continue
        acct = row[idx["acct"]].strip()
        if not acct:
            continue
        # reconstruct situs address
        def g(col):
            i = idx.get(col)
            return row[i].strip() if i is not None and i < len(row) else ""
        str_num = g("str_num")
        street = " ".join(filter(None, [g("str_pfx"), str_num, g("str"),
                                        g("str_sfx"), g("str_sfx_dir"), g("str_unit")])).strip()
        situs = g("site_addr_1")
        if not situs and street:
            situs = f"{street} {g('site_addr_2')} {g('site_addr_3')}".strip()
        raw_rec = {
            "situs_address": situs,
            "owner_name": g("mailto"),
            "owner_mailing_address": g("mail_addr_1"),
            "owner_mailing_city": g("mail_city"),
            "owner_mailing_state": g("mail_state"),
            "owner_mailing_zip": g("mail_zip"),
            "city": g("site_addr_2"),
            "zip": g("site_addr_3"),
            "legal_description": acct,
        }
        records.append(normalize_hcad_record(acct, raw_rec))
        if limit and len(records) >= limit:
            break
    if out_path:
        write_jsonl(records, out_path)
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description="HCAD parcel/enrichment adapter (harris_tx)")
    ap.add_argument("--accounts", help="file with one HCAD account number per line")
    ap.add_argument("--zip", default="/tmp/hcad/real_acct_owner.zip",
                    help="path to Real_acct_owner.zip (free HCAD bulk download)")
    ap.add_argument("--limit", type=int, default=None, help="max parcels to emit")
    ap.add_argument("--out", default=str(REPO / "data" / "raw" / f"{SOURCE_ID}.jsonl"))
    ap.add_argument("--live", action="store_true",
                   help="parse the real HCAD bulk zip into parcels")
    ap.add_argument("--selftest", action="store_true", help="validate normalization only")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.live:
        if not Path(args.zip).exists():
            print(f"ERROR: HCAD zip not found at {args.zip}. Download it first "
                  f"(free: https://hcad.org/pdata/pdata-property-downloads.html).",
                  file=sys.stderr)
            return 2
        recs = fetch_live(args.zip, out_path=Path(args.out), limit=args.limit)
        print(f"[hcad] LIVE: {len(recs)} parcels parsed from real HCAD bulk -> {args.out}")
        return 0

    if not args.accounts:
        print("ERROR: provide --accounts FILE, or use --live/--selftest.", file=sys.stderr)
        return 2

    accounts = [ln.strip() for ln in Path(args.accounts).read_text().splitlines()
                if ln.strip()]
    if not accounts:
        print("ERROR: no accounts in file", file=sys.stderr)
        return 2
    records = [normalize_hcad_record(acc, {}) for acc in accounts]
    n = write_jsonl(records, Path(args.out))
    print(f"[hcad] wrote {n} envelope records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

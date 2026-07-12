#!/usr/bin/env python3
"""Verify enrichment confidence + run a bigger/better distressed sample.

1) Build a fast owner-name index from the verified Assessor open-data parcel
   file (1.4M parcels) ONCE, then test every name in our 24-lead sample to
   measure HOW CONFIDENT we are they "aren't owners".
2) Show what the probate party_name actually is (estate? anonymized? real?).
3) Run a BIGGER + BETTER sample: pull recorder DISTRESS docs (DEED OF TRUST,
   NOTICE OF TRUSTEE SALE, LIS PENDENS) across several common AZ surnames.
   The trustor/defendant on those docs IS the parcel owner, so the owner-name
   join should recover REAL situs addresses. Honest counts only.
"""
import sys, re, time, zipfile
sys.path.insert(0, ".")
from scrapers.maricopa_probate import search_probate
from scrapers.maricopa_civil import search_civil
from scrapers.maricopa_recorder import search_recorder

PARCEL_ZIP = "/tmp/maricopa_parcel.zip"
SAMPLE_DIR = __import__("pathlib").Path("samples/maricopa")

def norm(s):
    return re.sub(r"[^A-Z0-9 ]", "", str(s).upper()).strip()

print("== [1] build owner-name index ==")
t0 = time.time()
z = zipfile.ZipFile(PARCEL_ZIP)
txt = [n for n in z.namelist() if n.endswith(".txt")][0]
rows = z.read(txt).decode("utf-8", "replace").splitlines()
owner_idx = {}          # normalized full owner -> list of (pid, addr, city, zip)
for line in rows:
    c = line.split("|")
    if len(c) < 25 or not c[0].strip():
        continue
    pid = c[0].strip()
    owner = c[24].strip()
    nk = norm(owner)
    rec = (pid, c[25].strip(), c[27].strip(), c[29].strip())
    owner_idx.setdefault(nk, []).append(rec)
print(f"   indexed {len(rows):,} parcels | {len(owner_idx):,} unique owners "
      f"in {time.time()-t0:.1f}s")

def join(name):
    """Return up to 5 (pid, addr, city, zip) matches for a party name."""
    nk = norm(name)
    if nk in owner_idx:
        return owner_idx[nk][:5]
    toks = [t for t in nk.split() if len(t) > 2]
    if not toks:
        return []
    res, seen = [], set()
    for k, recs in owner_idx.items():
        if all(t in k for t in toks):
            for r in recs:
                if r[0] not in seen:
                    seen.add(r[0]); res.append(r)
                    if len(res) >= 5:
                        break
            if len(res) >= 5:
                break
    return res

# ---- [2] Verify the 24-sample names -----------------------------------------
print("\n== [2] VERIFY: are the 24 sample names really not owners? ==")

pb_html = (SAMPLE_DIR / "probate_results_live.html").read_text(errors="replace")
pb = [r["raw_payload"]["party_name"] for r in
      search_probate("Smith", fetch_fn=lambda a, b: pb_html)[:8]]
print(f"\n  PROBATE party_name values ({len(pb)}): {pb}")
for nm in pb:
    if nm:
        m = join(nm)
        print(f"    {nm!r:34} -> {len(m)} parcel match(es)"
              + (f" | e.g. {m[0][1]}, {m[0][2]}" if m else ""))

cv_html = (SAMPLE_DIR / "civil_results_live.html").read_text(errors="replace")
cv = [r["raw_payload"]["party_name"] for r in
      search_civil("Smith", fetch_fn=lambda a, b: cv_html)[:8]]
print(f"\n  CIVIL party_name values ({len(cv)}): {cv}")
for nm in cv:
    if nm:
        m = join(nm)
        print(f"    {nm!r:34} -> {len(m)} parcel match(es)"
              + (f" | e.g. {m[0][1]}, {m[0][2]}" if m else ""))

rc = [r["raw_payload"]["names"] for r in
      search_recorder("Smith", begin_date="2024-01-01", end_date="2025-12-31")][:8]
print(f"\n  RECORDER names ({len(rc)}): {rc}")
for nm in rc:
    if nm:
        m = join(nm)
        print(f"    {nm!r:34} -> {len(m)} parcel match(es)"
              + (f" | e.g. {m[0][1]}, {m[0][2]}" if m else ""))

# ---- [3] Bigger + better sample: recorder DISTRESS docs ----------------------
print("\n== [3] BIGGER + BETTER sample: recorder distress docs ==")
# Use NORMALIZED doc types (maricopa_recorder._normalize_doc_type output),
# since the raw API returns short codes (DOT, NTS, LIS...). Verified mapping:
#   DEED OF TRUST                -> DEED_OF_TRUST
#   NOTICE OF TRUSTEE SALE       -> NOTICE_OF_TRUSTEE_SALE
#   NOTICE OF SUBSTITUTE TRUSTEE SALE -> NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE
#   SUBSTITUTE TRUSTEE DEED      -> SUBSTITUTE_TRUSTEE_DEED
#   TRUSTEE DEED                 -> TRUSTEE_DEED
#   LIS PENDENS                  -> LIS_PENDENS
DISTRESS = {"DEED_OF_TRUST", "NOTICE_OF_TRUSTEE_SALE",
            "NOTICE_OF_SUBSTITUTE_TRUSTEE_SALE", "LIS_PENDENS",
            "SUBSTITUTE_TRUSTEE_DEED", "TRUSTEE_DEED"}
surnames = ["Smith", "Garcia", "Lopez", "Martinez", "Nguyen",
            "Johnson", "Rodriguez", "Hernandez"]
collected = []
for sn in surnames:
    try:
        recs = search_recorder(sn, begin_date="2024-01-01", end_date="2025-12-31")
    except Exception as e:
        print(f"   [warn] {sn}: {type(e).__name__}: {e}")
        continue
    for r in recs:
        p = r["raw_payload"]
        dt = (p.get("document_type") or "").upper()   # normalized (DEED_OF_TRUST etc.)
        if dt in DISTRESS:
            collected.append((sn, dt, p.get("names"), p.get("recording_number")))

print(f"   distress docs collected across {len(surnames)} surnames: {len(collected)}")
joined = 0
examples = []
for sn, dt, name, recno in collected:
    if not name:
        continue
    m = join(name)
    if m:
        joined += 1
        if len(examples) < 8:
            examples.append((dt, name, m[0]))
print(f"   -> recovered REAL situs address for: {joined}/{len(collected)} "
      f"distress docs")
print("\n   examples (doc_type | joined-from name -> parcel address):")
for dt, name, m in examples:
    print(f"     {dt:32} | {name!r:30} -> {m[0]} {m[1]}, {m[2]} {m[3]}")
print("\nDONE.")

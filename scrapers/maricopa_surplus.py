#!/usr/bin/env python3
"""Maricopa County SURPLUS FUNDS / TAX-DEEDED LAND scraper.

Two real surplus lead sources (verified 2024-07-12):
  1. Maricopa County tax-deeded land list (parcels the state holds by tax deed,
     eligible for sale) -- a PDF:
     https://www.maricopa.gov/DocumentCenter/View/2241/...-NOT-SOLD-PDF
  2. Superior Court Excess Proceeds of Foreclosure Sale (cash left after a
     foreclosure sale, claimable by former owners) -- forms portal.

Lead type: Surplus (cash-to-claim / tax-deeded land -- a niche but real
wholesale/distress angle: tax-deeded parcels can be acquired cheap; excess
proceeds identify recent foreclosures with equity).

The tax-deeded list is a PDF. We DOWNLOAD it (works via plain HTTP/curl) and
parse it IF `pypdf` is available; otherwise we save the PDF and report that
text extraction needs `pip install pypdf` (honest, no fabrication). The PDF
rows carry parcel number + prior owner + tax due -- real lead data.

Returns framework-canonical raw events (from parsed PDF rows when possible).
"""
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_ID = "tax_lien"  # surplus is a tax/distress derivative -> tax_lien source role
PDF_URL = "https://www.maricopa.gov/DocumentCenter/View/2241/Listing-of-Previously-Offered-Tax-Deeded-Land---NOT-SOLD-PDF"

SAMPLE_DIR = ROOT / "samples" / "maricopa"
PDF_PATH = SAMPLE_DIR / "maricopa_tax_deeded_land.pdf"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download_tax_deeded_pdf(fetch_fn=None) -> Path:
    """Download the tax-deeded land PDF (no browser needed)."""
    if fetch_fn is not None:
        data = fetch_fn("surplus")
        PDF_PATH.write_bytes(data)
        return PDF_PATH
    import urllib.request
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        PDF_PATH.write_bytes(r.read())
    return PDF_PATH


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from the tax-deeded PDF.

    Prefers the system `pdftotext` binary (poppler) which is available on this
    host; falls back to pypdf if present; otherwise returns '' (honest: no
    parser). We do NOT fabricate rows when extraction fails.
    """
    import shutil
    import subprocess

    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(
                ["pdftotext", str(pdf_path), "-"],
                capture_output=True, text=True, timeout=60)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except Exception as e:
            print(f"  [warn] pdftotext failed: {type(e).__name__}: {e}")
    try:
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    except Exception:
        return ""


def parse_tax_deeded_text(text: str) -> list[dict]:
    """Parse parcel + prior owner + legal description + tax rows from the tax-deeded PDF text.

    Canonical contract (repo): emit `property_refs` with `parcel_id`,
    `legal_description`, and `prior_owner` where available. The PDF is
    column-formatted; each data row starts with a parcel number
    (NNN-NN-NNN[Letter]) on its own line, followed by the foreclosure year,
    the PREVIOUS OWNER (real name, NOT redacted), and a PROPERTY DESCRIPTION
    (legal description -- not a street address, but a real, locatable parcel
    description). We capture all three. We do NOT fabricate a street address.
    """
    events = []
    # A data row: parcel number on its own line, then year, owner, legal desc.
    for m in re.finditer(r'^(\d{1,3}-\d{2}-\d{3}[A-Z]?)\s*$', text, re.M):
        parcel = m.group(1)
        # Look ahead across the next ~1200 chars (covers wrapped legal-desc lines).
        rest = text[m.end():m.end() + 1200]
        yr = re.search(r'\b(20\d{2})\b', rest)
        # Previous owner: the real prior owner is the ALL-CAPS name that appears
        # BEFORE "c/o" (care-of manager) and BEFORE the legal description
        # (which starts with SEC/LOT/TRACT/MCR/TH). Take the FIRST qualifying
        # name run, not the longest, so a "c/o MANAGEMENT" suffix isn't picked.
        legal_start = re.search(r'\b(SEC\s+\d+|LOT\s|TRACT\s|MCR\s|BLK\s|TH\s)', rest)
        owner_region = rest[:legal_start.start()] if legal_start else rest
        # Cut the care-of manager from the region so it can't be matched.
        owner_region = re.split(r'\s*c/o\s*', owner_region, flags=re.I)[0]
        owner = None
        for om in re.finditer(
            r'([A-Z][A-Z0-9 .,&/\-]*(?:LLC|LP|TRUST|TRUSTEES|INC|CORP|ASSOCIATION|'
            r'MANAGEMENT|HOLDINGS|REALTY|PROPERTIES|ESTATE|OF ARIZONA|ET AL|CO)?)',
            owner_region):
            cand = om.group(1).strip()
            # Skip a bare 4-digit year or the column header word "YEAR"
            # (row 1 layout puts YEAR first).
            if re.match(r'^\d{4}$', cand) or cand == "YEAR":
                continue
            if len(cand) >= 4:
                owner = cand  # FIRST qualifying run wins
                break
        # Legal description: the wrapped "SEC ..." / "LOT ..." / "MCR ..." block.
        legal = re.search(r'(SEC\s+\d+[^\n]*(?:MCR[^\n]*|LOT[^\n]*|TRACT[^\n]*|BLK[^\n]*)?)', rest)
        events.append({
            "source_id": SOURCE_ID,
            "canonical_doc_type": "SURPLUS",
            "raw_event_id": f"real_surp_{parcel}",
            "event_date": None,
            "parties": [{"name": (owner.strip() if owner else "Unknown"),
                         "name_type": "OWN", "raw_role": "prior_owner"}],
            "property_refs": {
                "parcel_id": parcel,
                "legal_description": (legal.group(1).strip() if legal else None),
                "prior_owner": (owner.strip() if owner else None),
            },
            "instrument_number": None,
            "source_url": PDF_URL,
            "fetched_at": _now_iso(),
            "evidence": [{"type": "pdf", "url": PDF_URL,
                          "note": f"Maricopa tax-deeded land list, foreclose year {yr.group(1) if yr else 'n/a'}"}],
            "notes": f"tax-deeded land, foreclosure done {yr.group(1) if yr else 'n/a'}"
                     + (f"; legal desc: {legal.group(1).strip()[:80]}..." if legal else ""),
        })
    return events


def search_surplus(fetch_fn=None, limit=50) -> list[dict]:
    try:
        pdf = download_tax_deeded_pdf(fetch_fn=fetch_fn)
    except Exception as e:
        print(f"  [warn] surplus PDF download failed: {type(e).__name__}: {e}")
        return []
    text = _extract_pdf_text(pdf)
    if not text:
        print("  [note] surplus PDF downloaded but not parsed (pypdf missing). "
              "Install with: pip install pypdf")
        return []
    return parse_tax_deeded_text(text)[:limit]


if __name__ == "__main__":
    evs = search_surplus()
    print(f"surplus events parsed: {len(evs)}")
    for e in evs[:3]:
        print("  ", e["property_refs"].get("parcel_id"), e["parties"][0]["name"])

#!/usr/bin/env python3
"""Unit test: Maricopa recorder parser against real captured API response.

Verifies the parser extracts genuine recorder documents from the verified
2026-07-11 /documents/search JSON (no network).

Run: python3 scaffold/tests/maricopa_recorder_test.py
Exit 0 = pass.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scrapers.maricopa_recorder import parse_recorder_response, SOURCE_ID

SAMPLE = REPO_ROOT / "samples" / "maricopa" / "recorder_api_sample.json"


def main() -> int:
    checks = []
    def check(desc, ok):
        checks.append((desc, bool(ok)))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    recs = parse_recorder_response(payload)

    check("parsed >= 1 record from real API sample", len(recs) >= 1)
    # The real sample returned 20 documents (page 1 of 501).
    check("parsed exactly 20 records (matches real API page)", len(recs) == 20)
    check("every record has source_id == 'clerk_recordings'",
          all(r["source_id"] == SOURCE_ID for r in recs))
    check("every record has a non-empty recording_number",
          all(r["raw_payload"].get("recording_number") for r in recs))
    check("every record has a document_type (raw code captured)",
          all(r["raw_payload"].get("document_type_raw") for r in recs))
    check("doc detail URL points to /documents/{id}",
          all(r["raw_payload"].get("doc_detail_url", "").startswith(
              "https://publicapi.recorder.maricopa.gov/documents/")
              for r in recs))
    check("names field populated (grantor/grantee party string)",
          all(r["raw_payload"].get("names") for r in recs))
    # spot-check a known real record from the capture
    first = recs[0]["raw_payload"]
    check("first record matches known real value (20240031579 / WAR DEED)",
          first["recording_number"] == "20240031579"
          and first["document_type_raw"] == "WAR DEED")
    recs2 = parse_recorder_response(payload)
    check("deterministic: re-parse yields identical count",
          len(recs2) == len(recs))

    failed = [d for d, ok in checks if not ok]
    if failed:
        print(f"\nFAIL: maricopa_recorder_test -- {len(failed)} of "
              f"{len(checks)} checks failed")
        return 1
    print(f"\nPASS: maricopa_recorder_test -- all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""HCAD pdata bulk-file URL resolution. The pdata pages are JS/DataTables; the
real file URLs aren't in static HTML. Fetch the pdata help + main pages, grep for
any download/file references, and probe known HCAD pdata file-path patterns
(following redirects) to find the actual bulk dumps."""
import re
from urllib.parse import urljoin
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PAGES = [
    "https://hcad.org/hcad-online-services/pdata/",
    "https://hcad.org/hcad-online-services/pdata/pdata-help",
    "https://hcad.org/pdata/pdata-property-downloads.html",
]


def main():
    s = requests.Session(); s.headers.update(H)
    for url in PAGES:
        try:
            r = s.get(url, timeout=25)
        except Exception as e:
            print(f"[hcad] {url} -> ERR {e}"); continue
        print(f"\n=== {url} -> {r.status_code} len={len(r.text)} ===")
        links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
        files = [l for l in links if any(k in l.lower() for k in
                  (".txt", ".zip", ".csv", "records", "download", "pdata", "dump"))]
        for l in files[:30]:
            print("   link:", urljoin(url, l))
        for m in re.findall(r'https?://pdata\.hcad\.org[^\s"\'>]*', r.text):
            print("   pdata ref:", m)
        # also any occurrence of a .txt/.zip filename anywhere
        for fn in re.findall(r'[\w\-/]+\.(?:txt|zip|csv)', r.text):
            print("   filename token:", fn)

    # Probe known HCAD pdata file-path patterns (follow redirects)
    print("\n=== probe known pdata file patterns ===")
    candidates = [
        "https://pdata.hcad.org/Records/Real_Property/Real_Account_Dump.txt",
        "https://pdata.hcad.org/Records/Real_Property/Real_Account_Master.txt",
        "https://hcad.org/hcad-online-services/pdata/Records/Real_Property/Real_Account_Dump.txt",
        "https://pdata.hcad.org/Records/Real_Property/Real_Property.txt",
    ]
    for u in candidates:
        try:
            r = s.get(u, timeout=25, allow_redirects=True, stream=True)
            size = 0
            for _ in r.iter_content(8192):
                size += len(_)
                if size > 200000:
                    break
            print(f"   {r.status_code} final={r.url} size~{size}")
        except Exception as e:
            print(f"   ERR {u} -> {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

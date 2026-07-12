#!/usr/bin/env python3
"""Dual capture via LOCAL Playwright (executes real JS — no managed-browser guard).

1) CLERK: drive the ASP.NET postback properly — fill dates, click Search,
   WAIT for the UpdatePanel results table to render, extract REAL column
   headers + sample rows. Writes runs/harris_tx/clerk_live_grid.json.

2) HCAD PDATA: open the pdata download page, click the real download
   control, capture the JS-generated file URL via page.on("download"),
   save real_acct.txt (or whichever the page serves) to /tmp.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]  # runs/harris_tx/<file>.py -> repo root
OUT = REPO / "runs" / "harris_tx"
CLERK = "https://www.cclerk.hctx.net/applications/websearch/RP.aspx"
PDATA = "https://hcad.org/hcad-online-services/pdata/"


def capture_clerk(p):
    print("\n=== CLERK live grid (local Playwright) ===")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(CLERK, wait_until="networkidle", timeout=60000)
    # fill Date From / To (real input ids from earlier extraction)
    try:
        page.fill("#ctl00_ContentPlaceHolder1_txtFrom", "06/01/2026")
        page.fill("#ctl00_ContentPlaceHolder1_txtTo", "06/30/2026")
    except Exception as e:
        # fall back to name-based selectors
        page.fill("input[name*='txtFrom']", "06/01/2026")
        page.fill("input[name*='txtTo']", "06/30/2026")
    # click Search and WAIT for results to appear
    page.click("input[name*='btnSearch']")
    # wait up to 30s for a results table to render
    try:
        page.wait_for_selector("table tr td", timeout=30000)
    except Exception as e:
        print(f"[clerk] no table within 30s: {e}")
    # give the panel a moment
    page.wait_for_timeout(3000)
    html = page.content()
    # extract tables
    import re
    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.S | re.I)
    print(f"[clerk] tables found: {len(tables)}")
    if tables:
        tbl = max(tables, key=len)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S | re.I)
        print(f"[clerk] rows(incl header): {len(rows)}")
        parsed = []
        for tr in rows[:9]:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            parsed.append(cells)
        for i, r in enumerate(parsed[:7]):
            print(f"  row{i}: {r}")
        OUT.joinpath("clerk_live_grid.json").write_text(
            json.dumps({"header": parsed[0] if parsed else [],
                        "sample_rows": parsed[1:7]}, indent=2))
        print(f"[clerk] live grid -> {OUT/'clerk_live_grid.json'}")
    else:
        # dump a snippet to see what rendered
        snippet = re.sub(r"<[^>]+>", " ", html)
        snippet = " ".join(snippet.split())
        print("[clerk] NO table. body snippet:", snippet[:800])
    page.close()


def capture_hcad_pdata(p):
    print("\n=== HCAD pdata download (local Playwright) ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(accept_downloads=True)
    page = ctx.new_page()
    # the REAL download grid (DataTables-rendered) lives here:
    page.goto("https://hcad.org/pdata/pdata-property-downloads.html",
              wait_until="networkidle", timeout=60000)
    # wait for the DataTables download buttons to render (JS/AJAX)
    try:
        page.wait_for_selector("a:has-text('Real')", timeout=20000)
    except Exception as e:
        print(f"[hcad] no 'Real' link within 20s: {e}")
    page.wait_for_timeout(5000)
    dl_info = {}
    page.on("download", lambda d: dl_info.update(
        url=d.url, suggested_filename=d.suggested_filename))
    # click the first download control that names a real-property file
    clicked = False
    for label in ("Real Account", "real_acct", "Account", "real", "Download"):
        try:
            page.click(f"a:has-text('{label}')", timeout=4000)
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        # fall back: any <a download> or button
        try:
            page.click("a[download], button:has-text('Download')", timeout=4000)
            clicked = True
        except Exception:
            pass
    page.wait_for_timeout(8000)
    print(f"[hcad] clicked={clicked} download event: {dl_info}")
    if dl_info.get("url"):
        print(f"[hcad] REAL FILE URL: {dl_info['url']}")
        OUT.joinpath("hcad_pdata_url.txt").write_text(dl_info["url"])
    else:
        # dump the rendered download-control hrefs so we can see the real pattern
        import re
        html = page.content()
        links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I)
        rel = [(h, re.sub(r"<[^>]+>", "", t).strip())
                for h, t in links
                if any(k in (h + t).lower() for k in
                    ("real", "account", "download", ".txt", ".zip", "property"))]
        print(f"[hcad] rendered download controls ({len(rel)}):")
        for h, t in rel[:15]:
            print(f"   {t!r} -> {h}")
    browser.close()


def main():
    with sync_playwright() as p:
        p.chromium.launch(headless=True)
        capture_clerk(p)
        capture_hcad_pdata(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

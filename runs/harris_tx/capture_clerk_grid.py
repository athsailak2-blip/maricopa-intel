#!/usr/bin/env python3
"""Clerk live result-grid capture. Try full postback + async delta, save raw
responses, print diagnostics so we can parse the REAL column order."""
import re, sys
from pathlib import Path
import requests

BASE = "https://www.cclerk.hctx.net/applications/websearch/RP.aspx"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def _f(html, name):
    m = re.search(r'name="%s"[^>]*?value="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else ""


def diag(label, txt):
    tbls = re.findall(r"<table[^>]*>.*?</table>", txt, re.S | re.I)
    print(f"[{label}] len={len(txt)} pipes={txt.count('|')} "
          f"has_updatePanel={'|updatePanel|' in txt} tables={len(tbls)}")
    for kw in ("No records", "no record", "LIS PENDENS", "Instrument",
               "Grantor", "Grantee", "Record Date", "Document"):
        if kw.lower() in txt.lower():
            print(f"   marker: {kw}")


def main():
    s = requests.Session(); s.headers.update(H)
    r0 = s.get(BASE, timeout=30)
    vs, ev = _f(r0.text, "__VIEWSTATE"), _f(r0.text, "__EVENTVALIDATION")
    print(f"[clerk] GET {r0.status_code} VS={len(vs)} EV={len(ev)}")

    # Strategy A: full postback (button in data, EVENTTARGET empty), broad date range
    dataA = {
        "__VIEWSTATE": vs, "__EVENTVALIDATION": ev,
        "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        "ctl00$ContentPlaceHolder1$txtFrom": "01/01/2026",
        "ctl00$ContentPlaceHolder1$txtTo": "06/30/2026",
        "ctl00$ContentPlaceHolder1$txtInstrument": "",
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
    }
    rA = s.post(BASE, data=dataA, timeout=30)
    Path("/tmp/clerk_A.html").write_text(rA.text)
    diag("A", rA.text)

    # Strategy B: async delta (EVENTTARGET=btnSearch, AJAX header)
    r0b = s.get(BASE, timeout=30)
    vs2, ev2 = _f(r0b.text, "__VIEWSTATE"), _f(r0b.text, "__EVENTVALIDATION")
    dataB = {
        "__VIEWSTATE": vs2, "__EVENTVALIDATION": ev2,
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnSearch",
        "__EVENTARGUMENT": "",
        "ctl00$ContentPlaceHolder1$txtFrom": "01/01/2026",
        "ctl00$ContentPlaceHolder1$txtTo": "06/30/2026",
        "ctl00$ContentPlaceHolder1$txtInstrument": "",
    }
    hB = dict(H); hB["X-MicrosoftAjax"] = "Delta=true"
    rB = s.post(BASE, data=dataB, headers=hB, timeout=30)
    Path("/tmp/clerk_B.html").write_text(rB.text)
    diag("B", rB.text)

    # If delta, extract updatePanel content and look for tables there
    for lab, t in (("A", rA.text), ("B", rB.text)):
        if "|updatePanel|" in t:
            # segment after 'updatePanel|<panelid>|' up to next '|<num>|'
            m = re.search(r"updatePanel\|[^|]*\|(.*?)(?=\|\d+\||$)", t, re.S)
            seg = m.group(1) if m else ""
            tbls = re.findall(r"<table[^>]*>.*?</table>", seg, re.S | re.I)
            print(f"[{lab}] delta updatePanel tables={len(tbls)} seglen={len(seg)}")
            if tbls:
                rows = re.findall(r"<tr[^>]*>(.*?)</tr>", max(tbls, key=len), re.S | re.I)
                print(f"[{lab}] rows(incl header)={len(rows)}")
                for i, tr in enumerate(rows[:4]):
                    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
                    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                    print(f"   {lab} row{i}:", cells)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

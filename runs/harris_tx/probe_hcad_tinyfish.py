#!/usr/bin/env python3
"""Phase 2 verification probe: use TinyFish stealth browser (repo cost-gated
escalation for Cloudflare-blocked HCAD) to see if search.hcad.org clears the
challenge. Reports page state honestly. No data fabricated."""
import sys, time, json
sys.path.insert(0, "/root/.hermes/profiles/harris/skills/web-scraping/tinyfish-remote-browser/references")
from tinyfish_browser import create_session, destroy_session

TARGET = "https://search.hcad.org/"
sid = cdp = None
try:
    sid, cdp = create_session(TARGET, timeout_seconds=240)
    print(f"[tinyfish] session {sid} created")
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(TARGET, wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)  # let Cloudflare/JS settle
    title = page.title()
    txt = page.content()
    print(f"[tinyfish] page title: {title!r}")
    lowered = txt.lower()
    cf = ("verify you are human" in lowered) or ("just a moment" in lowered) or ("challenge" in lowered and "cloudflare" in lowered)
    print(f"[tinyfish] cloudflare_challenge_present: {cf}")
    print(f"[tinyfish] page bytes: {len(txt)}")
    # Show a snippet of what we actually got
    snippet = txt[:600].replace("\n", " ")
    print(f"[tinyfish] snippet: {snippet}")
    if not cf:
        print("[tinyfish] CHALLENGE CLEARED — HCAD reachable via TinyFish")
    else:
        print("[tinyfish] still challenged — TinyFish IP also hit Cloudflare")
finally:
    if sid:
        destroy_session(sid)
        print(f"[tinyfish] session {sid} destroyed")

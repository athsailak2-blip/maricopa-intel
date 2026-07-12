# Harris County, TX — Documented API Discovery Report

Generated per knowledge_base/protocols/01_county_recon.md §01.12 + §16 matrix companion.
Records the API-discovery search log and findings. No live REST/GraphQL API was found for the
primary sources; all are ASP.NET postback portals or bulk-file downloads (scraped via local
Playwright / direct download, per framework blocker-resolver order).

## searched
    - https://www.cclerk.hctx.net/applications/websearch/RP.aspx (View Source / Network tab)
    - https://www.hcdistrictclerk.com/eDocs/Public/Search.aspx (Network tab)
    - https://hcad.org/pdata/pdata-property-downloads.html (download flow)
    - https://www.hctax.net/Property/TaxSales/Index (network tab)
    - https://api.hcad.org / https://api.harriscountytx.gov (probed — not authoritative)

## found
    (none — no public REST/GraphQL contract documented for these county portals)

## discovered_apis
    - kind: bulk_file (not a live API)
      api_url: https://hcad.org/pdata/.../Real_acct_owner.zip
      api_type: Other (static bulk download behind JS/DataTables flow)
      auth_required: false
      rate_limited: false
      source_role: ENRICHMENT_SOURCE
      notes: Real file URL is client-side generated (page.on("download") -> d.url). Static
             pdata.hcad.org/Records/* probes 404/redirect. Download host has NO Cloudflare.
    - kind: postback_portal (not a live API)
      api_url: https://www.cclerk.hctx.net/applications/websearch/RP.aspx
      api_type: Other (ASP.NET __doPostBack; UpdatePanel async delta)
      auth_required: false
      source_role: PRIMARY_LEAD_SOURCE
      notes: Driven by local Playwright (fill -> click -> wait_for_selector). Managed browser
             tool + raw requests POST fail to render the grid.

## search_notes
    No authoritative programmatic API exists for Harris County primary lead sources. The
    framework's blocker-resolver order (use_playwright → use_session_cookie → ...) applies;
    local Playwright + official bulk download are the verified free paths. TinyFish / stealth
    browser NOT needed (Cloudflare holds only HCAD's search host, not the download host).

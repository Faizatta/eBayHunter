# ─────────────────────────────────────────────────────────────────
# FIX 1 — Sold filter MANDATORY in URL (always pre-applied)
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(keyword: str, base_url: str) -> str:
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html?_nkw={q}"
        f"&LH_Sold=1"           # ← SOLD items only
        f"&LH_Complete=1"       # ← completed listings only
        f"&LH_BIN=1"
        f"&LH_PrefLoc=1"
        f"&LH_ItemCondition=1000"
        f"&_sop=10"             # sort: most recently sold first
        f"&_ipg={ITEMS_PER_PAGE}"
        f"&_stpos=0"            # ← force page 1 / fresh results each call
        f"&_sacat=0"
        f"&rt=nc"               # ← bypass eBay result caching
    )


# ─────────────────────────────────────────────────────────────────
# FIX 2 — Clear cache + add random nonce so eBay never serves
#          a cached/stale results page
# ─────────────────────────────────────────────────────────────────

import time, random

def build_ebay_sold_url(keyword: str, base_url: str) -> str:
    q     = quote_plus(keyword)
    nonce = f"{int(time.time())}_{random.randint(1000, 9999)}"  # unique per call
    return (
        f"{base_url}/sch/i.html?_nkw={q}"
        f"&LH_Sold=1&LH_Complete=1"
        f"&LH_BIN=1&LH_PrefLoc=1&LH_ItemCondition=1000"
        f"&_sop=10&_ipg={ITEMS_PER_PAGE}"
        f"&_stpos=0&_sacat=0&rt=nc"
        f"&_rdc={nonce}"        # ← busts any eBay-side result cache
    )


# ─────────────────────────────────────────────────────────────────
# FIX 3 — After page loads, HARD-VERIFY sold filter is active.
#          If eBay redirected and stripped it, reload immediately.
# ─────────────────────────────────────────────────────────────────

    await page.goto(url, wait_until="networkidle", timeout=40000)

    if "LH_Sold=1" not in page.url:
        print("[BOT] Sold filter lost — forcing reload", file=sys.stderr)
        await page.goto(url, wait_until="networkidle", timeout=40000)
        await asyncio.sleep(1.5)

    html = await page.content()

    # Final guard — if rendered HTML has no sold listings, reject entirely
    if not re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE):
        print("[BOT] REJECT — page has no sold listings", file=sys.stderr)
        return ""

    return html

# ─────────────────────────────────────────────────────────────────
# 1. URL BUILDER — sold filter always baked in
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(keyword: str, base_url: str) -> str:
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1&LH_Complete=1"   # ← sold filter pre-applied
        f"&LH_PrefLoc=1&_sop=10&LH_BIN=1&LH_ItemCondition=1000"
        f"&_ipg={ITEMS_PER_PAGE}"
    )


# ─────────────────────────────────────────────────────────────────
# 2. AFTER PAGE LOAD — verify filter wasn't stripped by a redirect
# ─────────────────────────────────────────────────────────────────

async def fetch_page_with_retry(playwright, url, country_cfg, max_retries=3):
    # ... proxy / browser setup omitted for brevity ...

    await page.goto(url, wait_until="networkidle", timeout=40000)
    await asyncio.sleep(random.uniform(1.5, 3.0))

    current_url = page.url
    if "LH_Sold=1" not in current_url and "LH_Complete=1" not in current_url:
        # eBay redirected and dropped the filter — reload with it forced back in
        print("[BOT]   Sold filter lost after redirect — reloading", file=sys.stderr)
        await page.goto(url, wait_until="networkidle", timeout=40000)
        await asyncio.sleep(2.0)

    html = await page.content()
    return html


# ─────────────────────────────────────────────────────────────────
# 3. PARSER — reject page if sold word not found in rendered HTML
# ─────────────────────────────────────────────────────────────────

def parse_sold_from_html(html: str) -> dict:
    if not re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE):
        return {"reject_reason": "sold filter not applied — page did not render sold listings"}

    # ... rest of parsing continues normally ...

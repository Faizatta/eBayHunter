import time
import random
import asyncio
import re
import sys
from urllib.parse import quote_plus, urlencode, urlparse, urlunparse, parse_qs

# ─────────────────────────────────────────────────────────────────
# COUNTRY CONFIG — each country has its own eBay domain
# ─────────────────────────────────────────────────────────────────

EBAY_PLATFORMS = {
    "UK":        { "name": "UK",        "url": "https://www.ebay.co.uk",  "currency": "GBP", "locale": "en-GB", "country_code": "GB", "timezone": "Europe/London",    "ali_ship_param": "GB" },
    "DE":        { "name": "Germany",   "url": "https://www.ebay.de",     "currency": "EUR", "locale": "de-DE", "country_code": "DE", "timezone": "Europe/Berlin",    "ali_ship_param": "DE" },
    "IT":        { "name": "Italy",     "url": "https://www.ebay.it",     "currency": "EUR", "locale": "it-IT", "country_code": "IT", "timezone": "Europe/Rome",      "ali_ship_param": "IT" },
    "AU":        { "name": "Australia", "url": "https://www.ebay.com.au", "currency": "AUD", "locale": "en-AU", "country_code": "AU", "timezone": "Australia/Sydney", "ali_ship_param": "AU" },
}


# ─────────────────────────────────────────────────────────────────
# STEP 1 — Build URL with sold filter baked in for the right country
# ─────────────────────────────────────────────────────────────────

def build_sold_url(keyword: str, base_url: str) -> str:
    """
    Builds a country-correct eBay sold-items URL.
    LH_Sold=1 + LH_Complete=1 are mandatory — sold filter pre-applied.
    _rdc nonce busts caching so every search returns fresh results.
    """
    nonce = f"{int(time.time())}_{random.randint(100, 999)}"
    params = {
        "_nkw":             keyword,
        "LH_Sold":          "1",        # ← SOLD items only
        "LH_Complete":      "1",        # ← completed listings only
        "LH_BIN":           "1",        # buy it now
        "LH_ItemCondition": "1000",     # new items
        "LH_PrefLoc":       "1",        # prefer local country
        "_sop":             "10",       # sort: most recently sold first
        "_ipg":             "60",       # 60 results per page
        "rt":               "nc",       # no result caching
        "_rdc":             nonce,      # unique per call = fresh results
    }
    return f"{base_url}/sch/i.html?{urlencode(params)}"


# ─────────────────────────────────────────────────────────────────
# STEP 2 — After page loads, verify + force the sold filter
# ─────────────────────────────────────────────────────────────────

async def enforce_sold_filter(page, base_url: str, keyword: str) -> bool:
    """
    Checks if 'Sold items' pill/filter is active on the page.
    If not, navigates directly to the correct sold URL for this country.
    Returns True only when sold listings are confirmed on the page.
    """
    await asyncio.sleep(2.0)

    # Check 1 — is the sold pill visible in the DOM?
    pill_found = await page.evaluate("""
        () => {
            const els = Array.from(document.querySelectorAll('*'));
            return els.some(el =>
                el.children.length <= 3 &&
                el.textContent.trim().toLowerCase().includes('sold items')
            );
        }
    """)

    if pill_found:
        print(f"[BOT]   ✅ Sold items pill found on page", file=sys.stderr)
        return True

    # Pill missing — force navigate to correct country sold URL
    print(f"[BOT]   ⚠️  Sold filter missing — forcing to {base_url}", file=sys.stderr)
    sold_url = build_sold_url(keyword, base_url)
    await page.goto(sold_url, wait_until="networkidle", timeout=40000)
    await asyncio.sleep(2.0)

    # Check 2 — verify pill appeared after reload
    pill_found = await page.evaluate("""
        () => {
            const els = Array.from(document.querySelectorAll('*'));
            return els.some(el =>
                el.children.length <= 3 &&
                el.textContent.trim().toLowerCase().includes('sold items')
            );
        }
    """)

    # Check 3 — fallback: look for green "Sold 5th January 2026" dates in HTML
    if not pill_found:
        html = await page.content()
        pill_found = bool(re.search(
            r"Sold\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}",
            html, re.IGNORECASE
        ))

    if pill_found:
        print(f"[BOT]   ✅ Sold filter confirmed after reload", file=sys.stderr)
    else:
        print(f"[BOT]   ❌ Sold filter could not be applied — skipping", file=sys.stderr)

    return pill_found


# ─────────────────────────────────────────────────────────────────
# STEP 3 — Fetch page: country-matched domain + sold filter enforced
# ─────────────────────────────────────────────────────────────────

async def fetch_sold_page(playwright, keyword: str, country_cfg: dict) -> str:
    """
    Opens the correct country eBay domain, applies sold filter,
    and returns HTML only when sold listings are confirmed.
    """
    base_url = country_cfg["url"]      # e.g. https://www.ebay.de for Germany
    locale   = country_cfg["locale"]   # e.g. de-DE
    tz       = country_cfg["timezone"]
    country  = country_cfg["name"]

    sold_url = build_sold_url(keyword, base_url)
    print(f"[BOT]   Opening {country} → {sold_url[:80]}...", file=sys.stderr)

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    context = await browser.new_context(
        locale=locale,
        timezone_id=tz,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        extra_http_headers={"Accept-Language": f"{locale},en;q=0.8"},
    )

    try:
        page = await context.new_page()

        # Navigate directly to country-correct sold URL
        await page.goto(sold_url, wait_until="networkidle", timeout=40000)

        # Enforce sold filter — will re-navigate if missing
        sold_ok = await enforce_sold_filter(page, base_url, keyword)

        if not sold_ok:
            print(f"[BOT]   SKIP {country} — sold filter could not be confirmed", file=sys.stderr)
            return ""

        html = await page.content()

        # Final guard — page must have actual sold dates
        if not re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE):
            print(f"[BOT]   SKIP {country} — no sold listings in HTML", file=sys.stderr)
            return ""

        print(f"[BOT]   ✅ {country} — sold listings confirmed", file=sys.stderr)
        return html

    finally:
        await context.close()
        await browser.close()


# ─────────────────────────────────────────────────────────────────
# STEP 4 — Run across all 4 countries
# ─────────────────────────────────────────────────────────────────

async def run_search_async(keyword: str) -> list:
    from playwright.async_api import async_playwright

    all_results = []

    async with async_playwright() as pw:
        for key, cfg in EBAY_PLATFORMS.items():
            try:
                html = await fetch_sold_page(pw, keyword, cfg)
                if html:
                    items = parse_items_from_html(html, cfg["name"], cfg["currency"], cfg["url"])
                    all_results.extend(items)
                    print(f"[BOT]   {cfg['name']}: {len(items)} products", file=sys.stderr)
            except Exception as e:
                print(f"[BOT]   {cfg['name']} error: {e}", file=sys.stderr)

    return all_results

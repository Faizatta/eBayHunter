import asyncio
import re
import sys
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# EBAY CONFIG
# ─────────────────────────────────────────────
EBAY_PLATFORMS = {
    "UK": {"name": "UK",        "url": "https://www.ebay.co.uk",  "currency": "GBP", "locale": "en-GB", "timezone": "Europe/London"},
    "DE": {"name": "Germany",   "url": "https://www.ebay.de",     "currency": "EUR", "locale": "de-DE", "timezone": "Europe/Berlin"},
    "IT": {"name": "Italy",     "url": "https://www.ebay.it",     "currency": "EUR", "locale": "it-IT", "timezone": "Europe/Rome"},
    "AU": {"name": "Australia", "url": "https://www.ebay.com.au", "currency": "AUD", "locale": "en-AU", "timezone": "Australia/Sydney"},
}

# ─────────────────────────────────────────────
# BUILD SOLD URL
# ─────────────────────────────────────────────
def build_sold_url(keyword: str, base_url: str, page: int = 1) -> str:
    params = {
        "_nkw":             keyword,
        "_sop":             "15",
        "LH_BIN":           "1",
        "LH_ItemCondition": "1000",
        "rt":               "nc",
        "LH_Sold":          "1",
        "LH_Complete":      "1",
        "_pgn":             page,
        "_ipg":             "60",
    }
    return f"{base_url}/sch/i.html?{urlencode(params)}"

# ─────────────────────────────────────────────
# FORCE SOLD PARAMS INTO ANY URL
# ─────────────────────────────────────────────
def ensure_sold_params(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    params["LH_Sold"]          = ["1"]
    params["LH_Complete"]      = ["1"]
    params["LH_BIN"]           = ["1"]
    params["LH_ItemCondition"] = ["1000"]
    params["rt"]               = ["nc"]

    flat      = {k: v[0] for k, v in params.items()}
    new_query = urlencode(flat)

    fixed = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    print(f"[BOT] 🔧 Fixed URL: {fixed[:100]}", file=sys.stderr)
    return fixed

# ─────────────────────────────────────────────
# PRICE EXTRACTOR
# ─────────────────────────────────────────────
def extract_price(text: str):
    match = re.search(r"[\d]+[.,]?\d*", text.replace(",", ""))
    return float(match.group().replace(",", ".")) if match else None

# ─────────────────────────────────────────────
# PARSE ITEMS FROM HTML
# ─────────────────────────────────────────────
def parse_items(html: str, country: str, currency: str) -> list:
    soup  = BeautifulSoup(html, "lxml")
    items = []

    for li in soup.select("li.s-item"):
        title_tag = li.select_one("h3.s-item__title")
        price_tag = li.select_one(".s-item__price")
        link_tag  = li.select_one("a.s-item__link")

        if not title_tag or not price_tag:
            continue

        title = title_tag.get_text(strip=True)
        if any(x in title for x in ["Shop on eBay", "Explore related"]):
            continue

        price = extract_price(price_tag.get_text())
        if not price:
            continue

        items.append({
            "country":  country,
            "currency": currency,
            "title":    title,
            "price":    price,
            "link":     link_tag["href"] if link_tag else "",
        })

    return items

# ─────────────────────────────────────────────
# FETCH ONE COUNTRY — 4 STRICT GATES
# ─────────────────────────────────────────────
async def fetch_country(pw, keyword: str, cfg: dict, pages: int = 2) -> list:
    base_url   = cfg["url"]
    country    = cfg["name"]
    all_items  = []

    browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    context = await browser.new_context(
        locale=cfg["locale"],
        timezone_id=cfg["timezone"],
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        extra_http_headers={"Accept-Language": f"{cfg['locale']},en;q=0.8"},
    )

    page = await context.new_page()

    # ── GATE 1: Intercept redirects that strip sold filter ───────────
    async def block_filter_strip(route, request):
        url = request.url
        if "ebay" in url and "sch/i.html" in url:
            if "LH_Sold=1" not in url or "LH_Complete=1" not in url:
                print(f"[BOT] ⛔ Blocked redirect stripping sold filter: {url[:80]}", file=sys.stderr)
                fixed_url = ensure_sold_params(url)
                await route.continue_(url=fixed_url)
                return
        await route.continue_()

    await page.route("**/*", block_filter_strip)

    try:
        for p in range(1, pages + 1):
            url = build_sold_url(keyword, base_url, page=p)
            print(f"\n[BOT] {country} p{p} → {url}", file=sys.stderr)

            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(2)

            # ── GATE 2: Check current URL still has sold params ──────────
            current_url = page.url
            if "LH_Sold=1" not in current_url or "LH_Complete=1" not in current_url:
                print(f"[BOT] ⚠️  URL lost sold params — forcing fix...", file=sys.stderr)
                fixed = ensure_sold_params(current_url)
                await page.goto(fixed, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(2)

            # ── GATE 3: Verify final URL is correct ──────────────────────
            final_url = page.url
            if "LH_Sold=1" not in final_url:
                print(f"[BOT] ❌ {country} p{p} — sold filter STILL missing, skipping page", file=sys.stderr)
                continue

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            html = await page.content()

            # ── GATE 4: Verify sold content exists in HTML ───────────────
            if not re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE):
                print(f"[BOT] ❌ {country} p{p} — no sold dates found in HTML, skipping page", file=sys.stderr)
                continue

            print(f"[BOT] ✅ {country} p{p} — all 4 gates passed", file=sys.stderr)

            items = parse_items(html, country, cfg["currency"])
            print(f"[BOT] ✅ {country} p{p} → {len(items)} items parsed", file=sys.stderr)
            all_items.extend(items)

    finally:
        await context.close()
        await browser.close()

    return all_items

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
async def run(keyword: str, pages: int = 2):
    async with async_playwright() as pw:
        tasks   = [fetch_country(pw, keyword, cfg, pages) for cfg in EBAY_PLATFORMS.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for r in results:
        if isinstance(r, Exception):
            print(f"[BOT] Error: {r}", file=sys.stderr)
        else:
            final.extend(r)

    return final

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    keyword = "gym Commercial"

    results = asyncio.run(run(keyword, pages=2))

    print(f"\n===== RESULTS ({len(results)} total) =====\n")
    for r in results[:20]:
        print(f"[{r['country']}] {r['title'][:60]}")
        print(f"  Price : {r['currency']} {r['price']}")
        print(f"  Link  : {r['link'][:80]}")
        print()

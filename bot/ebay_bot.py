import time
import random
import asyncio
import re
import sys
from urllib.parse import quote_plus, urlencode
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────────────────────────
# COUNTRY CONFIG
# ─────────────────────────────────────────────────────────────────
EBAY_PLATFORMS = {
    "UK": { "name": "UK", "url": "https://www.ebay.co.uk", "currency": "GBP", "locale": "en-GB", "timezone": "Europe/London" },
    "DE": { "name": "Germany", "url": "https://www.ebay.de", "currency": "EUR", "locale": "de-DE", "timezone": "Europe/Berlin" },
    "IT": { "name": "Italy", "url": "https://www.ebay.it", "currency": "EUR", "locale": "it-IT", "timezone": "Europe/Rome" },
    "AU": { "name": "Australia", "url": "https://www.ebay.com.au", "currency": "AUD", "locale": "en-AU", "timezone": "Australia/Sydney" },
}

# ─────────────────────────────────────────────────────────────────
# BUILD SOLD URL
# ─────────────────────────────────────────────────────────────────
def build_sold_url(keyword: str, base_url: str) -> str:
    nonce = f"{int(time.time())}_{random.randint(100,999)}"
    params = {
        "_nkw": quote_plus(keyword),
        "LH_BIN": "1",
        "LH_ItemCondition": "1000",
        "_sop": "13",     # sort by recently sold
        "_ipg": "60",
        "rt": "nc",
        "_rdc": nonce
    }
    return f"{base_url}/sch/i.html?{urlencode(params)}"

# ─────────────────────────────────────────────────────────────────
# FORCE CLICK SOLD FILTER
# ─────────────────────────────────────────────────────────────────
async def force_click_sold_filter(page):
    try:
        print("[BOT] Trying to click SOLD filter...", file=sys.stderr)
        await page.wait_for_selector('input[type="checkbox"]', timeout=10000)

        sold_selectors = [
            'input[aria-label*="Sold"]',
            'input[aria-label*="Verkauft"]',  # German
            'input[value="LH_Sold"]'
        ]

        for selector in sold_selectors:
            checkbox = page.locator(selector)
            if await checkbox.count() > 0:
                await checkbox.first.click()
                await asyncio.sleep(3)
                print("[BOT] ✅ Clicked SOLD filter", file=sys.stderr)
                return True

        print("[BOT] ❌ SOLD checkbox not found", file=sys.stderr)
        return False

    except Exception as e:
        print(f"[BOT] ❌ Click error: {e}", file=sys.stderr)
        return False

# ─────────────────────────────────────────────────────────────────
# VERIFY SOLD LISTINGS
# ─────────────────────────────────────────────────────────────────
async def verify_sold(page) -> bool:
    # Look for SOLD labels directly in listings
    sold_labels = await page.locator('span:has-text("Sold"), span:has-text("Verkauft")').count()

    html = await page.content()
    date_check = bool(re.search(r"Sold\\s+\\d{1,2}", html, re.IGNORECASE))

    print(f"[BOT] Verify → labels:{sold_labels} | dates:{date_check}", file=sys.stderr)
    return sold_labels > 5 or date_check

# ─────────────────────────────────────────────────────────────────
# FETCH SOLD PAGE
# ─────────────────────────────────────────────────────────────────
async def fetch_sold_page(playwright, keyword: str, cfg: dict) -> str:
    base_url = cfg["url"]
    name     = cfg["name"]
    url = build_sold_url(keyword, base_url)

    print(f"[BOT] Opening {name}: {url[:100]}...", file=sys.stderr)

    browser = await playwright.chromium.launch(
        headless=False,  # set to True in production
        args=["--disable-blink-features=AutomationControlled"]
    )

    context = await browser.new_context(
        locale=cfg["locale"],
        timezone_id=cfg["timezone"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    )

    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(2)

        # Click sold filter
        await force_click_sold_filter(page)
        await page.wait_for_load_state("networkidle")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # Verify
        if not await verify_sold(page):
            print(f"[BOT] ❌ {name} — sold not detected", file=sys.stderr)
            return ""

        print(f"[BOT] ✅ {name} — sold confirmed", file=sys.stderr)
        return await page.content()

    except Exception as e:
        print(f"[BOT] ❌ ERROR ({name}): {e}", file=sys.stderr)
        return ""

    finally:
        await context.close()
        await browser.close()

# ─────────────────────────────────────────────────────────────────
# PARSE ITEMS FROM HTML
# ─────────────────────────────────────────────────────────────────
def parse_items_from_html(html: str, country_name: str, currency: str, base_url: str) -> list:
    from bs4 import BeautifulSoup
    items = []
    soup = BeautifulSoup(html, "html.parser")
    listings = soup.select("li.s-item")

    for li in listings:
        title_tag = li.select_one("h3.s-item__title")
        price_tag = li.select_one("span.s-item__price")
        link_tag  = li.select_one("a.s-item__link")
        if not title_tag or not price_tag or not link_tag:
            continue

        title = title_tag.get_text(strip=True)
        price = price_tag.get_text(strip=True)
        link  = link_tag.get("href")

        items.append({
            "country": country_name,
            "title": title,
            "price": price,
            "currency": currency,
            "link": link
        })
    return items

# ─────────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────
async def run_search_async(keyword: str):
    results = []
    async with async_playwright() as pw:
        for key, cfg in EBAY_PLATFORMS.items():
            try:
                html = await fetch_sold_page(pw, keyword, cfg)
                if html:
                    items = parse_items_from_html(html, cfg["name"], cfg["currency"], cfg["url"])
                    results.extend(items)
                    print(f"[BOT] {cfg['name']} → {len(items)} items", file=sys.stderr)
            except Exception as e:
                print(f"[BOT] {cfg['name']} ERROR: {e}", file=sys.stderr)
    return results

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    keyword = "gym Multi-Function"
    all_results = asyncio.run(run_search_async(keyword))
    print(f"\nTOTAL ITEMS FOUND: {len(all_results)}")
    for item in all_results:
        print(item)

import time
import random
import asyncio
import re
import sys
from urllib.parse import quote_plus, urlencode


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
# BUILD SOLD URL (MAIN FIX)
# ─────────────────────────────────────────────────────────────────

def build_sold_url(keyword: str, base_url: str) -> str:
    nonce = f"{int(time.time())}_{random.randint(100,999)}"

    params = {
        "_nkw": quote_plus(keyword),
        "LH_Sold": "1",
        "LH_Complete": "1",
        "LH_BIN": "1",
        "LH_ItemCondition": "1000",
        "LH_PrefLoc": "1",
        "_sop": "13",     # MOST IMPORTANT (recently sold)
        "_ipg": "60",
        "rt": "nc",
        "_rdc": nonce
    }

    return f"{base_url}/sch/i.html?{urlencode(params)}"


# ─────────────────────────────────────────────────────────────────
# VERIFY SOLD LISTINGS (FIXED)
# ─────────────────────────────────────────────────────────────────

async def verify_sold(page) -> bool:

    text_check = await page.evaluate("""
        () => {
            const text = document.body.innerText.toLowerCase();
            return text.includes('items sold') || text.includes('sold ');
        }
    """)

    html = await page.content()

    date_check = bool(re.search(
        r"Sold\\s+\\d{1,2}(?:st|nd|rd|th)?\\s+\\w+\\s+\\d{4}",
        html,
        re.IGNORECASE
    ))

    print(f"[BOT] Verify → text:{text_check} | dates:{date_check}", file=sys.stderr)

    return text_check or date_check


# ─────────────────────────────────────────────────────────────────
# FETCH SOLD PAGE
# ─────────────────────────────────────────────────────────────────

async def fetch_sold_page(playwright, keyword: str, cfg: dict) -> str:

    base_url = cfg["url"]
    name     = cfg["name"]

    url = build_sold_url(keyword, base_url)

    print(f"[BOT] Opening {name}: {url[:100]}...", file=sys.stderr)

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )

    context = await browser.new_context(
        locale=cfg["locale"],
        timezone_id=cfg["timezone"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    )

    try:
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=40000)

        # Scroll for lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # VERIFY
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
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────

async def run_search_async(keyword: str):

    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as pw:
        for key, cfg in EBAY_PLATFORMS.items():
            try:
                html = await fetch_sold_page(pw, keyword, cfg)

                if html:
                    items = parse_items_from_html(
                        html,
                        cfg["name"],
                        cfg["currency"],
                        cfg["url"]
                    )
                    results.extend(items)

                    print(f"[BOT] {cfg['name']} → {len(items)} items", file=sys.stderr)

            except Exception as e:
                print(f"[BOT] {cfg['name']} ERROR: {e}", file=sys.stderr)

    return results

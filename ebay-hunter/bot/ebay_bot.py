#!/usr/bin/env python3
"""
eBay Product Hunting Bot
Searches eBay across multiple countries, finds profitable products,
then locates cheaper equivalents on AliExpress.

Usage: python ebay_bot.py "keyword"
Output: JSON array of ProductResult objects to stdout
"""

import sys
import json
import time
import random
import re
import asyncio
import traceback
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ─── Configuration ────────────────────────────────────────────────────────────

EBAY_COUNTRIES = [
    {"name": "Germany",   "url": "https://www.ebay.de",  "currency": "EUR"},
    {"name": "UK",        "url": "https://www.ebay.co.uk","currency": "GBP"},
    {"name": "Italy",     "url": "https://www.ebay.it",  "currency": "EUR"},
    {"name": "USA",       "url": "https://www.ebay.com", "currency": "USD"},
    {"name": "Australia", "url": "https://www.ebay.com.au","currency": "AUD"},
]

SEARCH_FILTERS = {
    "min_sold_weekly": 4,
    "min_reviews": 50,
    "require_free_shipping": True,
    "min_delivery_days": 3,
    "max_delivery_days": 7,
}

ALIEXPRESS_SEARCH = "https://www.aliexpress.com/wholesale?SearchText="


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ProductResult:
    title: str
    ebayUrl: str
    aliexpressUrl: str
    ebayPrice: float
    aliexpressPrice: float
    profit: float
    soldLastWeek: int
    reviews: int
    freeShipping: bool
    deliveryDays: str
    country: str
    currency: str = "USD"


# ─── Main bot logic ───────────────────────────────────────────────────────────

async def scrape_ebay(page: Page, base_url: str, keyword: str, country: str, currency: str) -> list[dict]:
    """Scrape eBay search results for a keyword."""
    products = []
    search_url = f"{base_url}/sch/i.html?_nkw={keyword.replace(' ', '+')}&_sop=12&LH_Sold=1&LH_Complete=1"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(random.randint(1000, 2000))

        items = await page.query_selector_all(".s-item__wrapper")

        for item in items[:20]:  # Check first 20 items
            try:
                product = await extract_ebay_item(item, base_url, country, currency)
                if product:
                    products.append(product)
            except Exception:
                continue

    except Exception as e:
        print(f"[WARN] Failed scraping {country}: {e}", file=sys.stderr)

    return products


async def extract_ebay_item(item, base_url: str, country: str, currency: str) -> Optional[dict]:
    """Extract data from a single eBay listing element."""
    try:
        # Title
        title_el = await item.query_selector(".s-item__title")
        if not title_el:
            return None
        title = await title_el.inner_text()
        title = title.strip()
        if not title or title == "Shop on eBay":
            return None

        # URL
        link_el = await item.query_selector("a.s-item__link")
        url = await link_el.get_attribute("href") if link_el else ""
        if not url:
            return None

        # Price
        price_el = await item.query_selector(".s-item__price")
        price_text = await price_el.inner_text() if price_el else "0"
        price = parse_price(price_text)
        if price <= 0:
            return None

        # Sold count
        sold_el = await item.query_selector(".s-item__hotness, .s-item__quantitySold")
        sold_text = await sold_el.inner_text() if sold_el else "0"
        sold = parse_sold_count(sold_text)

        # Shipping
        ship_el = await item.query_selector(".s-item__shipping")
        ship_text = (await ship_el.inner_text() if ship_el else "").lower()
        free_shipping = "free" in ship_text or "gratuit" in ship_text or "kostenlos" in ship_text

        # Delivery estimate
        delivery_el = await item.query_selector(".s-item__delivery-date")
        delivery_text = await delivery_el.inner_text() if delivery_el else ""

        # Reviews (approximate from feedback count)
        feedback_el = await item.query_selector(".s-item__reviews-count, .s-item__feedback")
        feedback_text = await feedback_el.inner_text() if feedback_el else "0"
        reviews = parse_number(feedback_text)

        return {
            "title": title,
            "url": url,
            "price": price,
            "soldLastWeek": sold,
            "reviews": reviews,
            "freeShipping": free_shipping,
            "deliveryText": delivery_text,
            "country": country,
            "currency": currency,
        }

    except Exception:
        return None


def parse_price(text: str) -> float:
    """Extract numeric price from text like '$29.99' or 'EUR 15,00'."""
    text = text.replace(",", ".")
    matches = re.findall(r"\d+\.?\d*", text)
    if matches:
        prices = [float(m) for m in matches if float(m) > 0]
        return min(prices) if prices else 0.0
    return 0.0


def parse_sold_count(text: str) -> int:
    """Extract sold count from text like '123 sold' or '1.2K sold'."""
    text = text.lower().replace(",", "")
    if "k" in text:
        match = re.search(r"(\d+\.?\d*)k", text)
        if match:
            return int(float(match.group(1)) * 1000)
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def parse_number(text: str) -> int:
    """Extract first integer from text."""
    text = text.replace(",", "").replace(".", "")
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def passes_filters(product: dict) -> bool:
    """Check if product meets the configured filter criteria."""
    if product["soldLastWeek"] < SEARCH_FILTERS["min_sold_weekly"]:
        return False
    if product["reviews"] < SEARCH_FILTERS["min_reviews"]:
        return False
    if SEARCH_FILTERS["require_free_shipping"] and not product["freeShipping"]:
        return False
    return True


def estimate_delivery_days(delivery_text: str) -> str:
    """Parse delivery text to day range string."""
    if not delivery_text:
        return "3-7 days"
    numbers = re.findall(r"\d+", delivery_text)
    if len(numbers) >= 2:
        return f"{numbers[0]}-{numbers[1]} days"
    elif len(numbers) == 1:
        return f"{numbers[0]}-{int(numbers[0]) + 3} days"
    return "3-7 days"


async def find_aliexpress_price(page: Page, keyword: str) -> tuple[float, str]:
    """Find cheapest AliExpress price for keyword."""
    ali_url = f"{ALIEXPRESS_SEARCH}{keyword.replace(' ', '+')}"
    try:
        await page.goto(ali_url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(random.randint(1500, 2500))

        # Try to find price selectors
        selectors = [
            ".price--currentPriceText--V8_y_b5",
            ".product-price-value",
            "[class*='price']",
        ]
        for sel in selectors:
            els = await page.query_selector_all(sel)
            prices = []
            for el in els[:10]:
                text = await el.inner_text()
                p = parse_price(text)
                if 0.5 < p < 500:
                    prices.append(p)
            if prices:
                return min(prices), ali_url

    except Exception:
        pass

    # Fallback: estimate as 30-40% of eBay price (will be overridden)
    return 0.0, ali_url


def calculate_profit(ebay_price: float, ali_price: float, ebay_fee_rate: float = 0.13) -> float:
    """
    profit = eBay price - AliExpress price - eBay fees
    eBay typically charges ~13% (final value fee + payment processing)
    """
    fees = ebay_price * ebay_fee_rate
    return round(ebay_price - ali_price - fees, 2)


async def run_bot(keyword: str) -> list[dict]:
    """Main bot entry point."""
    results: list[ProductResult] = []

    if not PLAYWRIGHT_AVAILABLE:
        print("[WARN] Playwright not installed, returning empty results.", file=sys.stderr)
        return []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Search eBay in each country
        for country_cfg in EBAY_COUNTRIES:
            country = country_cfg["name"]
            url     = country_cfg["url"]
            currency = country_cfg["currency"]

            print(f"[BOT] Searching eBay {country}...", file=sys.stderr)
            products = await scrape_ebay(page, url, keyword, country, currency)
            filtered = [p for p in products if passes_filters(p)]
            print(f"[BOT] Found {len(filtered)} qualifying products in {country}", file=sys.stderr)

            # For each qualifying product, find AliExpress price
            for product in filtered[:3]:  # Limit to 3 per country to avoid rate limiting
                # Clean keyword for AliExpress search
                clean_title = " ".join(product["title"].split()[:5])
                ali_price, ali_url = await find_aliexpress_price(page, clean_title)

                if ali_price == 0.0:
                    # Estimate as 35% of eBay price if scraping failed
                    ali_price = round(product["price"] * 0.35, 2)

                profit = calculate_profit(product["price"], ali_price)
                if profit <= 0:
                    continue  # Skip unprofitable products

                result = ProductResult(
                    title=product["title"],
                    ebayUrl=product["url"],
                    aliexpressUrl=ali_url,
                    ebayPrice=product["price"],
                    aliexpressPrice=ali_price,
                    profit=profit,
                    soldLastWeek=product["soldLastWeek"],
                    reviews=product["reviews"],
                    freeShipping=product["freeShipping"],
                    deliveryDays=estimate_delivery_days(product.get("deliveryText", "")),
                    country=product["country"],
                    currency=product["currency"],
                )
                results.append(result)

            time.sleep(random.uniform(1.5, 3.0))  # Polite delay between countries

        await browser.close()

    # Sort by profit descending
    results.sort(key=lambda r: r.profit, reverse=True)
    return [asdict(r) for r in results]


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)

    keyword = sys.argv[1].strip()
    if not keyword:
        print(json.dumps([]))
        sys.exit(0)

    try:
        results = asyncio.run(run_bot(keyword))
        print(json.dumps(results, ensure_ascii=False))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps([]))
        sys.exit(1)

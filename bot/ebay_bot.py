import asyncio
import httpx
import re
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# EBAY CONFIG
# ─────────────────────────────────────────────
EBAY_BASE_URLS = {
    "IT": "https://www.ebay.it",
    "DE": "https://www.ebay.de",
    "UK": "https://www.ebay.co.uk",
    "AU": "https://www.ebay.com.au",
}

# ─────────────────────────────────────────────
# BUILD FILTERED EBAY URL (Sold, BIN, New)
# ─────────────────────────────────────────────
def build_ebay_url(keyword: str, country_code: str = "IT") -> str:
    base_url = EBAY_BASE_URLS.get(country_code.upper(), EBAY_BASE_URLS["IT"])
    params = {
        "_nkw": quote_plus(keyword),        # keyword
        "_sop": "3",                        # sort by newly listed
        "LH_BIN": "1",                      # Buy It Now
        "LH_ItemCondition": "1000",         # New
        "rt": "nc",                         # search type
        "LH_Sold": "1"                      # Sold items only
    }
    return f"{base_url}/sch/i.html?{urlencode(params)}"

# ─────────────────────────────────────────────
# EXTRACT PRICE FROM STRING
# ─────────────────────────────────────────────
def extract_price(text: str):
    match = re.search(r"(\d+[.,]?\d*)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None

# ─────────────────────────────────────────────
# PARSE EBAY HTML
# ─────────────────────────────────────────────
def parse_ebay(html: str):
    soup = BeautifulSoup(html, "lxml")
    items = []

    for li in soup.select("li.s-item"):
        title_tag = li.select_one("h3.s-item__title")
        price_tag = li.select_one(".s-item__price")
        link_tag  = li.select_one("a.s-item__link")

        if not title_tag or not price_tag:
            continue

        price = extract_price(price_tag.get_text())
        if not price:
            continue

        items.append({
            "title": title_tag.get_text(strip=True),
            "ebay_price": price,
            "link": link_tag["href"] if link_tag else ""
        })
    return items

# ─────────────────────────────────────────────
# FETCH ALIEXPRESS PRICE (CHEAPEST)
# ─────────────────────────────────────────────
async def fetch_aliexpress_price(keyword: str):
    url = f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(keyword)}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        html = r.text

    soup = BeautifulSoup(html, "lxml")
    prices = []
    for p in soup.select(".manhattan--price-sale--1CCSZfK"):
        val = extract_price(p.get_text())
        if val:
            prices.append(val)

    return min(prices) if prices else None

# ─────────────────────────────────────────────
# CALCULATE PROFIT & MARGIN
# ─────────────────────────────────────────────
def calculate_profit(ebay_price, ali_price):
    if not ali_price:
        return None, None
    profit = ebay_price - ali_price
    margin = (profit / ali_price) * 100
    return round(profit, 2), round(margin, 2)

# ─────────────────────────────────────────────
# FETCH EBAY PAGE USING PLAYWRIGHT
# ─────────────────────────────────────────────
async def fetch_ebay_page(keyword, country_code="IT"):
    url = build_ebay_url(keyword, country_code)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        # scroll to load lazy items
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        html = await page.content()
        await browser.close()
    return html

# ─────────────────────────────────────────────
# MAIN BOT
# ─────────────────────────────────────────────
async def run_bot(keyword):
    html = await fetch_ebay_page(keyword)
    ebay_items = parse_ebay(html)
    print(f"[BOT] Found {len(ebay_items)} eBay items")

    results = []
    for item in ebay_items[:10]:  # limit first 10 items
        ali_price = await fetch_aliexpress_price(item["title"])
        profit, margin = calculate_profit(item["ebay_price"], ali_price)
        results.append({
            "title": item["title"],
            "ebay_price": item["ebay_price"],
            "ali_price": ali_price,
            "profit": profit,
            "margin": margin,
            "link": item["link"]
        })
    return results

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    keyword = "gym Mini"
    results = asyncio.run(run_bot(keyword))

    print("\n===== RESULTS =====\n")
    for r in results:
        print(f"""
Title: {r['title']}
eBay: {r['ebay_price']}
AliExpress: {r['ali_price']}
Profit: {r['profit']}
Margin: {r['margin']}%
Link: {r['link']}
--------------------------
""")

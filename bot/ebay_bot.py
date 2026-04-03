import time
import random
import asyncio
import re
import sys
from urllib.parse import quote_plus, urlencode
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import httpx

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
EBAY_PLATFORMS = {
    "DE": { "name": "Germany", "url": "https://www.ebay.de", "currency": "EUR" },
}

# ─────────────────────────────────────────────
# BUILD EBAY URL
# ─────────────────────────────────────────────
def build_url(keyword, base_url):
    params = {
        "_nkw": keyword,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "LH_BIN": "1",
        "_sop": "13"
    }
    return f"{base_url}/sch/i.html?{urlencode(params)}"

# ─────────────────────────────────────────────
# FETCH EBAY
# ─────────────────────────────────────────────
async def fetch_ebay(page, keyword, base_url):
    url = build_url(keyword, base_url)

    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # scroll
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

    return await page.content()

# ─────────────────────────────────────────────
# PARSE EBAY
# ─────────────────────────────────────────────
def parse_ebay(html):
    soup = BeautifulSoup(html, "lxml")
    items = []

    for li in soup.select("li.s-item"):
        title = li.select_one("h3.s-item__title")
        price = li.select_one(".s-item__price")
        link  = li.select_one("a.s-item__link")

        if not title or not price:
            continue

        price_text = price.get_text()
        price_val = extract_price(price_text)

        if not price_val:
            continue

        items.append({
            "title": title.get_text(strip=True),
            "price": price_val,
            "link": link["href"] if link else ""
        })

    return items

# ─────────────────────────────────────────────
# EXTRACT PRICE
# ─────────────────────────────────────────────
def extract_price(text):
    match = re.search(r"(\d+[.,]?\d*)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None

# ─────────────────────────────────────────────
# FETCH ALIEXPRESS (FAST API METHOD)
# ─────────────────────────────────────────────
async def fetch_aliexpress_price(keyword):
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

    if not prices:
        return None

    return min(prices)  # cheapest

# ─────────────────────────────────────────────
# CALCULATE PROFIT
# ─────────────────────────────────────────────
def calculate_profit(ebay_price, ali_price):
    if not ali_price:
        return None, None

    profit = ebay_price - ali_price
    margin = (profit / ali_price) * 100

    return round(profit, 2), round(margin, 2)

# ─────────────────────────────────────────────
# MAIN BOT
# ─────────────────────────────────────────────
async def run_bot(keyword):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()

        html = await fetch_ebay(page, keyword, EBAY_PLATFORMS["DE"]["url"])
        ebay_items = parse_ebay(html)

        print(f"[BOT] Found {len(ebay_items)} eBay items")

        results = []

        for item in ebay_items[:10]:  # limit for speed
            ali_price = await fetch_aliexpress_price(item["title"])

            profit, margin = calculate_profit(item["price"], ali_price)

            results.append({
                "title": item["title"],
                "ebay_price": item["price"],
                "ali_price": ali_price,
                "profit": profit,
                "margin": margin,
                "link": item["link"]
            })

        await browser.close()
        return results

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    keyword = "gym multi function"
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

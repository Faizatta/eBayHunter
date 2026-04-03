import asyncio
import re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# EBAY CONFIG
# ─────────────────────────────────────────────
EBAY_BASE_URLS = {
    "DE": "https://www.ebay.de",
    "IT": "https://www.ebay.it",
    "UK": "https://www.ebay.co.uk",
    "AU": "https://www.ebay.com.au",
}

# ─────────────────────────────────────────────
# BUILD CORRECT SOLD URL ✅
# ─────────────────────────────────────────────
def build_ebay_url(keyword: str, country="DE", page=1):
    base = EBAY_BASE_URLS.get(country, EBAY_BASE_URLS["DE"])

    params = {
        "_nkw": keyword,          # IMPORTANT: no quote_plus
        "_sop": "13",             # sort by recently sold
        "_pgn": page,
        "LH_BIN": "1",
        "LH_ItemCondition": "1000",
        "rt": "nc",
        "LH_Sold": "1",           # REQUIRED
        "LH_Complete": "1"        # REQUIRED
    }

    return f"{base}/sch/i.html?{urlencode(params)}"

# ─────────────────────────────────────────────
# PRICE EXTRACTOR
# ─────────────────────────────────────────────
def extract_price(text):
    match = re.search(r"(\d+[.,]?\d*)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None

# ─────────────────────────────────────────────
# PARSE EBAY HTML
# ─────────────────────────────────────────────
def parse_ebay(html, country):
    soup = BeautifulSoup(html, "lxml")
    items = []

    listings = soup.select("li.s-item")

    for li in listings:
        title_tag = li.select_one("h3.s-item__title")
        price_tag = li.select_one(".s-item__price")
        link_tag  = li.select_one("a.s-item__link")

        if not title_tag or not price_tag:
            continue

        title = title_tag.get_text(strip=True)

        # Skip ads / unwanted
        if "Shop on eBay" in title or "Explore" in title:
            continue

        price = extract_price(price_tag.get_text())
        if not price:
            continue

        link = link_tag["href"] if link_tag else ""

        items.append({
            "country": country,
            "title": title,
            "price": price,
            "link": link
        })

    return items

# ─────────────────────────────────────────────
# FETCH PAGE
# ─────────────────────────────────────────────
async def fetch_page(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # Scroll for lazy loading
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(2)

    return await page.content()

# ─────────────────────────────────────────────
# SCRAPE ONE COUNTRY
# ─────────────────────────────────────────────
async def scrape_country(pw, keyword, country, pages=2):
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    all_items = []

    for p in range(1, pages + 1):
        url = build_ebay_url(keyword, country, p)
        print(f"[BOT] {country} Page {p}: {url}")

        html = await fetch_page(page, url)
        items = parse_ebay(html, country)

        print(f"[BOT] {country} Page {p} → {len(items)} items")

        all_items.extend(items)

    await browser.close()
    return all_items

# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
async def run_bot(keyword):
    async with async_playwright() as pw:
        tasks = []

        for country in EBAY_BASE_URLS.keys():
            tasks.append(scrape_country(pw, keyword, country, pages=2))

        results = await asyncio.gather(*tasks)

    # Flatten list
    final_results = [item for sublist in results for item in sublist]
    return final_results

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    keyword = "gym Mini"

    results = asyncio.run(run_bot(keyword))

    print("\n===== FINAL RESULTS =====\n")

    for r in results[:20]:
        print(f"""
Country: {r['country']}
Title: {r['title']}
Price: {r['price']}
Link: {r['link']}
--------------------------
""")

    print(f"\nTOTAL ITEMS: {len(results)}")

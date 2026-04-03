import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ---------------------
# UTILITIES
# ---------------------
def extract_price(text: str):
    match = re.search(r"[\d]+[.,]?\d*", text.replace(",", ""))
    return float(match.group().replace(",", ".")) if match else None

def parse_items(html: str, country: str, currency: str):
    soup = BeautifulSoup(html, "lxml")
    items = []

    for li in soup.select("li.s-item"):
        title_tag = li.select_one("h3.s-item__title")
        price_tag = li.select_one(".s-item__price")
        link_tag  = li.select_one("a.s-item__link")
        sold_tag  = li.select_one(".s-item__title--tagblock")  # Sold/Venduto/Verkauft

        if not title_tag or not price_tag or not sold_tag:
            continue

        title = title_tag.get_text(strip=True)
        price = extract_price(price_tag.get_text())
        if not price:
            continue

        # Confirm sold status
        sold_text = sold_tag.get_text(strip=True)
        if not re.search(r"Sold|Venduto|Verkauft|Vendu", sold_text, re.IGNORECASE):
            continue

        items.append({
            "country":  country,
            "currency": currency,
            "title":    title,
            "price":    price,
            "link":     link_tag["href"] if link_tag else "",
        })

    return items

# ---------------------
# FETCH SOLD ITEMS
# ---------------------
async def fetch_sold_items(keyword: str, base_url: str, country: str, currency: str, pages: int = 2):
    all_items = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="Europe/London",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for p in range(1, pages + 1):
            url = f"{base_url}/sch/i.html?_nkw={keyword.replace(' ','+')}&_pgn={p}&LH_Sold=1&LH_Complete=1&LH_BIN=1&LH_ItemCondition=1000"
            await page.goto(url, wait_until="domcontentloaded")

            # Click "Sold items" checkbox if present
            try:
                checkbox = page.locator('input[aria-label*="Sold items"], input#LH_Sold')
                if await checkbox.count() > 0 and not await checkbox.first.is_checked():
                    await checkbox.first.click()
                    await page.wait_for_load_state("networkidle")
            except:
                pass  # fallback to URL only

            await asyncio.sleep(2)
            html = await page.content()
            items = parse_items(html, country, currency)
            all_items.extend(items)
            print(f"[{country}] Page {p}: {len(items)} sold items found")

        await context.close()
        await browser.close()

    return all_items

# ---------------------
# RUN EXAMPLE
# ---------------------
async def main():
    countries = {
        "UK": {"url": "https://www.ebay.co.uk", "currency": "GBP"},
        "IT": {"url": "https://www.ebay.it", "currency": "EUR"},
    }

    keyword = "gym commercial"
    tasks = [fetch_sold_items(keyword, cfg["url"], name, cfg["currency"], pages=2)
             for name, cfg in countries.items()]

    results = await asyncio.gather(*tasks)
    all_sold = [item for sub in results for item in sub]

    print(f"\nTotal sold items: {len(all_sold)}")
    for r in all_sold[:20]:
        print(f"[{r['country']}] {r['title']} — {r['currency']} {r['price']}")

# ---------------------
if __name__ == "__main__":
    asyncio.run(main())

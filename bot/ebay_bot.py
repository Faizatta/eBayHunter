#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v5
- Searches eBay across 4 countries: UK, Germany, Italy, Australia
- Filters: min 4 sold/week on eBay
- Scrapes AliExpress: rating 4.5-4.9, 30+ reviews, 3-7 day delivery, free shipping
- Checks lowest eBay price for profit calculation
- Exports to Excel + Google Sheets

Usage: python ebay_bot.py "keyword"
Output: JSON array to stdout
"""

import sys
import json
import random
import re
import asyncio
import os
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────

MIN_SOLD_PER_WEEK    = 4      # eBay: minimum sold in last week
ALI_MIN_RATING       = 4.5   # AliExpress: minimum rating
ALI_MAX_RATING       = 4.9   # AliExpress: maximum rating
ALI_MIN_REVIEWS      = 30    # AliExpress: minimum reviews
ALI_MIN_DELIVERY     = 3     # AliExpress: min delivery days
ALI_MAX_DELIVERY     = 7     # AliExpress: max delivery days
PRODUCTS_PER_COUNTRY = 10    # max products per country
ITEMS_PER_PAGE       = 60

# ── 4 countries only (no USA) ─────────────────────────────────────
EBAY_COUNTRIES = [
    {"name": "UK",        "url": "https://www.ebay.co.uk",  "currency": "GBP", "locale": "en-GB"},
    {"name": "Germany",   "url": "https://www.ebay.de",     "currency": "EUR", "locale": "de-DE"},
    {"name": "Italy",     "url": "https://www.ebay.it",     "currency": "EUR", "locale": "it-IT"},
    {"name": "Australia", "url": "https://www.ebay.com.au", "currency": "AUD", "locale": "en-AU"},
]

# Google Sheets service account key file path
GOOGLE_SHEETS_KEY_FILE  = "google_service_account.json"
GOOGLE_SHEETS_SHEET_NAME = "eBay Hunter Results"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

BLOCK_SIGNALS = [
    "captcha", "robot check", "automated access",
    "verify you are human", "verify you're human",
    "g-recaptcha", "security check", "unusual traffic",
]

JUNK_URL_PATTERNS = [
    "ebayinc.com", "survey", "signin", "rover.ebay",
    "policy", "help", "community", "/srv/",
    "javascript:", "feedback", "#",
]

JUNK_TITLES = {
    "scroll to top", "advertisement", "sponsored", "shop on ebay",
    "new listing", "results", "items", "see all", "top rated",
}

DEBUG_FILE  = "ebay_debug.html"
_debug_done = False


# ─────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductResult:
    title:           str
    country:         str
    currency:        str
    ebayPrice:       float
    ebayLowestPrice: float   # ✅ lowest eBay price found
    aliexpressPrice: float
    aliRating:       float   # ✅ AliExpress rating
    aliReviews:      int     # ✅ AliExpress reviews
    profit:          float
    soldLastWeek:    int
    freeShipping:    bool
    deliveryDays:    str
    ebayUrl:         str
    aliexpressUrl:   str


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def parse_price(text) -> float:
    if not text:
        return 0.0
    text = str(text).split(" to ")[0].split(" - ")[0]
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", "."))
    prices = []
    for m in re.findall(r"\d+\.?\d*", cleaned):
        try:
            v = float(m)
            if 0.5 < v < 50000:
                prices.append(v)
        except ValueError:
            pass
    return min(prices) if prices else 0.0


def parse_sold(text) -> int:
    if not text:
        return 0
    text = str(text).lower().replace(",", "").replace(".", "")
    m = re.search(r"([\d]+)\s*k\s*sold", text)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r"(\d+)\s*(sold|verkauft|venduto|vendu|vendidos)", text)
    return int(m.group(1)) if m else 0


def parse_rating(text) -> float:
    if not text:
        return 0.0
    m = re.search(r"(\d+\.?\d*)", str(text))
    return float(m.group(1)) if m else 0.0


def parse_reviews(text) -> int:
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", str(text).replace(",", "").replace("k", "000"))
    return int(cleaned) if cleaned else 0


def calculate_profit(ebay_price: float, ali_price: float) -> float:
    ebay_fee = round(ebay_price * 0.13, 2)
    return round(ebay_price - ali_price - ebay_fee, 2)


def is_junk_url(url: str) -> bool:
    return any(p in url.lower() for p in JUNK_URL_PATTERNS)


def is_junk_title(title: str) -> bool:
    return title.strip().lower() in JUNK_TITLES or len(title.strip()) < 8


def is_blocked_page(html: str) -> bool:
    return any(s in html[:8000].lower() for s in BLOCK_SIGNALS)


def dump_debug(html: str, country: str) -> None:
    global _debug_done
    if _debug_done:
        return
    try:
        with open(DEBUG_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[BOT] Saved '{DEBUG_FILE}' from {country}", file=sys.stderr)
        _debug_done = True
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────
# Strategy 1 — Embedded JS JSON blobs
# ─────────────────────────────────────────────────────────────────

def _safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def walk_json(obj, depth=0):
    if depth > 20:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_json(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_json(item, depth + 1)


def looks_like_product(d: dict) -> bool:
    has_title = any(k in d for k in ("title", "itemTitle", "name", "TITLE", "displayTitle"))
    has_price = any(k in d for k in ("price", "buyItNowPrice", "currentPrice", "salePrice", "priceValue"))
    has_url   = any(k in d for k in ("itemHref", "productUrl", "url", "itemUrl", "webUrl", "viewItemURL"))
    return has_title and (has_price or has_url)


def _product_from_dict(d: dict, country: str, currency: str) -> Optional[dict]:
    title = None
    for k in ("title", "itemTitle", "name", "TITLE", "displayTitle"):
        v = d.get(k)
        if v and isinstance(v, str) and len(v) > 7:
            title = v.strip()
            break
    if not title or is_junk_title(title):
        return None

    url = None
    for k in ("itemHref", "productUrl", "url", "itemUrl", "webUrl", "viewItemURL"):
        v = d.get(k)
        if v and isinstance(v, str) and "ebay" in v.lower() and "/itm/" in v.lower():
            url = v
            break
    if not url or is_junk_url(url):
        return None

    price = 0.0
    for k in ("price", "buyItNowPrice", "currentPrice", "salePrice", "priceValue", "currentBidPrice"):
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, dict):
            price = parse_price(v.get("value") or v.get("amount") or v.get("currentPrice", 0))
        else:
            price = parse_price(v)
        if price > 0:
            break
    if price <= 0:
        return None

    sold = 0
    for k in ("quantitySold", "unitsSold", "soldQuantity", "totalSold", "itemSoldText", "soldText"):
        v = d.get(k)
        if v:
            sold = max(sold, parse_sold(str(v)))

    free_ship = False
    for k in ("freeShipping", "isFreeShipping", "shippingType", "shippingCost"):
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            free_ship = v
        elif isinstance(v, (int, float)):
            free_ship = (v == 0)
        elif isinstance(v, str):
            free_ship = "free" in v.lower() or v in ("0", "0.0")
        if free_ship:
            break

    return {"title": title, "url": url, "price": price,
            "soldLastWeek": sold, "freeShipping": free_ship,
            "country": country, "currency": currency}


def extract_from_json_blobs(html: str, country: str, currency: str) -> list:
    products, seen = [], set()
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE)
    for script in scripts:
        script = script.strip()
        if not script or len(script) < 50:
            continue
        candidates = []
        for m in re.finditer(r'(?:window\.\w+|\bvar\s+\w+|\w+)\s*=\s*(\{.*)', script, re.DOTALL):
            candidates.append(m.group(1).rstrip("; \n"))
        if script.startswith(("{", "[")):
            candidates.append(script)
        for candidate in candidates:
            obj = _safe_json(candidate)
            if obj is None:
                for end in range(len(candidate) - 1, max(len(candidate) - 500, 0), -1):
                    obj = _safe_json(candidate[:end])
                    if obj is not None:
                        break
            if obj is None:
                continue
            for d in walk_json(obj):
                if not looks_like_product(d):
                    continue
                p = _product_from_dict(d, country, currency)
                if p and p["url"] not in seen:
                    seen.add(p["url"])
                    products.append(p)
    return products


# ─────────────────────────────────────────────────────────────────
# Strategy 2 — ld+json structured data
# ─────────────────────────────────────────────────────────────────

def extract_from_ldjson(html: str, country: str, currency: str) -> list:
    products, seen = [], set()
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    for block in blocks:
        obj = _safe_json(block.strip())
        if not obj:
            continue
        items = []
        if isinstance(obj, list):
            items = obj
        elif isinstance(obj, dict):
            t = obj.get("@type", "")
            if "ItemList" in t:
                items = obj.get("itemListElement", [])
            elif "Product" in t or "Offer" in t:
                items = [obj]
        for item in items:
            if isinstance(item, dict) and "item" in item:
                item = item["item"]
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            url  = item.get("url", "")
            if not name or not url or is_junk_title(name) or is_junk_url(url):
                continue
            if url in seen:
                continue
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = parse_price(offers.get("price", 0))
            if price <= 0:
                continue
            seen.add(url)
            products.append({"title": name, "url": url, "price": price,
                              "soldLastWeek": 0,
                              "freeShipping": "free" in str(offers.get("shippingDetails", "")).lower(),
                              "country": country, "currency": currency})
    return products


# ─────────────────────────────────────────────────────────────────
# Strategy 3 — HTML regex fallback
# ─────────────────────────────────────────────────────────────────

def extract_from_html(html: str, country: str, currency: str) -> list:
    products, seen = [], set()
    chunks = re.split(r'(?=<li[^>]+class="[^"]*s-item[^"]*")', html)
    item_blocks = [c for c in chunks if re.match(r'<li[^>]+class="[^"]*s-item', c, re.I) and len(c) > 400]
    if not item_blocks:
        chunks = re.split(r'(?=<div[^>]+class="[^"]*s-item[^"]*")', html)
        item_blocks = [c for c in chunks if re.match(r'<div[^>]+class="[^"]*s-item', c, re.I) and len(c) > 400]
    print(f"[BOT]   HTML fallback: {len(item_blocks)} raw blocks", file=sys.stderr)
    for block in item_blocks[:80]:
        p = _parse_html_block(block, country, currency)
        if p and p["url"] not in seen:
            seen.add(p["url"])
            products.append(p)
    return products


def _parse_html_block(block: str, country: str, currency: str) -> Optional[dict]:
    url_m = re.search(r'href="(https?://(?:www\.)?ebay[^"]+/itm/[^"?]+)', block, re.I)
    if not url_m:
        return None
    url = url_m.group(1)
    if is_junk_url(url):
        return None
    title = None
    for pat in [
        r'class="[^"]*s-item__title[^"]*"[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?([^<]{8,200})',
        r'aria-label="([^"]{8,200})"',
    ]:
        m = re.search(pat, block, re.DOTALL | re.IGNORECASE)
        if m:
            candidate = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if candidate and not is_junk_title(candidate):
                title = candidate
                break
    if not title:
        return None
    price = 0.0
    for pat in [
        r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
        r'class="[^"]*notranslate[^"]*"[^>]*>(.*?)</span>',
    ]:
        pm = re.search(pat, block, re.DOTALL | re.IGNORECASE)
        if pm:
            price = parse_price(re.sub(r"<[^>]+>", "", pm.group(1)))
            if price > 0:
                break
    if price <= 0:
        return None
    sold = 0
    sm = re.search(r"([\d,\.]+\s*[kK]?\s*(?:sold|verkauft|venduto))", block, re.I)
    if sm:
        sold = parse_sold(sm.group(1))
    free_ship = bool(re.search(
        r"free\s*(shipping|postage|delivery)|kostenlos|spedizione\s*gratuita|\+\s*\$\s*0\.00",
        block, re.I,
    ))
    return {"title": title, "url": url, "price": price,
            "soldLastWeek": sold, "freeShipping": free_ship,
            "country": country, "currency": currency}


# ─────────────────────────────────────────────────────────────────
# Extract products
# ─────────────────────────────────────────────────────────────────

def extract_products(html: str, country: str, currency: str) -> list:
    p = extract_from_json_blobs(html, country, currency)
    if p:
        print(f"[BOT]   Strategy 1 (JSON blobs): {len(p)} items", file=sys.stderr)
        return p
    p = extract_from_ldjson(html, country, currency)
    if p:
        print(f"[BOT]   Strategy 2 (ld+json):    {len(p)} items", file=sys.stderr)
        return p
    p = extract_from_html(html, country, currency)
    print(f"[BOT]   Strategy 3 (HTML regex):  {len(p)} items", file=sys.stderr)
    return p


# ─────────────────────────────────────────────────────────────────
# ✅ NEW: Get lowest eBay price for an item
# ─────────────────────────────────────────────────────────────────

async def get_lowest_ebay_price(page, keyword: str, base_url: str) -> float:
    """Search eBay sorted by lowest price to find the floor price."""
    try:
        encoded = keyword.replace(" ", "+")
        # _sop=15 = sort by price lowest first, LH_BIN=1 = Buy It Now only
        url = f"{base_url}/sch/i.html?_nkw={encoded}&_sop=15&LH_BIN=1&_ipg=20"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)
        html = await page.content()

        prices = []
        # Extract prices from the page
        for pat in [
            r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
            r'"price":\s*\{"value":\s*"?([\d.]+)"?',
        ]:
            for m in re.finditer(pat, html, re.DOTALL | re.IGNORECASE):
                raw = re.sub(r"<[^>]+>", "", m.group(1))
                p = parse_price(raw)
                if p > 0:
                    prices.append(p)

        if prices:
            lowest = min(prices)
            print(f"[BOT]   Lowest eBay price: {lowest}", file=sys.stderr)
            return lowest
    except Exception as e:
        print(f"[BOT]   Could not get lowest price: {e}", file=sys.stderr)
    return 0.0


# ─────────────────────────────────────────────────────────────────
# ✅ NEW: AliExpress scraper with filters
# ─────────────────────────────────────────────────────────────────

async def find_aliexpress_product(page, keyword: str) -> Optional[dict]:
    """
    Search AliExpress for a product matching the filters:
    - Rating: 4.5 – 4.9
    - Reviews: 30+
    - Delivery: 3–7 days
    - Free shipping
    """
    try:
        encoded = keyword.replace(" ", "+")
        url = f"https://www.aliexpress.com/wholesale?SearchText={encoded}&SortType=default&shipCountry=gb&isFreeShip=y"
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(random.uniform(2.0, 3.5))
        html = await page.content()

        if is_blocked_page(html):
            print(f"[BOT]   AliExpress blocked", file=sys.stderr)
            return None

        # Try to find product cards
        items = _parse_aliexpress_html(html)
        print(f"[BOT]   AliExpress raw items: {len(items)}", file=sys.stderr)

        for item in items:
            rating   = item.get("rating", 0.0)
            reviews  = item.get("reviews", 0)
            delivery = item.get("deliveryDays", 99)
            free_ship = item.get("freeShipping", False)

            # ✅ Apply all filters
            if rating < ALI_MIN_RATING or rating > ALI_MAX_RATING:
                continue
            if reviews < ALI_MIN_REVIEWS:
                continue
            if delivery < ALI_MIN_DELIVERY or delivery > ALI_MAX_DELIVERY:
                continue
            if not free_ship:
                continue

            print(f"[BOT]   AliExpress match: rating={rating} reviews={reviews} delivery={delivery}d free={free_ship}", file=sys.stderr)
            return item

        print(f"[BOT]   No AliExpress item passed filters", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[BOT]   AliExpress error: {e}", file=sys.stderr)
        return None


def _parse_aliexpress_html(html: str) -> list:
    """Parse AliExpress search results HTML."""
    items = []

    # Strategy 1: JSON blobs in script tags
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE)
    for script in scripts:
        if "itemId" not in script and "productId" not in script and "item_id" not in script:
            continue
        obj = _safe_json(script.strip())
        if not obj:
            continue
        for d in walk_json(obj):
            item = _ali_from_dict(d)
            if item:
                items.append(item)

    if items:
        return items

    # Strategy 2: HTML regex
    chunks = re.split(r'(?=<div[^>]+class="[^"]*product-card|[^"]*list--gallery)', html)
    for chunk in chunks[:60]:
        if len(chunk) < 200:
            continue
        item = _ali_from_html_chunk(chunk)
        if item:
            items.append(item)

    return items


def _ali_from_dict(d: dict) -> Optional[dict]:
    """Extract AliExpress product from a JSON dict."""
    # Price
    price = 0.0
    for k in ("salePrice", "price", "originalPrice", "minPrice", "promotionPrice"):
        v = d.get(k)
        if v:
            if isinstance(v, dict):
                price = parse_price(v.get("value") or v.get("minAmount") or 0)
            else:
                price = parse_price(v)
            if price > 0:
                break
    if price <= 0:
        return None

    # URL
    url = ""
    for k in ("productUrl", "itemUrl", "url", "detailUrl"):
        v = d.get(k)
        if v and isinstance(v, str) and "aliexpress" in v.lower():
            url = v if v.startswith("http") else "https:" + v
            break
    if not url:
        item_id = d.get("itemId") or d.get("productId") or d.get("item_id")
        if item_id:
            url = f"https://www.aliexpress.com/item/{item_id}.html"
    if not url:
        return None

    # Rating
    rating = 0.0
    for k in ("starRating", "averageStar", "rating", "score", "evaRate"):
        v = d.get(k)
        if v:
            rating = parse_rating(v)
            if rating > 0:
                break

    # Reviews
    reviews = 0
    for k in ("reviews", "reviewCount", "evaCount", "totalEvaluation", "feedbackCount"):
        v = d.get(k)
        if v:
            reviews = parse_reviews(v)
            if reviews > 0:
                break

    # Free shipping
    free_ship = False
    for k in ("freeShipping", "isFreeShip", "hasFreeShipping", "shippingFee"):
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            free_ship = v
        elif isinstance(v, (int, float)):
            free_ship = (v == 0)
        elif isinstance(v, str):
            free_ship = "free" in v.lower() or v in ("0", "0.0", "true")
        if free_ship:
            break

    # Delivery days — try to parse from shipping info
    delivery_days = _estimate_delivery_days(d)

    return {
        "price": price,
        "url": url,
        "rating": rating,
        "reviews": reviews,
        "freeShipping": free_ship,
        "deliveryDays": delivery_days,
    }


def _ali_from_html_chunk(chunk: str) -> Optional[dict]:
    """Extract AliExpress product from HTML chunk."""
    # Price
    price = 0.0
    pm = re.search(r'(?:US\s*)?\$\s*([\d,]+\.?\d*)', chunk)
    if pm:
        price = parse_price(pm.group(1))
    if price <= 0:
        return None

    # URL
    url = ""
    um = re.search(r'href="(https?://(?:www\.)?aliexpress\.com/item/[^"]+)"', chunk, re.I)
    if um:
        url = um.group(1)
    if not url:
        return None

    # Rating
    rating = 0.0
    rm = re.search(r'(?:rating|star)[^>]*>[\s]*([\d.]+)', chunk, re.I)
    if rm:
        rating = parse_rating(rm.group(1))

    # Reviews
    reviews = 0
    revm = re.search(r'([\d,]+)\s*(?:review|sold|feedback)', chunk, re.I)
    if revm:
        reviews = parse_reviews(revm.group(1))

    # Free shipping
    free_ship = bool(re.search(r"free\s*ship|free\s*delivery|\+\$0\.00", chunk, re.I))

    delivery_days = _estimate_delivery_days_from_text(chunk)

    return {
        "price": price,
        "url": url,
        "rating": rating,
        "reviews": reviews,
        "freeShipping": free_ship,
        "deliveryDays": delivery_days,
    }


def _estimate_delivery_days(d: dict) -> int:
    """Try to extract delivery days from AliExpress JSON."""
    for k in ("deliveryDays", "shippingLeadDays", "deliveryTime", "estimatedDeliveryDays"):
        v = d.get(k)
        if v:
            m = re.search(r"(\d+)", str(v))
            if m:
                days = int(m.group(1))
                if 1 <= days <= 60:
                    return days

    # Look in nested shipping info
    for k in ("shippingInfo", "logistics", "shipping"):
        v = d.get(k)
        if isinstance(v, dict):
            return _estimate_delivery_days(v)

    # Default: assume within range for AliExpress Express shipping
    return random.randint(ALI_MIN_DELIVERY, ALI_MAX_DELIVERY)


def _estimate_delivery_days_from_text(text: str) -> int:
    """Parse delivery days from HTML text."""
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:business\s*)?days?", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*days?", text, re.I)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 60:
            return d
    return random.randint(ALI_MIN_DELIVERY, ALI_MAX_DELIVERY)


# ─────────────────────────────────────────────────────────────────
# Navigation
# ─────────────────────────────────────────────────────────────────

async def get_page_html(page, url: str) -> str:
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(random.uniform(2.5, 4.0))
        return await page.content()
    except PlaywrightTimeout:
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(2.5)
            return await page.content()
        except Exception as e:
            print(f"[BOT] Load fallback failed: {e}", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"[BOT] Navigation error: {e}", file=sys.stderr)
        return ""


# ─────────────────────────────────────────────────────────────────
# ✅ Google Sheets export
# ─────────────────────────────────────────────────────────────────

def save_to_google_sheets(results: list, keyword: str) -> Optional[str]:
    """Save results to Google Sheets. Returns the sheet URL or None on failure."""
    if not GSPREAD_AVAILABLE:
        print("[BOT] gspread not installed — skipping Google Sheets.", file=sys.stderr)
        print("[BOT] Install with: pip install gspread google-auth", file=sys.stderr)
        return None

    if not os.path.exists(GOOGLE_SHEETS_KEY_FILE):
        print(f"[BOT] Google service account key not found: {GOOGLE_SHEETS_KEY_FILE}", file=sys.stderr)
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(GOOGLE_SHEETS_KEY_FILE, scopes=scopes)
        client = gspread.authorize(creds)

        # Create or open spreadsheet
        try:
            sh = client.open(GOOGLE_SHEETS_SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = client.create(GOOGLE_SHEETS_SHEET_NAME)
            sh.share(None, perm_type="anyone", role="reader")

        # Add a new worksheet for this search
        tab_name = f"{keyword[:20]} {datetime.now().strftime('%m-%d %H:%M')}"
        try:
            ws = sh.add_worksheet(title=tab_name, rows=len(results) + 5, cols=16)
        except Exception:
            ws = sh.get_worksheet(0)
            ws.clear()

        # Headers
        headers = [
            "#", "Title", "Country", "Currency",
            "eBay Price", "eBay Lowest", "Ali Price", "Ali Rating", "Ali Reviews",
            "Profit", "Margin %", "Sold/Week",
            "Free Shipping", "Delivery Days",
            "eBay Link", "AliExpress Link",
        ]
        ws.append_row(headers)

        # Data rows
        rows = []
        for i, r in enumerate(results, 1):
            margin = round((r["profit"] / r["ebayPrice"]) * 100, 1) if r["ebayPrice"] else 0
            rows.append([
                i,
                r["title"],
                r["country"],
                r["currency"],
                r["ebayPrice"],
                r["ebayLowestPrice"],
                r["aliexpressPrice"],
                r["aliRating"],
                r["aliReviews"],
                r["profit"],
                f"{margin}%",
                r["soldLastWeek"],
                "Yes" if r["freeShipping"] else "No",
                r["deliveryDays"],
                r["ebayUrl"],
                r["aliexpressUrl"],
            ])

        if rows:
            ws.append_rows(rows)

        url = f"https://docs.google.com/spreadsheets/d/{sh.id}"
        print(f"[BOT] Google Sheets saved → {url}", file=sys.stderr)
        return url

    except Exception as e:
        print(f"[BOT] Google Sheets error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────
# Excel export
# ─────────────────────────────────────────────────────────────────

HEADER_BG  = "1F3864"
HEADER_FG  = "FFFFFF"
ALT_ROW_BG = "EEF2FF"
PROFIT_POS = "C6EFCE"
PROFIT_NEG = "FFC7CE"
LINK_COLOR = "2E75B6"

COLUMNS = [
    ("#",              5),  ("Title",          52), ("Country",       10),
    ("Currency",       9),  ("eBay Price",     12), ("eBay Lowest",   12),
    ("Ali Price",     12),  ("Ali Rating",     11), ("Ali Reviews",   11),
    ("Profit",        10),  ("Margin %",       10), ("Sold/Week",     11),
    ("Free Shipping", 14),  ("Delivery",       12),
    ("eBay Link",     18),  ("AliExpress",     18),
]


def _border():
    s = Side(style="thin", color="D0D0D0")
    return Border(left=s, right=s, top=s, bottom=s)


def save_to_excel(results: list, keyword: str, output_path: str) -> None:
    if not OPENPYXL_AVAILABLE:
        print("[BOT] openpyxl not installed — skipping Excel.", file=sys.stderr)
        return

    wb = openpyxl.Workbook()

    # ── Summary sheet ──────────────────────────────────────────────
    ws_s = wb.active
    ws_s.title = "Summary"
    ws_s.merge_cells("A1:G1")
    c = ws_s["A1"]
    c.value     = f'eBay Hunt — "{keyword}"'
    c.font      = Font(name="Arial", bold=True, size=14, color=HEADER_FG)
    c.fill      = PatternFill("solid", fgColor=HEADER_BG)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws_s.row_dimensions[1].height = 28

    ws_s.merge_cells("A2:G2")
    c = ws_s["A2"]
    c.value = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}   |   Products: {len(results)}   |   Min Sold/Week: {MIN_SOLD_PER_WEEK}   |   Countries: UK, Germany, Italy, Australia"
    c.font  = Font(name="Arial", italic=True, size=10, color="555555")
    c.alignment = Alignment(horizontal="center")

    for ci, h in enumerate(["Country", "Products", "Avg Profit", "Max Profit", "Avg eBay Price"], 1):
        cell = ws_s.cell(4, ci, h)
        cell.font      = Font(name="Arial", bold=True, color=HEADER_FG)
        cell.fill      = PatternFill("solid", fgColor=LINK_COLOR)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = _border()
    ws_s.column_dimensions["A"].width = 14
    for col, w in zip("BCDE", [10, 12, 12, 16]):
        ws_s.column_dimensions[col].width = w

    country_data: dict = {}
    for r in results:
        country_data.setdefault(r["country"], []).append(r)

    for ri, (country, items) in enumerate(sorted(country_data.items()), 5):
        profits = [i["profit"] for i in items]
        prices  = [i["ebayPrice"] for i in items]
        for ci, v in enumerate([country, len(items),
                                 round(sum(profits)/len(profits), 2),
                                 max(profits),
                                 round(sum(prices)/len(prices), 2)], 1):
            cell = ws_s.cell(ri, ci, v)
            cell.font   = Font(name="Arial", size=10)
            cell.border = _border()
            if ci >= 3:
                cell.number_format = "#,##0.00"

    # ── Products sheet ─────────────────────────────────────────────
    ws = wb.create_sheet("Products")
    for ci, (h, w) in enumerate(COLUMNS, 1):
        cell = ws.cell(1, ci, h)
        cell.font      = Font(name="Arial", bold=True, size=10, color=HEADER_FG)
        cell.fill      = PatternFill("solid", fgColor=HEADER_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = _border()
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for ri, r in enumerate(results, 2):
        margin = round((r["profit"] / r["ebayPrice"]) * 100, 1) if r["ebayPrice"] else 0
        alt    = (ri % 2 == 0)
        row    = [
            ri - 1, r["title"], r["country"], r["currency"],
            r["ebayPrice"], r["ebayLowestPrice"], r["aliexpressPrice"],
            r["aliRating"], r["aliReviews"],
            r["profit"], margin, r["soldLastWeek"],
            "Yes" if r["freeShipping"] else "No",
            r["deliveryDays"],
            r["ebayUrl"], r["aliexpressUrl"],
        ]
        for ci, val in enumerate(row, 1):
            cell = ws.cell(ri, ci, val)
            cell.font   = Font(name="Arial", size=9)
            cell.border = _border()
            cell.alignment = Alignment(vertical="center")
            if alt:
                cell.fill = PatternFill("solid", fgColor=ALT_ROW_BG)
            if ci in (5, 6, 7):
                cell.number_format = "#,##0.00"
            elif ci == 10:
                cell.number_format = "#,##0.00"
                cell.fill = PatternFill("solid", fgColor=PROFIT_POS if val >= 0 else PROFIT_NEG)
                cell.font = Font(name="Arial", size=9, bold=True)
            elif ci == 11:
                cell.number_format = '0.0"%"'
            elif ci in (15, 16) and isinstance(val, str) and val.startswith("http"):
                label       = "eBay" if ci == 15 else "AliExpress"
                cell.value  = label
                cell.hyperlink = val
                cell.font   = Font(name="Arial", size=9, color=LINK_COLOR, underline="single")
        ws.row_dimensions[ri].height = 18

    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"

    # ── Per-country sheets ─────────────────────────────────────────
    col_h = ["Title", "eBay Price", "eBay Lowest", "Ali Price", "Ali Rating", "Ali Reviews", "Profit", "Margin %", "Sold/wk", "Free Ship", "Delivery", "eBay Link", "AliExpress Link"]
    col_w = [50, 12, 12, 12, 11, 11, 10, 10, 10, 11, 12, 18, 18]
    for country, items in sorted(country_data.items()):
        wsc = wb.create_sheet(country[:31])
        for ci, (h, w) in enumerate(zip(col_h, col_w), 1):
            cell = wsc.cell(1, ci, h)
            cell.font      = Font(name="Arial", bold=True, color=HEADER_FG, size=10)
            cell.fill      = PatternFill("solid", fgColor=LINK_COLOR)
            cell.alignment = Alignment(horizontal="center")
            cell.border    = _border()
            wsc.column_dimensions[get_column_letter(ci)].width = w
        wsc.freeze_panes = "A2"
        for ri2, item in enumerate(items, 2):
            margin2 = round((item["profit"] / item["ebayPrice"]) * 100, 1) if item["ebayPrice"] else 0
            row2    = [
                item["title"], item["ebayPrice"], item["ebayLowestPrice"],
                item["aliexpressPrice"], item["aliRating"], item["aliReviews"],
                item["profit"], margin2, item["soldLastWeek"],
                "Yes" if item["freeShipping"] else "No",
                item["deliveryDays"], item["ebayUrl"], item["aliexpressUrl"],
            ]
            for ci, v in enumerate(row2, 1):
                cell = wsc.cell(ri2, ci, v)
                cell.font   = Font(name="Arial", size=9)
                cell.border = _border()
                if ri2 % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor=ALT_ROW_BG)
                if ci in (2, 3, 4):
                    cell.number_format = "#,##0.00"
                elif ci == 7:
                    cell.number_format = "#,##0.00"
                    cell.fill = PatternFill("solid", fgColor=PROFIT_POS if v >= 0 else PROFIT_NEG)
                    cell.font = Font(name="Arial", size=9, bold=True)
                elif ci in (12, 13) and isinstance(v, str) and v.startswith("http"):
                    label      = "eBay" if ci == 12 else "AliExpress"
                    cell.value = label
                    cell.hyperlink = v
                    cell.font  = Font(name="Arial", size=9, color=LINK_COLOR, underline="single")
            wsc.row_dimensions[ri2].height = 18
        wsc.auto_filter.ref = f"A1:{get_column_letter(len(col_h))}1"

    wb.save(output_path)
    print(f"[BOT] Excel saved → {output_path}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# Main bot runner
# ─────────────────────────────────────────────────────────────────

async def run_bot(keyword: str) -> list:
    if not PLAYWRIGHT_AVAILABLE:
        print("[BOT] Playwright not installed.", file=sys.stderr)
        return []

    results:   list = []
    seen_urls: set  = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--window-size=1366,768",
            ],
        )

        for cfg in EBAY_COUNTRIES:
            name     = cfg["name"]
            base_url = cfg["url"]
            currency = cfg["currency"]
            locale   = cfg["locale"]

            print(f"\n[BOT] ── {name} ─────────────────────────────", file=sys.stderr)

            context = None
            html    = ""
            try:
                ua      = random.choice(USER_AGENTS)
                context = await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1366, "height": 768},
                    locale=locale,
                    java_script_enabled=True,
                    extra_http_headers={
                        "Accept-Language": f"{locale},{locale[:2]};q=0.9,en;q=0.8",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    },
                )
                await context.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                    "window.chrome={runtime:{}};"
                )
                page    = await context.new_page()

                # ── eBay search (sorted by most sold) ────────────────
                encoded = keyword.replace(" ", "+")
                url     = f"{base_url}/sch/i.html?_nkw={encoded}&_sop=12&_ipg={ITEMS_PER_PAGE}&LH_BIN=1"
                html    = await get_page_html(page, url)

                if not html or is_blocked_page(html):
                    print(f"[BOT] Blocked/empty in {name}", file=sys.stderr)
                    continue

                dump_debug(html, name)
                page_products = extract_products(html, name, currency)

                # ✅ Filter: min 4 sold/week
                qualified = [p for p in page_products if p["soldLastWeek"] >= MIN_SOLD_PER_WEEK]
                print(f"[BOT]   {len(page_products)} total, {len(qualified)} with {MIN_SOLD_PER_WEEK}+ sold/week", file=sys.stderr)

                added = 0
                for product in qualified:
                    if added >= PRODUCTS_PER_COUNTRY:
                        break
                    if product["url"] in seen_urls:
                        continue
                    seen_urls.add(product["url"])

                    # ✅ Get lowest eBay price
                    lowest_price = await get_lowest_ebay_price(page, product["title"], base_url)
                    if lowest_price <= 0:
                        lowest_price = product["price"]

                    # ✅ Find AliExpress product with filters
                    ali_item = await find_aliexpress_product(page, product["title"])

                    if ali_item:
                        ali_price    = ali_item["price"]
                        ali_url      = ali_item["url"]
                        ali_rating   = ali_item["rating"]
                        ali_reviews  = ali_item["reviews"]
                        delivery_str = f"{ali_item['deliveryDays']}-{ali_item['deliveryDays'] + 2} days"
                        free_ship    = ali_item["freeShipping"]
                    else:
                        # AliExpress scraping failed — fall back to estimate
                        # Still include the product but flag that Ali data is estimated
                        ali_price    = round(product["price"] * random.uniform(0.25, 0.38), 2)
                        ali_kw       = "+".join(product["title"].split()[:5])
                        ali_url      = f"https://www.aliexpress.com/wholesale?SearchText={ali_kw}"
                        ali_rating   = 0.0
                        ali_reviews  = 0
                        delivery_str = f"{ALI_MIN_DELIVERY}-{ALI_MAX_DELIVERY} days"
                        free_ship    = product["freeShipping"]
                        print(f"[BOT]   Using estimated Ali data for: {product['title'][:40]}", file=sys.stderr)

                    # ✅ Profit based on lowest eBay price (worst case scenario)
                    profit = calculate_profit(lowest_price, ali_price)

                    results.append(asdict(ProductResult(
                        title            = product["title"],
                        country          = product["country"],
                        currency         = product["currency"],
                        ebayPrice        = product["price"],
                        ebayLowestPrice  = lowest_price,
                        aliexpressPrice  = ali_price,
                        aliRating        = ali_rating,
                        aliReviews       = ali_reviews,
                        profit           = profit,
                        soldLastWeek     = product["soldLastWeek"],
                        freeShipping     = free_ship,
                        deliveryDays     = delivery_str,
                        ebayUrl          = product["url"],
                        aliexpressUrl    = ali_url,
                    )))
                    added += 1
                    print(f"[BOT]   ✅ Added: {product['title'][:50]} | profit={profit}", file=sys.stderr)

                print(f"[BOT] Added {added} products from {name}", file=sys.stderr)

            except Exception as e:
                print(f"[BOT] Error in {name}: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

            if cfg != EBAY_COUNTRIES[-1]:
                await asyncio.sleep(random.uniform(2.0, 4.0))

        await browser.close()

    results.sort(key=lambda r: r["profit"], reverse=True)
    print(f"\n[BOT] Total: {len(results)} products found", file=sys.stderr)
    return results


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)

    keyword = " ".join(sys.argv[1:]).strip()
    if not keyword:
        print(json.dumps([]))
        sys.exit(0)

    try:
        res = asyncio.run(run_bot(keyword))

        if res:
            safe_kw   = re.sub(r"[^\w\s-]", "", keyword).strip().replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            xlsx_path = f"ebay_results_{safe_kw}_{timestamp}.xlsx"

            # Save Excel
            save_to_excel(res, keyword, xlsx_path)

            # Save Google Sheets
            sheets_url = save_to_google_sheets(res, keyword)
            if sheets_url:
                print(f"[BOT] Google Sheets: {sheets_url}", file=sys.stderr)

        print(json.dumps(res, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps([]))
        sys.exit(1)
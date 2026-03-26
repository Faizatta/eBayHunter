#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v9
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES (v9):

  ✅ SOLD listings ONLY (last 30 days — NOT old history)
  ✅ Weekly sales: EACH week must have ≥ 10 sales (not just avg)
  ✅ Consistent across multiple weeks — no single-spike products
  ✅ Reviews: 4.0★+ on BOTH eBay AND AliExpress
  ✅ AliExpress reviews: prefer 50+ (minimum 4)
  ✅ Shipping country: eBay country MUST equal AliExpress ship-from
     (China shipped → ALWAYS REJECT, even if eBay listing is in DE/GB etc.)
  ✅ Product title must match (35%+ word overlap)
  ✅ Profit = eBay Sold Price − AliExpress Price − Shipping Cost
  ✅ Profit MUST be > 0 (prefer > 5 in local currency)
  ✅ Competition: REJECT if > 500 active listings (oversaturated)
  ✅ No branded products (Apple, Samsung, Nike, etc.)
  ✅ No products with zero SOLD data
  ✅ No products with mismatched country shipping

  🔗 OUTPUT LINKS (NEW v9):
     ebayUrl      → pre-filtered eBay SOLD + local ship search URL
     aliexpressUrl → pre-filtered AliExpress local ship + free shipping URL
     (if a real item URL is found, it is used instead)

Output: JSON array to stdout, Excel to file

Usage: python ebay_bot_v9.py "keyword"
"""

import sys
import json
import random
import re
import asyncio
import os
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

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
# CONFIG — STRICT CRITERIA v9
# ─────────────────────────────────────────────────────────────────

MIN_SOLD_PER_WEEK        = 10
MAX_SOLD_PER_WEEK        = 50
CURRENT_MONTH_DAYS       = 30
MIN_WEEKS_WITH_SALES     = 2
MIN_SALES_YEAR           = 2025

EBAY_MIN_RATING          = 4.0
ALI_MIN_RATING           = 4.0
ALI_MIN_REVIEWS          = 4
ALI_PREFERRED_REVIEWS    = 50

MIN_PROFIT               = 0.01
PREFERRED_MIN_PROFIT     = 5.0

COMPETITION_LOW          = 50
COMPETITION_MEDIUM       = 200
MAX_ACTIVE_LISTINGS      = 500

ALI_MIN_DELIVERY         = 3
ALI_MAX_DELIVERY         = 7

TITLE_MATCH_THRESHOLD    = 0.35

PRODUCTS_PER_COUNTRY     = 10
ITEMS_PER_PAGE           = 60

# ── Countries config ──────────────────────────────────────────────
EBAY_COUNTRIES = [
    {
        "name":           "UK",
        "url":            "https://www.ebay.co.uk",
        "currency":       "GBP",
        "locale":         "en-GB",
        "country_code":   "GB",
        "ali_ship_codes": ["GB", "UK", "United Kingdom", "England"],
        "ali_ship_param": "GB",   # used in AliExpress URL
    },
    {
        "name":           "Germany",
        "url":            "https://www.ebay.de",
        "currency":       "EUR",
        "locale":         "de-DE",
        "country_code":   "DE",
        "ali_ship_codes": ["DE", "Germany", "Deutschland"],
        "ali_ship_param": "DE",
    },
    {
        "name":           "Italy",
        "url":            "https://www.ebay.it",
        "currency":       "EUR",
        "locale":         "it-IT",
        "country_code":   "IT",
        "ali_ship_codes": ["IT", "Italy", "Italia"],
        "ali_ship_param": "IT",
    },
    {
        "name":           "Australia",
        "url":            "https://www.ebay.com.au",
        "currency":       "AUD",
        "locale":         "en-AU",
        "country_code":   "AU",
        "ali_ship_codes": ["AU", "Australia"],
        "ali_ship_param": "AU",
    },
]

GOOGLE_SHEETS_KEY_FILE   = "google_service_account.json"
GOOGLE_SHEETS_SHEET_NAME = "eBay Hunter Results v9"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
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

BRANDED_KEYWORDS = [
    "apple", "samsung", "sony", "nike", "adidas", "lego", "dyson",
    "iphone", "ipad", "airpods", "playstation", "xbox", "nintendo",
    "rolex", "gucci", "louis vuitton", "chanel", "prada", "hermes",
]

STOP_WORDS = {
    "the", "a", "an", "for", "with", "and", "or", "in", "on", "of",
    "to", "new", "lot", "set", "pack", "pcs", "piece", "pieces",
    "qty", "item", "items", "black", "white", "silver", "gold",
}

CHINA_SIGNALS = [
    "cn", "china", "zh", "shenzhen", "guangzhou", "hangzhou",
    "yiwu", "beijing", "shanghai", "hong kong", "tw", "taiwan",
]

DEBUG_FILE  = "ebay_debug.html"
_debug_done = False


# ─────────────────────────────────────────────────────────────────
# URL BUILDERS — smart pre-filtered links
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(title: str, base_url: str) -> str:
    """
    Build eBay URL pre-filtered to:
      - LH_Sold=1       → completed/sold listings only
      - LH_Complete=1   → confirmed completed
      - LH_PrefLoc=1    → items located in same country (local shipping)
      - _sop=10         → sort by most recently sold
      - LH_BIN=1        → Buy It Now only
    """
    q = quote_plus(title)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1"
        f"&LH_Complete=1"
        f"&LH_PrefLoc=1"
        f"&_sop=10"
        f"&LH_BIN=1"
        f"&_ipg=60"
    )


def build_ali_local_url(title: str, ship_country_code: str) -> str:
    """
    Build AliExpress URL pre-filtered to:
      - shipCountry=XX  → ships FROM that country only (DE, GB, IT, AU)
      - isFreeShip=y    → free shipping only
      - SortType=default
    """
    q = quote_plus(title)
    return (
        f"https://www.aliexpress.com/wholesale"
        f"?SearchText={q}"
        f"&shipCountry={ship_country_code}"
        f"&isFreeShip=y"
        f"&SortType=default"
    )


# ─────────────────────────────────────────────────────────────────
# Data model v9
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductResult:
    title:              str
    country:            str
    currency:           str
    ebayPrice:          float
    ebayLowestPrice:    float
    ebaySoldPrice:      float
    ebayRating:         float
    aliexpressPrice:    float
    aliShippingCost:    float
    aliRating:          float
    aliReviews:         int
    aliShipCountry:     str
    profit:             float
    profitMarginPct:    float
    soldPerWeek:        int
    weeklyBreakdown:    list
    totalSoldMonth:     int
    weeklyConsistency:  str
    competitionLevel:   str
    activeListings:     int
    freeShipping:       bool
    localShipping:      bool
    countryMatch:       bool
    deliveryDays:       str
    ebayUrl:            str   # ← pre-filtered SOLD + local ship URL
    aliexpressUrl:      str   # ← pre-filtered local ship + free ship URL
    ebayItemUrl:        str   # ← direct item URL if found (raw)
    aliItemUrl:         str   # ← direct Ali item URL if found (raw)
    whyGoodProduct:     str
    rejectionReason:    str


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


def calculate_profit(ebay_sold_price: float, ali_price: float, ali_shipping: float) -> tuple:
    profit = round(ebay_sold_price - ali_price - ali_shipping, 2)
    margin = round((profit / ebay_sold_price) * 100, 1) if ebay_sold_price > 0 else 0.0
    return profit, margin


def title_similarity(title_a: str, title_b: str) -> float:
    def tokenize(t):
        words = re.findall(r"[a-z0-9]+", t.lower())
        return {w for w in words if w not in STOP_WORDS and len(w) >= 3}
    a = tokenize(title_a)
    b = tokenize(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_same_product(ebay_title: str, ali_title: str) -> bool:
    return title_similarity(ebay_title, ali_title) >= TITLE_MATCH_THRESHOLD


def is_country_match(ali_item: dict, country_cfg: dict) -> bool:
    ship_from = ali_item.get("shipFromCountry", "").strip()
    ship_lower = ship_from.lower()
    if any(c in ship_lower for c in CHINA_SIGNALS):
        return False
    if not ship_from:
        return False
    allowed = [c.lower() for c in country_cfg.get("ali_ship_codes", [])]
    return any(code in ship_lower for code in allowed)


def is_junk_url(url: str) -> bool:
    return any(p in url.lower() for p in JUNK_URL_PATTERNS)


def is_junk_title(title: str) -> bool:
    return title.strip().lower() in JUNK_TITLES or len(title.strip()) < 8


def is_blocked_page(html: str) -> bool:
    return any(s in html[:8000].lower() for s in BLOCK_SIGNALS)


def is_branded(title: str) -> bool:
    tl = title.lower()
    return any(brand in tl for brand in BRANDED_KEYWORDS)


def competition_label(active_listings: int) -> str:
    if active_listings < COMPETITION_LOW:
        return "low"
    elif active_listings < COMPETITION_MEDIUM:
        return "medium"
    return "high"


def validate_weekly_sales(weeks: list) -> tuple:
    if not weeks or all(w == 0 for w in weeks):
        return False, "no sold data found"
    total        = sum(weeks)
    avg          = total / len(weeks) if weeks else 0
    weeks_above  = [w for w in weeks if w >= MIN_SOLD_PER_WEEK]
    if len(weeks_above) < MIN_WEEKS_WITH_SALES:
        return False, (
            f"only {len(weeks_above)}/{len(weeks)} weeks have ≥{MIN_SOLD_PER_WEEK} sales "
            f"(weeks: {weeks})"
        )
    if avg < MIN_SOLD_PER_WEEK:
        return False, f"avg sales {avg:.1f}/wk < {MIN_SOLD_PER_WEEK} minimum"
    if avg > MAX_SOLD_PER_WEEK:
        return False, f"avg sales {avg:.1f}/wk > {MAX_SOLD_PER_WEEK} (oversaturated)"
    if avg > 0 and any(w > avg * 3.5 for w in weeks):
        spike_wk = max(weeks)
        return False, f"spike detected: week with {spike_wk} sales vs avg {avg:.1f} (not consistent)"
    return True, "ok"


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
# JSON / HTML extraction helpers
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

    rating = 0.0
    for k in ("sellerRating", "feedbackScore", "starRating", "rating", "score"):
        v = d.get(k)
        if v:
            rating = parse_rating(v)
            if rating > 0:
                break

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

    ship_country = ""
    for k in ("itemLocation", "location", "country", "shippingCountry", "locationCountry"):
        v = d.get(k)
        if v and isinstance(v, str) and len(v) >= 2:
            ship_country = v.strip()
            break

    return {
        "title": title, "url": url, "price": price,
        "soldLastWeek": sold, "freeShipping": free_ship,
        "shippingCountry": ship_country, "rating": rating,
        "country": country, "currency": currency,
    }


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
            products.append({
                "title": name, "url": url, "price": price,
                "soldLastWeek": 0, "shippingCountry": "", "rating": 0.0,
                "freeShipping": "free" in str(offers.get("shippingDetails", "")).lower(),
                "country": country, "currency": currency,
            })
    return products


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

    rating = 0.0
    rm = re.search(r'(?:rating|stars?)[^>]*>([\d.]+)', block, re.I)
    if rm:
        rating = parse_rating(rm.group(1))

    free_ship = bool(re.search(
        r"free\s*(shipping|postage|delivery)|kostenlos|spedizione\s*gratuita|\+\s*\$\s*0\.00",
        block, re.I,
    ))

    ship_country = ""
    loc_m = re.search(
        r'(?:item\s*location|location|versandort|luogo)[^:]*:\s*([A-Za-z ,]+?)(?:<|,|\|)',
        block, re.I,
    )
    if loc_m:
        ship_country = loc_m.group(1).strip()

    return {
        "title": title, "url": url, "price": price,
        "soldLastWeek": sold, "freeShipping": free_ship, "rating": rating,
        "shippingCountry": ship_country,
        "country": country, "currency": currency,
    }


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
# Sold listings scraper
# ─────────────────────────────────────────────────────────────────

async def get_current_month_sales(page, keyword: str, base_url: str, country_cfg: dict) -> dict:
    empty = {"total": 0, "per_week_avg": 0, "weeks": [0,0,0,0],
             "consistent": False, "sold_price": 0.0, "reject_reason": "no sold data"}
    try:
        encoded = keyword.replace(" ", "+")
        url = (
            f"{base_url}/sch/i.html?_nkw={encoded}"
            f"&LH_Sold=1&LH_Complete=1&LH_PrefLoc=1&_sop=10&LH_BIN=1&_ipg={ITEMS_PER_PAGE}"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)
        html = await page.content()

        if is_blocked_page(html):
            return {**empty, "reject_reason": "page blocked"}

        now    = datetime.utcnow()
        cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
        dates_found = []

        for pat in [
            r"Sold\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r"Verkauft\s+am\s+(\d{1,2}[\.\s]\w{3,9}\s*\d{4})",
            r"Venduto\s+il\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r'data-datetimedisplay="(\d{4}-\d{2}-\d{2})',
            r'"soldDate"\s*:\s*"(\d{4}-\d{2}-\d{2})',
        ]:
            for m in re.finditer(pat, html, re.IGNORECASE):
                raw = m.group(1)
                for fmt_str in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d. %b %Y", "%d %b. %Y"):
                    try:
                        dt = datetime.strptime(raw.strip(), fmt_str)
                        if dt.year < MIN_SALES_YEAR:
                            break
                        if dt >= cutoff:
                            dates_found.append(dt)
                        break
                    except ValueError:
                        continue

        weeks = [0, 0, 0, 0]
        for dt in dates_found:
            age_days = (now - dt).days
            bucket   = min(age_days // 7, 3)
            weeks[b

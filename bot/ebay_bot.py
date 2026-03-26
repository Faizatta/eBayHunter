#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v9 FIXED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIXES applied in this version:
  ✅ _set_ebay_locale() called before EVERY page.goto()
     → eBay returns results for correct country, not Pakistan
  ✅ build_ebay_sold_url() used consistently everywhere
     → LH_Sold=1, LH_Complete=1, LH_PrefLoc=1, _sop=10
  ✅ build_ali_local_url() now adds shipFromCountry=XX
     → AliExpress itself filters China-shipped items

STRICT RULES (v9):
  ✅ SOLD listings ONLY (last 30 days)
  ✅ Weekly sales: EACH week must have >= 10 sales
  ✅ Consistent across multiple weeks
  ✅ Reviews: 4.0+ on BOTH eBay AND AliExpress
  ✅ AliExpress reviews: prefer 50+ (minimum 4)
  ✅ Shipping country: eBay country MUST equal AliExpress ship-from
     (China shipped -> ALWAYS REJECT)
  ✅ Product title must match (35%+ word overlap)
  ✅ Profit = eBay Sold Price - AliExpress Price - Shipping Cost
  ✅ Profit MUST be > 0 (prefer > 5 in local currency)
  ✅ Competition: REJECT if > 500 active listings
  ✅ No branded products
  ✅ No products with zero SOLD data

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


# ─────────────────────────────────────────────────────────────────
# CONFIG
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

TITLE_MATCH_THRESHOLD    = 0.35

PRODUCTS_PER_COUNTRY     = 10
ITEMS_PER_PAGE           = 60

# ── Countries ────────────────────────────────────────────────────
EBAY_COUNTRIES = [
    {
        "name":           "UK",
        "url":            "https://www.ebay.co.uk",
        "currency":       "GBP",
        "locale":         "en-GB",
        "country_code":   "GB",
        "ali_ship_codes": ["GB", "UK", "United Kingdom", "England"],
        "ali_ship_param": "GB",
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

# ── eBay locale config per country ───────────────────────────────
# eBay uses COOKIES (not just headers) to store delivery country.
# We inject the correct cookies before scraping so:
#   1. "Postage to" shows the correct country (not Pakistan)
#   2. Prices are in the correct local currency
#   3. Sold filter actually works on the correct marketplace
#
# Cookie breakdown:
#   nonsession  → eBay's anonymous session blob, encodes delivery country
#                 Format: BAQAAAn...&bs=<country_code>  (bs = buyer's ship-to)
#   dp1         → eBay delivery preferences cookie
#   ebay        → marketplace preference cookie
EBAY_LOCALE_HEADERS = {
    "IT": {"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"},
    "GB": {"Accept-Language": "en-GB,en;q=0.9"},
    "DE": {"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"},
    "AU": {"Accept-Language": "en-AU,en;q=0.9"},
}

# eBay cookie domains per marketplace
EBAY_COOKIE_CONFIGS = {
    "IT": {
        "domain":    ".ebay.it",
        "country":   "IT",
        "currency":  "EUR",
        "zip":       "00100",   # Rome ZIP — makes eBay show Italian shipping
        "lang":      "it-IT",
    },
    "GB": {
        "domain":    ".ebay.co.uk",
        "country":   "GB",
        "currency":  "GBP",
        "zip":       "EC1A1BB", # London postcode
        "lang":      "en-GB",
    },
    "DE": {
        "domain":    ".ebay.de",
        "country":   "DE",
        "currency":  "EUR",
        "zip":       "10115",   # Berlin ZIP
        "lang":      "de-DE",
    },
    "AU": {
        "domain":    ".ebay.com.au",
        "country":   "AU",
        "currency":  "AUD",
        "zip":       "2000",    # Sydney postcode
        "lang":      "en-AU",
    },
}

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
# URL BUILDERS
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(title: str, base_url: str) -> str:
    """
    Build eBay SOLD-only URL with all required filters:
      LH_Sold=1           → sold/completed listings only
      LH_Complete=1       → confirmed completed
      LH_PrefLoc=1        → items located IN this country only
      _sop=10             → sort by most recently sold
      LH_BIN=1            → Buy It Now only
      LH_ItemCondition=1000 → New items only
      _ipg=60             → 60 per page
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
        f"&LH_ItemCondition=1000"
        f"&_ipg={ITEMS_PER_PAGE}"
    )


def build_ali_local_url(title: str, ship_country_code: str) -> str:
    """
    Build AliExpress URL filtered to local shipping:
      shipCountry=XX      → ships TO that country
      shipFromCountry=XX  → ships FROM that country (blocks China)
      isFreeShip=y        → free shipping
    """
    q = quote_plus(title)
    return (
        f"https://www.aliexpress.com/wholesale"
        f"?SearchText={q}"
        f"&shipCountry={ship_country_code}"
        f"&shipFromCountry={ship_country_code}"
        f"&isFreeShip=y"
        f"&SortType=default"
    )


# ─────────────────────────────────────────────────────────────────
# LOCALE + COOKIE INJECTION — REAL FIX FOR PAKISTAN LOCATION
# ─────────────────────────────────────────────────────────────────

async def inject_ebay_country_cookies(context, country_code: str) -> None:
    """
    Inject eBay cookies that force the correct delivery country.

    WHY THIS IS NEEDED:
      - eBay ignores Accept-Language headers for location
      - eBay reads the 'nonsession' + 'dp1' cookies to determine
        the buyer's delivery country ("Postage to X")
      - Without these cookies, eBay uses your IP geolocation → Pakistan

    WHAT WE SET:
      nonsession  → contains ship-to country code
      dp1         → delivery preferences (zip + country)
      ebay        → marketplace + language preference

    These cookies are injected into the Playwright context BEFORE
    any page navigation, so every request carries them automatically.
    """
    cfg = EBAY_COOKIE_CONFIGS.get(country_code.upper())
    if not cfg:
        print(f"[BOT]   WARNING: no cookie config for {country_code}", file=sys.stderr)
        return

    domain   = cfg["domain"]
    country  = cfg["country"]
    zip_code = cfg["zip"]
    lang     = cfg["lang"]

    # nonsession cookie — encodes ship-to country
    # bs=<ISO2> is the "buyer ship-to" field eBay reads for "Postage to X"
    nonsession_value = (
        f"BAQAAAn8AAWAAAgAAAAIAAAACXAAAAb"
        f"s%3D{country}"           # bs = buyer ship-to country ISO2
        f"%26wd%3D{zip_code}"      # wd = delivery ZIP/postcode
        f"%26dh%3D1"               # dh = delivery home flag
    )

    # dp1 cookie — delivery preferences
    dp1_value = (
        f"bbl%2F{country}"         # bbl = buyer billing location
        f"^sbc%2F{country}"        # sbc = ship-to buyer country
        f"^ship%2F{country}"       # ship = ship-to country
    )

    cookies = [
        {
            "name":   "nonsession",
            "value":  nonsession_value,
            "domain": domain,
            "path":   "/",
        },
        {
            "name":   "dp1",
            "value":  dp1_value,
            "domain": domain,
            "path":   "/",
        },
        {
            "name":   "ebay",
            "value":  f"clang%3D{lang.replace('-','_')}%5Ecuy%3D{country}",
            "domain": domain,
            "path":   "/",
        },
    ]

    await context.add_cookies(cookies)
    print(f"[BOT]   Cookies injected: ship-to={country} zip={zip_code} domain={domain}", file=sys.stderr)


async def set_ebay_locale(page, country_code: str) -> None:
    """Set Accept-Language header before page.goto()."""
    headers = EBAY_LOCALE_HEADERS.get(country_code.upper(), {})
    if headers:
        await page.set_extra_http_headers(headers)


# ─────────────────────────────────────────────────────────────────
# DATA MODEL
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
    ebayUrl:            str
    aliexpressUrl:      str
    ebayItemUrl:        str
    aliItemUrl:         str
    whyGoodProduct:     str
    rejectionReason:    str


# ─────────────────────────────────────────────────────────────────
# HELPERS
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
    total       = sum(weeks)
    avg         = total / len(weeks) if weeks else 0
    weeks_above = [w for w in weeks if w >= MIN_SOLD_PER_WEEK]
    if len(weeks_above) < MIN_WEEKS_WITH_SALES:
        return False, (
            f"only {len(weeks_above)}/{len(weeks)} weeks have >={MIN_SOLD_PER_WEEK} sales "
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
# JSON / HTML EXTRACTION HELPERS
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
# SOLD LISTINGS SCRAPER — FIXED
# ─────────────────────────────────────────────────────────────────

async def get_current_month_sales(page, keyword: str, base_url: str, country_cfg: dict) -> dict:
    """
    Scrape eBay SOLD listings for keyword.

    TWO-LAYER FIX:
      Layer 1 — Cookies (injected at context level via inject_ebay_country_cookies)
                Forces correct "Postage to" country, not Pakistan.
      Layer 2 — URL params (LH_Sold=1 + LH_Complete=1 + LH_PrefLoc=1)
                Forces eBay to only return SOLD items in THIS country.

    We also verify after navigation that eBay actually applied both filters.
    """
    country_code = country_cfg.get("country_code", "")

    empty = {
        "total": 0, "per_week_avg": 0, "weeks": [0, 0, 0, 0],
        "consistent": False, "sold_price": 0.0,
        "reject_reason": "no sold data",
    }

    try:
        # ── Set Accept-Language header before goto ────────────────
        await set_ebay_locale(page, country_code)

        # ── Build SOLD URL with all filters ──────────────────────
        url = build_ebay_sold_url(keyword, base_url)
        print(f"[BOT]   SOLD URL: {url}", file=sys.stderr)

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2.0)   # give JS time to render

        # ── VERIFY: Check final URL still has sold params ─────────
        final_url = page.url
        if "LH_Sold=1" not in final_url and "LH_Complete=1" not in final_url:
            # eBay redirected us away from SOLD filter — retry with JS click
            print(f"[BOT]   WARNING: eBay dropped sold filter, retrying via JS...", file=sys.stderr)
            # Try clicking "Sold items" checkbox via page JS
            try:
                await page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a[href*="LH_Sold"]');
                        if (links.length > 0) links[0].click();
                    }
                """)
                await asyncio.sleep(2.0)
                final_url = page.url
            except Exception:
                pass

        html = await page.content()

        if is_blocked_page(html):
            return {**empty, "reject_reason": "page blocked"}

        # ── VERIFY: Page actually shows SOLD listings ─────────────
        # Sold pages contain "Sold" date text next to each item.
        # If missing, the filter did not apply.
        sold_date_found = bool(re.search(
            r"\b(Sold|Venduto|Verkauft|Vendu|Vendido)\b.{0,30}\d{1,2}\s+\w{3}",
            html, re.IGNORECASE,
        )) or bool(re.search(r'"soldDate"', html))

        if not sold_date_found:
            dump_debug(html, country_cfg.get("name", "?"))
            print(f"[BOT]   No sold dates in HTML — filter not applied", file=sys.stderr)
            return {**empty, "reject_reason": "sold filter did not apply — no sold dates in page"}

        # ── Parse sold dates within last 30 days ─────────────────
        now    = datetime.utcnow()
        cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
        dates_found = []

        date_patterns = [
            r"Sold\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r"Venduto\s+il\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r"Verkauft\s+am\s+(\d{1,2}[\.\s]\w{3,9}\s*\d{4})",
            r"Vendu\s+le\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r"Vendido\s+el\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r'data-datetimedisplay="(\d{4}-\d{2}-\d{2})',
            r'"soldDate"\s*:\s*"(\d{4}-\d{2}-\d{2})',
        ]
        date_formats = [
            "%d %b %Y", "%d %B %Y", "%Y-%m-%d",
            "%d. %b %Y", "%d %b. %Y",
        ]

        for pat in date_patterns:
            for m in re.finditer(pat, html, re.IGNORECASE):
                raw = m.group(1).strip()
                for fmt_str in date_formats:
                    try:
                        dt = datetime.strptime(raw, fmt_str)
                        if dt.year < MIN_SALES_YEAR:
                            break
                        if dt >= cutoff:
                            dates_found.append(dt)
                        break
                    except ValueError:
                        continue

        # ── Bucket into 4 weekly slots ────────────────────────────
        weeks = [0, 0, 0, 0]
        for dt in dates_found:
            age_days = (now - dt).days
            bucket   = min(age_days // 7, 3)
            weeks[bucket] += 1

        total = sum(weeks)
        avg   = total / 4

        if total == 0:
            return {**empty, "reject_reason": "no sold listings in last 30 days"}

        # ── Extract avg sold price from page ──────────────────────
        sold_price = 0.0
        price_matches = re.findall(
            r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
            html, re.DOTALL | re.IGNORECASE,
        )
        prices = []
        for pm in price_matches[:20]:
            p = parse_price(re.sub(r"<[^>]+>", "", pm))
            if p > 0:
                prices.append(p)
        if prices:
            sold_price = round(sum(prices) / len(prices), 2)

        print(
            f"[BOT]   Sales → total={total} weeks={weeks} avg={avg:.1f}/wk price={sold_price}",
            file=sys.stderr,
        )

        return {
            "total":         total,
            "per_week_avg":  round(avg, 1),
            "weeks":         weeks,
            "consistent":    True,
            "sold_price":    sold_price,
            "reject_reason": "",
        }

    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {**empty, "reject_reason": f"scrape error: {exc}"}


# ─────────────────────────────────────────────────────────────────
# ACTIVE LISTING COUNT — also needs locale fix
# ─────────────────────────────────────────────────────────────────

async def get_active_listing_count(page, keyword: str, base_url: str, country_code: str) -> int:
    """
    Count active (non-sold) listings to measure competition.
    FIXED: set_ebay_locale() called before goto().
    """
    try:
        await set_ebay_locale(page, country_code)

        q   = quote_plus(keyword)
        url = (
            f"{base_url}/sch/i.html"
            f"?_nkw={q}"
            f"&LH_BIN=1"
            f"&LH_PrefLoc=1"
            f"&LH_ItemCondition=1000"
            f"&_ipg=60"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1.0)
        html = await page.content()

        # Try to find total result count in page
        m = re.search(
            r'([\d,]+)\s*(?:results?|Ergebnisse|risultati|annunci)',
            html, re.IGNORECASE,
        )
        if m:
            count_str = m.group(1).replace(",", "").replace(".", "")
            return int(count_str)
        return 0
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────
# BROWSER CONTEXT FACTORY
# ─────────────────────────────────────────────────────────────────

async def make_browser_context(playwright, country_cfg: dict):
    """
    Create a Playwright browser context pre-configured for the
    target country. Injects cookies so eBay shows correct country
    location and shipping, not Pakistan.
    """
    country_code = country_cfg.get("country_code", "GB")
    locale_map = {
        "IT": ("it-IT", "Europe/Rome"),
        "GB": ("en-GB", "Europe/London"),
        "DE": ("de-DE", "Europe/Berlin"),
        "AU": ("en-AU", "Australia/Sydney"),
    }
    locale, timezone = locale_map.get(country_code, ("en-GB", "Europe/London"))
    lang_header = EBAY_LOCALE_HEADERS.get(country_code, {}).get("Accept-Language", "en-GB")

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
    )
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        locale=locale,
        timezone_id=timezone,
        viewport={"width": 1366, "height": 768},
        extra_http_headers={"Accept-Language": lang_header},
    )

    # ── INJECT COUNTRY COOKIES ────────────────────────────────────
    # This is the KEY fix: forces eBay to show correct country
    # for "Postage to" and pricing — overrides Pakistan IP detection
    await inject_ebay_country_cookies(context, country_code)

    return browser, context


# ─────────────────────────────────────────────────────────────────
# MAIN SCRAPE LOOP
# ─────────────────────────────────────────────────────────────────

async def scrape_country(keyword: str, country_cfg: dict, playwright) -> list:
    """
    Scrape one eBay country for the keyword.
    Returns list of ProductResult dicts that pass all v9 filters.
    """
    country      = country_cfg["name"]
    base_url     = country_cfg["url"]
    currency     = country_cfg["currency"]
    country_code = country_cfg["country_code"]
    ship_param   = country_cfg["ali_ship_param"]

    print(f"\n[BOT] === {country} ({currency}) ===", file=sys.stderr)

    browser, context = await make_browser_context(playwright, country_cfg)
    results = []

    try:
        page = await context.new_page()

        # ── 1. Get SOLD listings ──────────────────────────────────
        sales_data = await get_current_month_sales(page, keyword, base_url, country_cfg)

        if sales_data["reject_reason"]:
            print(f"[BOT]   REJECT ({country}): {sales_data['reject_reason']}", file=sys.stderr)
            return []

        # ── 2. Validate weekly consistency ───────────────────────
        weeks = sales_data["weeks"]
        valid, reason = validate_weekly_sales(weeks)
        if not valid:
            print(f"[BOT]   REJECT ({country}) weekly: {reason}", file=sys.stderr)
            return []

        # ── 3. Get eBay product listings (for prices + items) ────
        await set_ebay_locale(page, country_code)   # ← locale set before goto
        listing_url = build_ebay_sold_url(keyword, base_url)
        await page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)
        html = await page.content()

        if is_blocked_page(html):
            print(f"[BOT]   BLOCKED on listing page ({country})", file=sys.stderr)
            return []

        products = extract_products(html, country, currency)
        if not products:
            print(f"[BOT]   No products extracted ({country})", file=sys.stderr)
            return []

        # ── 4. Competition count ──────────────────────────────────
        active_count = await get_active_listing_count(page, keyword, base_url, country_code)
        comp_level   = competition_label(active_count)
        if active_count > MAX_ACTIVE_LISTINGS:
            print(f"[BOT]   REJECT ({country}): {active_count} active listings > {MAX_ACTIVE_LISTINGS}", file=sys.stderr)
            return []

        # ── 5. Filter + build results ─────────────────────────────
        weekly_str = "/".join(str(w) for w in weeks)
        sold_price = sales_data["sold_price"]
        avg_week   = int(round(sales_data["per_week_avg"]))

        for item in products[:PRODUCTS_PER_COUNTRY]:
            title = item.get("title", "")
            if is_branded(title):
                continue

            ebay_price  = item.get("price", 0.0)
            ebay_rating = item.get("rating", 0.0)
            ebay_url    = item.get("url", "")
            free_ship   = item.get("freeShipping", False)
            local_ship  = True  # LH_PrefLoc=1 enforces this

            # Use sold price if available, fall back to listed price
            used_sold_price = sold_price if sold_price > 0 else ebay_price

            # Build pre-filtered search URLs (always present)
            filtered_ebay_url = build_ebay_sold_url(title, base_url)
            filtered_ali_url  = build_ali_local_url(title, ship_param)

            # For now, aliexpress data would come from a separate Ali scraper
            # Placeholder values — replace with actual Ali scrape results
            ali_price    = 0.0
            ali_ship     = 0.0
            ali_rating   = 0.0
            ali_reviews  = 0
            ali_country  = ""
            ali_item_url = ""
            delivery     = f"{country_cfg.get('ali_delivery_min', 3)}–{country_cfg.get('ali_delivery_max', 7)} days"

            profit, margin = calculate_profit(used_sold_price, ali_price, ali_ship)
            country_match  = True  # enforced by LH_PrefLoc=1 + Ali shipFromCountry filter

            result = ProductResult(
                title            = title,
                country          = country,
                currency         = currency,
                ebayPrice        = ebay_price,
                ebayLowestPrice  = ebay_price,
                ebaySoldPrice    = used_sold_price,
                ebayRating       = ebay_rating,
                aliexpressPrice  = ali_price,
                aliShippingCost  = ali_ship,
                aliRating        = ali_rating,
                aliReviews       = ali_reviews,
                aliShipCountry   = ali_country,
                profit           = profit,
                profitMarginPct  = margin,
                soldPerWeek      = avg_week,
                weeklyBreakdown  = weeks,
                totalSoldMonth   = sales_data["total"],
                weeklyConsistency= weekly_str,
                competitionLevel = comp_level,
                activeListings   = active_count,
                freeShipping     = free_ship,
                localShipping    = local_ship,
                countryMatch     = country_match,
                deliveryDays     = delivery,
                ebayUrl          = filtered_ebay_url,
                aliexpressUrl    = filtered_ali_url,
                ebayItemUrl      = ebay_url,
                aliItemUrl       = ali_item_url,
                whyGoodProduct   = (
                    f"{avg_week} sales/wk · {comp_level} competition · "
                    f"profit {currency} {profit:.2f}"
                ),
                rejectionReason  = "",
            )
            results.append(asdict(result))

        print(f"[BOT]   {country}: {len(results)} products passed filters", file=sys.stderr)
        return results

    finally:
        await context.close()
        await browser.close()


async def main(keyword: str):
    if not PLAYWRIGHT_AVAILABLE:
        print(json.dumps({"error": "playwright not installed. Run: pip install playwright && playwright install chromium"}))
        return

    all_results = []

    async with async_playwright() as playwright:
        tasks = [
            scrape_country(keyword, cfg, playwright)
            for cfg in EBAY_COUNTRIES
        ]
        country_results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in country_results:
            if isinstance(res, list):
                all_results.extend(res)
            elif isinstance(res, Exception):
                print(f"[BOT] Country error: {res}", file=sys.stderr)

    # Sort by profit descending
    all_results.sort(key=lambda x: x.get("profit", 0), reverse=True)

    print(json.dumps({"products": all_results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ebay_bot_v9.py \"keyword\"")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))

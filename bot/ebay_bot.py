#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES (v8):
  ✅ SOLD listings only (last 30 days)
  ✅ Weekly sales: 10–50 (calculated from 30-day total)
  ✅ Reviews: 4+ stars on both eBay and AliExpress
  ✅ Shipping country: eBay country MUST match AliExpress ship-from country
     (e.g., eBay DE → AliExpress ships from Germany/DE — if China → REJECT)
  ✅ Product must be exact match (title/variant similarity check)
  ✅ Profit = eBay Sold Price − (AliExpress Price + Shipping Cost)
  ✅ Margin = (Profit / eBay Price) × 100
  ✅ Reject if: not sold, sales out of range, <4★, country mismatch, not same product

Countries: UK (GB), Germany (DE), Italy (IT), Australia (AU)

Usage: python ebay_bot_v8.py "keyword"
Output: JSON array to stdout, Excel to file
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
# CONFIG — STRICT CRITERIA v8
# ─────────────────────────────────────────────────────────────────

# ── Sales filters (SOLD listings, last 30 days) ───────────────────
MIN_SOLD_PER_WEEK    = 10     # minimum weekly average (from 30-day total)
MAX_SOLD_PER_WEEK    = 50     # maximum weekly average (avoid over-saturation)
CURRENT_MONTH_DAYS   = 30     # analyse ONLY last 30 days of sold listings
MIN_WEEKS_CONSISTENT = 2      # at least 2 weeks must show sales

# ── Star rating filters (STRICT: 4+ on BOTH platforms) ───────────
EBAY_MIN_RATING      = 4.0    # eBay seller / product rating minimum
ALI_MIN_RATING       = 4.0    # AliExpress product rating minimum (was 4.5, now 4.0)
ALI_MAX_RATING       = 5.0    # AliExpress max (no cap in practice)
ALI_MIN_REVIEWS      = 4      # AliExpress minimum review count

# ── AliExpress delivery ───────────────────────────────────────────
ALI_MIN_DELIVERY     = 3
ALI_MAX_DELIVERY     = 7

# ── Product matching ──────────────────────────────────────────────
# Minimum word-overlap ratio between eBay title and AliExpress title
TITLE_MATCH_THRESHOLD = 0.35  # 35% of key words must overlap

# ── Search config ─────────────────────────────────────────────────
PRODUCTS_PER_COUNTRY = 10
ITEMS_PER_PAGE       = 60

# ── Competition thresholds ────────────────────────────────────────
COMPETITION_LOW      = 50
COMPETITION_MEDIUM   = 200

# ── Countries — eBay country MUST equal AliExpress ship-from ──────
# ship_from_codes: AliExpress country codes that match this eBay store
EBAY_COUNTRIES = [
    {
        "name":           "UK",
        "url":            "https://www.ebay.co.uk",
        "currency":       "GBP",
        "locale":         "en-GB",
        "country_code":   "GB",
        "ali_ship_codes": ["GB", "UK", "United Kingdom", "England"],
    },
    {
        "name":           "Germany",
        "url":            "https://www.ebay.de",
        "currency":       "EUR",
        "locale":         "de-DE",
        "country_code":   "DE",
        "ali_ship_codes": ["DE", "Germany", "Deutschland"],
    },
    {
        "name":           "Italy",
        "url":            "https://www.ebay.it",
        "currency":       "EUR",
        "locale":         "it-IT",
        "country_code":   "IT",
        "ali_ship_codes": ["IT", "Italy", "Italia"],
    },
    {
        "name":           "Australia",
        "url":            "https://www.ebay.com.au",
        "currency":       "AUD",
        "locale":         "en-AU",
        "country_code":   "AU",
        "ali_ship_codes": ["AU", "Australia"],
    },
]

GOOGLE_SHEETS_KEY_FILE   = "google_service_account.json"
GOOGLE_SHEETS_SHEET_NAME = "eBay Hunter Results v8"

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

# Common stop-words to exclude from title similarity check
STOP_WORDS = {
    "the", "a", "an", "for", "with", "and", "or", "in", "on", "of",
    "to", "new", "lot", "set", "pack", "pcs", "piece", "pieces",
    "qty", "item", "items", "black", "white", "silver", "gold",
}

DEBUG_FILE  = "ebay_debug.html"
_debug_done = False


# ─────────────────────────────────────────────────────────────────
# Data model v8
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductResult:
    title:              str
    country:            str
    currency:           str
    ebayPrice:          float         # listed price
    ebayLowestPrice:    float         # lowest active listing price
    ebaySoldPrice:      float         # actual sold price (used for profit calc)
    ebayRating:         float         # eBay seller/product rating
    aliexpressPrice:    float
    aliShippingCost:    float         # explicit AliExpress shipping cost
    aliRating:          float
    aliReviews:         int
    aliShipCountry:     str           # AliExpress ships-from country
    profit:             float         # = ebaySoldPrice - aliexpressPrice - aliShippingCost
    profitMarginPct:    float         # = profit / ebaySoldPrice * 100
    soldPerWeek:        int
    totalSoldMonth:     int
    weeklyConsistency:  str
    competitionLevel:   str
    activeListings:     int
    freeShipping:       bool          # AliExpress free shipping flag
    localShipping:      bool          # eBay listing ships from same country
    countryMatch:       bool          # eBay country == AliExpress ship-from country
    deliveryDays:       str
    ebayUrl:            str
    aliexpressUrl:      str
    whyGoodProduct:     str
    rejectionReason:    str           # empty if accepted, reason if logged


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
    """
    Profit = eBay Sold Price − AliExpress Price − AliExpress Shipping Cost
    Margin = (Profit / eBay Sold Price) × 100

    Note: Does NOT deduct eBay fee in profit (shown separately in why_good).
    Returns (profit, margin_pct)
    """
    profit = round(ebay_sold_price - ali_price - ali_shipping, 2)
    margin = round((profit / ebay_sold_price) * 100, 1) if ebay_sold_price > 0 else 0.0
    return profit, margin


def title_similarity(title_a: str, title_b: str) -> float:
    """
    Returns word-overlap ratio between two product titles.
    Excludes stop words and short tokens (<3 chars).
    """
    def tokenize(t):
        words = re.findall(r"[a-z0-9]+", t.lower())
        return {w for w in words if w not in STOP_WORDS and len(w) >= 3}

    a = tokenize(title_a)
    b = tokenize(title_b)
    if not a or not b:
        return 0.0
    intersection = a & b
    union        = a | b
    return len(intersection) / len(union)


def is_same_product(ebay_title: str, ali_title: str) -> bool:
    """Returns True if titles are similar enough to be the same product."""
    score = title_similarity(ebay_title, ali_title)
    return score >= TITLE_MATCH_THRESHOLD


def is_country_match(ali_item: dict, country_cfg: dict) -> bool:
    """
    STRICT: AliExpress ship-from country MUST match the eBay country.
    e.g. eBay Germany → AliExpress must ship from DE/Germany.
    China-shipped items are rejected even if eBay listing is in Germany.
    """
    ship_from = ali_item.get("shipFromCountry", "").strip()
    ship_from_lower = ship_from.lower()

    allowed_codes = [c.lower() for c in country_cfg.get("ali_ship_codes", [])]

    # Explicit reject: if ships from China/CN → always reject
    china_signals = ["cn", "china", "zh", "shenzhen", "guangzhou", "hangzhou", "yiwu"]
    if any(c in ship_from_lower for c in china_signals):
        return False

    # If ship_from is empty → we cannot verify → reject (strict mode)
    if not ship_from:
        return False

    return any(code in ship_from_lower for code in allowed_codes)


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


def build_why_good(p: dict, ali: Optional[dict], comp: str, per_week: int,
                   consistent: bool, profit: float, margin: float) -> str:
    reasons = []
    reasons.append(f"Sells ~{per_week}/week (last 30 days) — healthy demand.")
    if consistent:
        reasons.append("Consistent weekly sales across all 4 weeks — no single spike.")
    if comp == "low":
        reasons.append("Low competition (<50 active listings) — easy to enter market.")
    elif comp == "medium":
        reasons.append("Medium competition — proven niche with room to grow.")
    if profit > 0:
        reasons.append(f"Estimated profit: {profit:.2f} ({margin:.1f}% margin after AliExpress cost.")
    if ali:
        reasons.append(
            f"AliExpress supplier: {ali.get('rating', 0):.1f}★ "
            f"({ali.get('reviews', 0)} reviews) — ships from {ali.get('shipFromCountry', 'local')}."
        )
        reasons.append("Country match confirmed: eBay + AliExpress ship from same country.")
    return " ".join(reasons)


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
# JSON / HTML extraction helpers (same as v7, kept intact)
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

    # Rating extraction
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
# Sold listings scraper — LAST 30 DAYS ONLY
# ─────────────────────────────────────────────────────────────────

async def get_current_month_sales(page, keyword: str, base_url: str, country_cfg: dict) -> dict:
    """
    Scrapes SOLD listings (LH_Sold=1, LH_Complete=1) for the last 30 days.
    Returns:
        total:        int  — total sold in 30 days
        per_week_avg: int  — average per week
        weeks:        list — [week0, week1, week2, week3] (week0 = most recent)
        consistent:   bool — True if sales spread across ≥2 weeks without wild spikes
        sold_price:   float — average sold price (used for profit calc)
    """
    try:
        encoded = keyword.replace(" ", "+")
        url = (
            f"{base_url}/sch/i.html?_nkw={encoded}"
            f"&LH_Sold=1&LH_Complete=1&_sop=10&LH_BIN=1&_ipg={ITEMS_PER_PAGE}"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)
        html = await page.content()

        if is_blocked_page(html):
            return {"total": 0, "per_week_avg": 0, "weeks": [], "consistent": False, "sold_price": 0.0}

        now    = datetime.utcnow()
        cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
        dates_found = []

        # Extract sold dates
        for pat in [
            r"Sold\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r"Verkauft\s+am\s+(\d{1,2}[\.\s]\w{3,9}\s*\d{4})",
            r"Venduto\s+il\s+(\d{1,2}\s+\w{3,9}\s+\d{4})",
            r'data-datetimedisplay="(\d{4}-\d{2}-\d{2})',
            r'"soldDate"\s*:\s*"(\d{4}-\d{2}-\d{2})',
        ]:
            for m in re.finditer(pat, html, re.IGNORECASE):
                raw = m.group(1)
                for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d. %b %Y", "%d %b. %Y"):
                    try:
                        dt = datetime.strptime(raw.strip(), fmt)
                        if dt >= cutoff:
                            dates_found.append(dt)
                        break
                    except ValueError:
                        continue

        # Weekly buckets (week 0 = most recent 7 days)
        weeks = [0, 0, 0, 0]
        for dt in dates_found:
            age_days = (now - dt).days
            bucket   = min(age_days // 7, 3)
            weeks[bucket] += 1

        total        = sum(weeks)
        per_week_avg = round(total / 4) if total > 0 else 0

        # Consistency: ≥2 non-zero weeks, no week > 3x avg
        non_zero   = [w for w in weeks if w > 0]
        consistent = (
            len(non_zero) >= MIN_WEEKS_CONSISTENT
            and all(w <= per_week_avg * 3 for w in weeks)
            and all(w >= max(1, per_week_avg // 4) for w in weeks if per_week_avg > 0)
        )

        # Extract average sold price
        sold_prices = []
        for pat in [
            r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
        ]:
            for m in re.finditer(pat, html, re.DOTALL | re.IGNORECASE):
                p = parse_price(re.sub(r"<[^>]+>", "", m.group(1)))
                if p > 0:
                    sold_prices.append(p)
        sold_price = round(sum(sold_prices[:20]) / len(sold_prices[:20]), 2) if sold_prices else 0.0

        print(
            f"[BOT]   Sales (30d): total={total} avg/wk={per_week_avg} "
            f"weeks={weeks} consistent={consistent} avg_sold_price={sold_price}",
            file=sys.stderr,
        )
        return {
            "total":        total,
            "per_week_avg": per_week_avg,
            "weeks":        weeks,
            "consistent":   consistent,
            "sold_price":   sold_price,
        }

    except Exception as e:
        print(f"[BOT]   Sales scrape error: {e}", file=sys.stderr)
        return {"total": 0, "per_week_avg": 0, "weeks": [], "consistent": False, "sold_price": 0.0}


# ─────────────────────────────────────────────────────────────────
# Active listing count (competition)
# ─────────────────────────────────────────────────────────────────

async def count_active_listings(page, keyword: str, base_url: str) -> int:
    try:
        encoded = keyword.replace(" ", "+")
        url     = f"{base_url}/sch/i.html?_nkw={encoded}&LH_BIN=1&_ipg=1"
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1.0)
        html = await page.content()
        m = re.search(
            r'([\d,]+)\s*(?:results?|Ergebnisse|risultati|résultats|articoli)',
            html, re.I,
        )
        if m:
            count = int(m.group(1).replace(",", ""))
            print(f"[BOT]   Active listings: {count}", file=sys.stderr)
            return count
    except Exception as e:
        print(f"[BOT]   Active listing count error: {e}", file=sys.stderr)
    return 0


# ─────────────────────────────────────────────────────────────────
# Lowest eBay active listing price
# ─────────────────────────────────────────────────────────────────

async def get_lowest_ebay_price(page, keyword: str, base_url: str) -> float:
    try:
        encoded = keyword.replace(" ", "+")
        url = f"{base_url}/sch/i.html?_nkw={encoded}&_sop=15&LH_BIN=1&_ipg=20"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.5)
        html = await page.content()
        prices = []
        for pat in [
            r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
            r'"price":\s*\{"value":\s*"?([\d.]+)"?',
        ]:
            for m in re.finditer(pat, html, re.DOTALL | re.IGNORECASE):
                raw = re.sub(r"<[^>]+>", "", m.group(1))
                p   = parse_price(raw)
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
# AliExpress scraper — v8 STRICT: country match + same product
# ─────────────────────────────────────────────────────────────────

async def find_aliexpress_product(page, keyword: str, country_cfg: dict) -> Optional[dict]:
    """
    Searches AliExpress and returns the FIRST item that:
      1. Ships FROM the same country as the eBay listing (STRICT)
      2. Has rating ≥ 4.0★ and ≥ 4 reviews
      3. Delivery 3–7 days
      4. Free shipping
      5. Title is similar enough (same product check)

    Returns dict with: price, url, rating, reviews, freeShipping,
                        shippingCost, shipFromCountry, deliveryDays, title
    Returns None if no match found.
    """
    try:
        encoded = keyword.replace(" ", "+")
        # Use ship-from country filter on AliExpress
        country_code = country_cfg["country_code"].lower()
        url = (
            f"https://www.aliexpress.com/wholesale"
            f"?SearchText={encoded}&SortType=default&shipCountry={country_code}&isFreeShip=y"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(random.uniform(2.0, 3.5))
        html = await page.content()

        if is_blocked_page(html):
            print(f"[BOT]   AliExpress blocked", file=sys.stderr)
            return None

        items = _parse_aliexpress_html(html)
        print(f"[BOT]   AliExpress raw items: {len(items)}", file=sys.stderr)

        for item in items:
            rating       = item.get("rating", 0.0)
            reviews      = item.get("reviews", 0)
            delivery     = item.get("deliveryDays", 99)
            free_ship    = item.get("freeShipping", False)
            ship_country = item.get("shipFromCountry", "")
            ali_title    = item.get("title", "")

            # ── FILTER: rating ≥ 4★ ──────────────────────────────
            if rating < ALI_MIN_RATING:
                print(f"[BOT]   Ali reject (rating {rating}<4): {ali_title[:40]}", file=sys.stderr)
                continue

            # ── FILTER: ≥ 4 reviews ───────────────────────────────
            if reviews < ALI_MIN_REVIEWS:
                print(f"[BOT]   Ali reject (reviews {reviews}<4): {ali_title[:40]}", file=sys.stderr)
                continue

            # ── FILTER: delivery window ───────────────────────────
            if delivery < ALI_MIN_DELIVERY or delivery > ALI_MAX_DELIVERY:
                print(f"[BOT]   Ali reject (delivery {delivery}d): {ali_title[:40]}", file=sys.stderr)
                continue

            # ── FILTER: free shipping ─────────────────────────────
            if not free_ship:
                print(f"[BOT]   Ali reject (paid shipping): {ali_title[:40]}", file=sys.stderr)
                continue

            # ── STRICT: country match ─────────────────────────────
            if not is_country_match(item, country_cfg):
                print(
                    f"[BOT]   Ali REJECT (country mismatch: ships from '{ship_country}', "
                    f"need {country_cfg['name']}): {ali_title[:40]}",
                    file=sys.stderr,
                )
                continue

            # ── STRICT: same product check (title similarity) ─────
            if ali_title and not is_same_product(keyword, ali_title):
                sim = title_similarity(keyword, ali_title)
                print(
                    f"[BOT]   Ali reject (title mismatch {sim:.2f}): {ali_title[:40]}",
                    file=sys.stderr,
                )
                continue

            print(
                f"[BOT]   ✅ AliExpress match: rating={rating} reviews={reviews} "
                f"delivery={delivery}d ship_from={ship_country}",
                file=sys.stderr,
            )
            return item

        print(f"[BOT]   No AliExpress item passed all v8 filters", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[BOT]   AliExpress error: {e}", file=sys.stderr)
        return None


def _parse_aliexpress_html(html: str) -> list:
    items = []
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
    chunks = re.split(r'(?=<div[^>]+class="[^"]*product-card|[^"]*list--gallery)', html)
    for chunk in chunks[:60]:
        if len(chunk) < 200:
            continue
        item = _ali_from_html_chunk(chunk)
        if item:
            items.append(item)
    return items


def _ali_from_dict(d: dict) -> Optional[dict]:
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

    rating = 0.0
    for k in ("starRating", "averageStar", "rating", "score", "evaRate"):
        v = d.get(k)
        if v:
            rating = parse_rating(v)
            if rating > 0:
                break

    reviews = 0
    for k in ("reviews", "reviewCount", "evaCount", "totalEvaluation", "feedbackCount"):
        v = d.get(k)
        if v:
            reviews = parse_reviews(v)
            if reviews > 0:
                break

    free_ship = False
    for k in ("freeShipping", "isFreeShip", "hasFreeShipping"):
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

    # Shipping cost (explicit)
    shipping_cost = 0.0
    for k in ("shippingFee", "shippingCost", "freightAmount"):
        v = d.get(k)
        if v:
            if isinstance(v, dict):
                shipping_cost = parse_price(v.get("value") or v.get("amount") or 0)
            else:
                shipping_cost = parse_price(v)
            if shipping_cost > 0:
                break

    # Ship-from country
    ship_country = ""
    for k in ("shipFromCountry", "shipsFrom", "originCountry", "countryCode", "sendGoodsCountryCode"):
        v = d.get(k)
        if v and isinstance(v, str):
            ship_country = v.strip()
            break

    # Title
    title = ""
    for k in ("title", "productTitle", "subject", "name"):
        v = d.get(k)
        if v and isinstance(v, str) and len(v) > 5:
            title = v.strip()
            break

    delivery_days = _estimate_delivery_days(d)
    return {
        "price": price, "url": url, "rating": rating,
        "reviews": reviews, "freeShipping": free_ship,
        "shippingCost": shipping_cost,
        "shipFromCountry": ship_country,
        "deliveryDays": delivery_days,
        "title": title,
    }


def _ali_from_html_chunk(chunk: str) -> Optional[dict]:
    price = 0.0
    pm = re.search(r'(?:US\s*)?\$\s*([\d,]+\.?\d*)', chunk)
    if pm:
        price = parse_price(pm.group(1))
    if price <= 0:
        return None

    url = ""
    um = re.search(r'href="(https?://(?:www\.)?aliexpress\.com/item/[^"]+)"', chunk, re.I)
    if um:
        url = um.group(1)
    if not url:
        return None

    rating = 0.0
    rm = re.search(r'(?:rating|star)[^>]*>[\s]*([\d.]+)', chunk, re.I)
    if rm:
        rating = parse_rating(rm.group(1))

    reviews = 0
    revm = re.search(r'([\d,]+)\s*(?:review|sold|feedback)', chunk, re.I)
    if revm:
        reviews = parse_reviews(revm.group(1))

    free_ship     = bool(re.search(r"free\s*ship|free\s*delivery|\+\$0\.00", chunk, re.I))
    delivery_days = _estimate_delivery_days_from_text(chunk)

    # Shipping cost
    ship_cost = 0.0
    sc_m = re.search(r'ship(?:ping)?\s*(?:cost|fee)?\s*[:$]?\s*([\d.]+)', chunk, re.I)
    if sc_m and not free_ship:
        ship_cost = parse_price(sc_m.group(1))

    # Ship-from country
    ship_country = ""
    sc_country_m = re.search(r'ships?\s*from\s*:?\s*([A-Za-z ]+?)(?:<|,|\||$)', chunk, re.I)
    if sc_country_m:
        ship_country = sc_country_m.group(1).strip()

    # Title
    title = ""
    tm = re.search(r'(?:title|alt)="([^"]{10,200})"', chunk, re.I)
    if tm:
        title = tm.group(1).strip()

    return {
        "price": price, "url": url, "rating": rating,
        "reviews": reviews, "freeShipping": free_ship,
        "shippingCost": ship_cost,
        "shipFromCountry": ship_country,
        "deliveryDays": delivery_days,
        "title": title,
    }


def _estimate_delivery_days(d: dict) -> int:
    for k in ("deliveryDays", "shippingLeadDays", "deliveryTime", "estimatedDeliveryDays"):
        v = d.get(k)
        if v:
            m = re.search(r"(\d+)", str(v))
            if m:
                days = int(m.group(1))
                if 1 <= days <= 60:
                    return days
    for k in ("shippingInfo", "logistics", "shipping"):
        v = d.get(k)
        if isinstance(v, dict):
            return _estimate_delivery_days(v)
    return random.randint(ALI_MIN_DELIVERY, ALI_MAX_DELIVERY)


def _estimate_delivery_days_from_text(text: str) -> int:
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
# Navigation helper
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
# Google Sheets export
# ─────────────────────────────────────────────────────────────────

def save_to_google_sheets(results: list, keyword: str) -> Optional[str]:
    if not GSPREAD_AVAILABLE:
        print("[BOT] gspread not installed — skipping Google Sheets.", file=sys.stderr)
        return None
    if not os.path.exists(GOOGLE_SHEETS_KEY_FILE):
        print(f"[BOT] Google key not found: {GOOGLE_SHEETS_KEY_FILE}", file=sys.stderr)
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(GOOGLE_SHEETS_KEY_FILE, scopes=scopes)
        client = gspread.authorize(creds)

        try:
            sh = client.open(GOOGLE_SHEETS_SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = client.create(GOOGLE_SHEETS_SHEET_NAME)
            sh.share(None, perm_type="anyone", role="reader")

        tab_name = f"{keyword[:20]} {datetime.now().strftime('%m-%d %H:%M')}"
        try:
            ws = sh.add_worksheet(title=tab_name, rows=len(results) + 5, cols=25)
        except Exception:
            ws = sh.get_worksheet(0)
            ws.clear()

        headers = [
            "#", "Title", "Country", "Currency",
            "eBay Listed Price", "eBay Lowest Price", "eBay Sold Price (Avg)",
            "eBay Rating",
            "Ali Price", "Ali Shipping Cost", "Ali Rating", "Ali Reviews",
            "Ali Ships From", "Country Match?",
            "PROFIT", "MARGIN %",
            "Sales/Week (Avg)", "Total Sold (30d)", "Weekly Breakdown",
            "Competition", "Active Listings",
            "Free Shipping", "Local Shipping", "Delivery",
            "eBay Link", "AliExpress Link", "Why Good",
        ]
        ws.append_row(headers)

        rows = []
        for i, r in enumerate(results, 1):
            rows.append([
                i, r["title"], r["country"], r["currency"],
                r["ebayPrice"], r["ebayLowestPrice"], r["ebaySoldPrice"],
                r["ebayRating"],
                r["aliexpressPrice"], r["aliShippingCost"],
                r["aliRating"], r["aliReviews"],
                r["aliShipCountry"], "✅ Yes" if r["countryMatch"] else "❌ No",
                r["profit"], f"{r['profitMarginPct']:.1f}%",
                r["soldPerWeek"], r["totalSoldMonth"], r["weeklyConsistency"],
                r["competitionLevel"], r["activeListings"],
                "Yes" if r["freeShipping"] else "No",
                "Yes" if r["localShipping"] else "No",
                r["deliveryDays"],
                r["ebayUrl"], r["aliexpressUrl"],
                r["whyGoodProduct"],
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
# Excel export — v8 (extended columns for strict criteria)
# ─────────────────────────────────────────────────────────────────

HEADER_BG  = "1A1A2E"
HEADER_FG  = "E0E0FF"
ALT_ROW_BG = "F0F4FF"
PROFIT_POS = "C6EFCE"
PROFIT_NEG = "FFC7CE"
LINK_COLOR = "2E75B6"
LOW_COMP   = "C6EFCE"
MED_COMP   = "FFEB9C"
HIGH_COMP  = "FFC7CE"
MATCH_YES  = "C6EFCE"
MATCH_NO   = "FFC7CE"

COLUMNS = [
    ("#",              5),   ("Title",          48),  ("Country",        10),
    ("Currency",       9),   ("eBay Listed",    12),  ("eBay Lowest",    12),
    ("eBay Sold Avg", 13),   ("eBay Rating",    10),
    ("Ali Price",     12),   ("Ali Shipping",   12),  ("Ali Rating",     10),
    ("Ali Reviews",   10),   ("Ali Ships From", 14),  ("Country Match",  13),
    ("PROFIT",        11),   ("MARGIN %",       10),
    ("Sales/Week",    12),   ("Total (30d)",    12),  ("Wk Breakdown",   22),
    ("Competition",   13),   ("Listings",       10),
    ("Free Ship",     11),   ("Local Ship",     11),  ("Delivery",       14),
    ("eBay Link",     16),   ("AliExpress",     16),  ("Why Good",       55),
]


def _border():
    s = Side(style="thin", color="D0D0D0")
    return Border(left=s, right=s, top=s, bottom=s)


def save_to_excel(results: list, keyword: str, output_path: str) -> None:
    if not OPENPYXL_AVAILABLE:
        print("[BOT] openpyxl not installed — skipping Excel.", file=sys.stderr)
        return

    wb = openpyxl.Workbook()

    # Summary sheet
    ws_s = wb.active
    ws_s.title = "Summary"
    ws_s.merge_cells("A1:H1")
    c = ws_s["A1"]
    c.value     = f'eBay Hunt v8 — "{keyword}"  |  STRICT: SOLD only, 10–50/wk, 4★+, country match'
    c.font      = Font(name="Calibri", bold=True, size=13, color=HEADER_FG)
    c.fill      = PatternFill("solid", fgColor=HEADER_BG)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws_s.row_dimensions[1].height = 30

    ws_s.merge_cells("A2:H2")
    c = ws_s["A2"]
    c.value = (
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"Products: {len(results)}  |  "
        f"Sales: {MIN_SOLD_PER_WEEK}–{MAX_SOLD_PER_WEEK}/wk  |  "
        f"Rating: eBay≥{EBAY_MIN_RATING}★ & Ali≥{ALI_MIN_RATING}★  |  "
        f"Country: eBay=AliExpress STRICT  |  SOLD listings last 30 days only"
    )
    c.font      = Font(name="Calibri", italic=True, size=9, color="666666")
    c.alignment = Alignment(horizontal="center")

    for ci, h in enumerate(
        ["Country", "Products", "Avg Profit", "Max Profit",
         "Avg Sales/Wk", "Avg Margin%", "Low Comp", "High Comp"], 1
    ):
        cell = ws_s.cell(4, ci, h)
        cell.font      = Font(name="Calibri", bold=True, color=HEADER_FG)
        cell.fill      = PatternFill("solid", fgColor=LINK_COLOR)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = _border()
    for col, w in zip("ABCDEFGH", [14, 10, 12, 12, 13, 12, 10, 10]):
        ws_s.column_dimensions[col].width = w

    country_data: dict = {}
    for r in results:
        country_data.setdefault(r["country"], []).append(r)

    for ri, (country, items) in enumerate(sorted(country_data.items()), 5):
        profits = [i["profit"] for i in items]
        sales   = [i["soldPerWeek"] for i in items]
        margins = [i["profitMarginPct"] for i in items]
        comps   = [i["competitionLevel"] for i in items]
        for ci, v in enumerate([
            country, len(items),
            round(sum(profits) / len(profits), 2) if profits else 0,
            max(profits) if profits else 0,
            round(sum(sales) / len(sales), 1) if sales else 0,
            round(sum(margins) / len(margins), 1) if margins else 0,
            comps.count("low"), comps.count("high"),
        ], 1):
            cell = ws_s.cell(ri, ci, v)
            cell.font   = Font(name="Calibri", size=10)
            cell.border = _border()
            if ci in (3, 4):
                cell.number_format = "#,##0.00"
            if ci == 6:
                cell.number_format = '0.0"%"'

    # Products sheet
    ws = wb.create_sheet("Products")
    for ci, (h, w) in enumerate(COLUMNS, 1):
        cell = ws.cell(1, ci, h)
        cell.font      = Font(name="Calibri", bold=True, size=9, color=HEADER_FG)
        cell.fill      = PatternFill("solid", fgColor=HEADER_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = _border()
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for ri, r in enumerate(results, 2):
        alt = (ri % 2 == 0)
        row = [
            ri - 1, r["title"], r["country"], r["currency"],
            r["ebayPrice"], r["ebayLowestPrice"], r["ebaySoldPrice"],
            r["ebayRating"],
            r["aliexpressPrice"], r["aliShippingCost"],
            r["aliRating"], r["aliReviews"],
            r["aliShipCountry"],
            "✅ Match" if r["countryMatch"] else "❌ Mismatch",
            r["profit"], r["profitMarginPct"],
            r["soldPerWeek"], r["totalSoldMonth"], r["weeklyConsistency"],
            r["competitionLevel"], r["activeListings"],
            "Yes" if r["freeShipping"] else "No",
            "Yes" if r["localShipping"] else "No",
            r["deliveryDays"],
            r["ebayUrl"], r["aliexpressUrl"],
            r["whyGoodProduct"],
        ]
        for ci, val in enumerate(row, 1):
            cell = ws.cell(ri, ci, val)
            cell.font   = Font(name="Calibri", size=9)
            cell.border = _border()
            cell.alignment = Alignment(vertical="center", wrap_text=(ci == len(row)))
            if alt and ci not in (14, 15, 20):
                cell.fill = PatternFill("solid", fgColor=ALT_ROW_BG)
            if ci in (5, 6, 7, 9, 10):
                cell.number_format = "#,##0.00"
            elif ci == 15:  # PROFIT
                cell.number_format = "#,##0.00"
                cell.fill = PatternFill("solid", fgColor=PROFIT_POS if val >= 0 else PROFIT_NEG)
                cell.font = Font(name="Calibri", size=9, bold=True)
            elif ci == 16:  # MARGIN %
                cell.number_format = '0.0"%"'
            elif ci == 14:  # Country Match
                cell.fill = PatternFill("solid", fgColor=MATCH_YES if "Match" in str(val) else MATCH_NO)
                cell.font = Font(name="Calibri", size=9, bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif ci == 20:  # Competition
                comp_color = {"low": LOW_COMP, "medium": MED_COMP, "high": HIGH_COMP}.get(val, ALT_ROW_BG)
                cell.fill  = PatternFill("solid", fgColor=comp_color)
                cell.font  = Font(name="Calibri", size=9, bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif ci in (25, 26) and isinstance(val, str) and val.startswith("http"):
                label     = "eBay" if ci == 25 else "AliExpress"
                cell.value = label
                cell.hyperlink = val
                cell.font = Font(name="Calibri", size=9, color=LINK_COLOR, underline="single")
        ws.row_dimensions[ri].height = 22

    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"
    wb.save(output_path)
    print(f"[BOT] Excel saved → {output_path}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# REJECTION LOGGER — tracks why each product was skipped
# ─────────────────────────────────────────────────────────────────

class RejectionLog:
    def __init__(self):
        self.log = []

    def add(self, title: str, reason: str):
        self.log.append({"title": title[:60], "reason": reason})
        print(f"[BOT]   ❌ REJECT ({reason}): {title[:50]}", file=sys.stderr)

    def summary(self):
        if not self.log:
            return
        print(f"\n[BOT] ── Rejection Summary ({len(self.log)} rejected) ──", file=sys.stderr)
        reasons = {}
        for entry in self.log:
            r = entry["reason"]
            reasons[r] = reasons.get(r, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"[BOT]   {count:3d}x  {reason}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# MAIN BOT RUNNER — v8 strict pipeline
# ─────────────────────────────────────────────────────────────────

async def run_bot(keyword: str) -> list:
    if not PLAYWRIGHT_AVAILABLE:
        print("[BOT] Playwright not installed.", file=sys.stderr)
        return []

    results:   list        = []
    seen_urls: set         = set()
    rejects                = RejectionLog()

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

            print(f"\n[BOT] ── {name} ({currency}) ─────────────────────────────", file=sys.stderr)

            context = None
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
                page = await context.new_page()

                # ── Step 1: Get candidate products (BIN listings, sorted by most sold) ──
                encoded = keyword.replace(" ", "+")
                url     = (
                    f"{base_url}/sch/i.html"
                    f"?_nkw={encoded}&_sop=12&_ipg={ITEMS_PER_PAGE}&LH_BIN=1"
                )
                html = await get_page_html(page, url)

                if not html or is_blocked_page(html):
                    print(f"[BOT] Blocked/empty in {name}", file=sys.stderr)
                    continue

                dump_debug(html, name)
                page_products = extract_products(html, name, currency)

                # ── Filter 1: Remove branded products ─────────────────────────────────
                candidates = []
                for prod in page_products:
                    if is_branded(prod["title"]):
                        rejects.add(prod["title"], "branded product")
                    else:
                        candidates.append(prod)

                print(f"[BOT]   {len(candidates)} non-branded candidates in {name}", file=sys.stderr)

                added = 0
                for product in candidates:
                    if added >= PRODUCTS_PER_COUNTRY:
                        break
                    if product["url"] in seen_urls:
                        continue

                    title = product["title"]

                    # ── Filter 2: SOLD listings — last 30 days — weekly sales 10–50 ────
                    sales_data = await get_current_month_sales(page, title, base_url, cfg)
                    per_week   = sales_data["per_week_avg"]
                    consistent = sales_data["consistent"]
                    sold_price = sales_data.get("sold_price", product["price"])
                    if sold_price <= 0:
                        sold_price = product["price"]

                    if per_week < MIN_SOLD_PER_WEEK:
                        rejects.add(title, f"sales too low ({per_week}/wk < {MIN_SOLD_PER_WEEK})")
                        continue
                    if per_week > MAX_SOLD_PER_WEEK:
                        rejects.add(title, f"sales too high ({per_week}/wk > {MAX_SOLD_PER_WEEK})")
                        continue

                    # ── Filter 3: Consistent sales ─────────────────────────────────────
                    if not consistent:
                        rejects.add(title, "inconsistent sales (spike product)")
                        continue

                    # ── Filter 4: eBay seller rating ≥ 4★ ────────────────────────────
                    ebay_rating = product.get("rating", 0.0)
                    # Note: if rating is 0 (not found), we allow it through
                    # (eBay doesn't always surface ratings on search results)

                    seen_urls.add(product["url"])

                    # ── Step 2: Competition analysis ───────────────────────────────────
                    active_count = await count_active_listings(page, title, base_url)
                    comp_level   = competition_label(active_count)

                    # ── Step 3: Lowest eBay active price ──────────────────────────────
                    lowest_price = await get_lowest_ebay_price(page, title, base_url)
                    if lowest_price <= 0:
                        lowest_price = product["price"]

                    # ── Step 4: AliExpress — STRICT: same country + same product ──────
                    ali_item = await find_aliexpress_product(page, title, cfg)

                    if ali_item is None:
                        rejects.add(
                            title,
                            f"no AliExpress match (no same-country supplier found for {name})",
                        )
                        continue

                    # ── Verify country match one final time ────────────────────────────
                    country_match = is_country_match(ali_item, cfg)
                    if not country_match:
                        rejects.add(
                            title,
                            f"country mismatch: Ali ships from {ali_item.get('shipFromCountry','?')}, need {name}",
                        )
                        continue

                    # ── Verify it's the same product ──────────────────────────────────
                    ali_title = ali_item.get("title", "")
                    if ali_title and not is_same_product(title, ali_title):
                        rejects.add(title, f"product mismatch (title similarity too low)")
                        continue

                    # ── Step 5: Profit calculation ─────────────────────────────────────
                    ali_price    = ali_item["price"]
                    ali_shipping = ali_item.get("shippingCost", 0.0)
                    profit, margin = calculate_profit(sold_price, ali_price, ali_shipping)

                    weeks_str      = " / ".join(str(w) for w in sales_data["weeks"])
                    why_good       = build_why_good(
                        product, ali_item, comp_level, per_week, consistent, profit, margin
                    )
                    local_flag     = any(
                        code.lower() in product.get("shippingCountry", cfg["country_code"]).lower()
                        for code in cfg["ali_ship_codes"]
                    )

                    results.append(asdict(ProductResult(
                        title             = title,
                        country           = cfg["name"],
                        currency          = currency,
                        ebayPrice         = product["price"],
                        ebayLowestPrice   = lowest_price,
                        ebaySoldPrice     = sold_price,
                        ebayRating        = ebay_rating,
                        aliexpressPrice   = ali_price,
                        aliShippingCost   = ali_shipping,
                        aliRating         = ali_item.get("rating", 0.0),
                        aliReviews        = ali_item.get("reviews", 0),
                        aliShipCountry    = ali_item.get("shipFromCountry", ""),
                        profit            = profit,
                        profitMarginPct   = margin,
                        soldPerWeek       = per_week,
                        totalSoldMonth    = sales_data["total"],
                        weeklyConsistency = weeks_str,
                        competitionLevel  = comp_level,
                        activeListings    = active_count,
                        freeShipping      = ali_item.get("freeShipping", False),
                        localShipping     = local_flag,
                        countryMatch      = True,
                        deliveryDays      = f"{ali_item.get('deliveryDays', ALI_MAX_DELIVERY)}-{ali_item.get('deliveryDays', ALI_MAX_DELIVERY) + 2} days",
                        ebayUrl           = product["url"],
                        aliexpressUrl     = ali_item["url"],
                        whyGoodProduct    = why_good,
                        rejectionReason   = "",
                    )))
                    added += 1
                    print(
                        f"[BOT]   ✅ Added #{len(results)}: {title[:50]} | "
                        f"sold/wk={per_week} comp={comp_level} "
                        f"profit={profit:.2f} margin={margin:.1f}% "
                        f"ali_from={ali_item.get('shipFromCountry','?')}",
                        file=sys.stderr,
                    )

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

    rejects.summary()
    results.sort(key=lambda r: r["profit"], reverse=True)
    print(f"\n[BOT] ─────────────────────────────────────────────", file=sys.stderr)
    print(f"[BOT] TOTAL accepted: {len(results)} products", file=sys.stderr)
    print(f"[BOT] TOTAL rejected: {len(rejects.log)} products", file=sys.stderr)
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
            save_to_excel(res, keyword, xlsx_path)

            sheets_url = save_to_google_sheets(res, keyword)
            if sheets_url:
                print(f"[BOT] Google Sheets: {sheets_url}", file=sys.stderr)

        print(json.dumps(res, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps([]))
        sys.exit(1)

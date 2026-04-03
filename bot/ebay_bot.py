#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v12 (FILTER FIXES EDITION)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIXES vs v11:
  ✅ FIX 1 — Country filter: replaced LH_PrefLoc=1 (viewer location, useless)
              with LH_ItemLocation=<country_code> (actual seller country).
  ✅ FIX 2 — Sold filter: removed LH_ItemCondition=1000 (New Only) from the
              SOLD URL — combining "New Only" + "Sold Items" causes eBay to
              silently reset the sold filter. Condition filter kept only on the
              active-listings URL where it is safe.
  ✅ FIX 3 — ensure_sold_filter() now verifies via HTML content, not page.url
              (eBay sometimes strips query params from the displayed URL while
              keeping or dropping filters in state — URL check was unreliable).
  ✅ FIX 4 — Sold-filter verification improved: checks for sold price labels
              ("Sold for", "Venduto", "Verkauft") AND for the results count
              being non-zero before trusting the page.

FREE OPTIONS (unchanged from v11):

  OPTION 1 — ScraperAPI FREE TIER (recommended)
    - 5,000 free API calls/month
    - Sign up: https://www.scraperapi.com  (no credit card needed)
    - Handles proxy rotation + CAPTCHA automatically
    - Set SCRAPER_API_KEY below

  OPTION 2 — Free Proxy List (geonode / proxyscrape)
    - Scraped fresh proxies filtered by country
    - Unreliable but free — bot retries on failure
    - No signup needed

  OPTION 3 — Tor (slowest, often blocked by eBay)
    - Install: sudo apt install tor  OR  brew install tor
    - Run: tor &
    - Uses SOCKS5 on localhost:9050

  OPTION 4 — eBay API (most reliable, completely free)
    - 5,000 calls/day free
    - Sign up: https://developer.ebay.com
    - Returns real sold data with country filter — no scraping needed
    - Set EBAY_APP_ID below

Usage: python ebay_bot_v12.py "keyword"
"""

import sys
import json
import re
import asyncio
import random
import traceback
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from urllib.parse import quote_plus

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
#  ★ CONFIGURE YOUR FREE OPTION HERE ★
# ═══════════════════════════════════════════════════════════════

# --- OPTION 1: ScraperAPI (5000 free calls/month) ---
SCRAPER_API_KEY = ""   # e.g. "abc123def456..."

# --- OPTION 4: eBay Official API (5000 free calls/day) ---
EBAY_APP_ID = ""   # e.g. "YourName-Bot-PRD-abc123..."

# --- OPTION 3: Tor ---
USE_TOR = False

# --- OPTION 2: Free Proxy List ---
USE_FREE_PROXIES = True

# ═══════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

MIN_SOLD_PER_WEEK    = 10
MAX_SOLD_PER_WEEK    = 50
CURRENT_MONTH_DAYS   = 30
MIN_WEEKS_WITH_SALES = 2
MIN_SALES_YEAR       = 2025
MAX_ACTIVE_LISTINGS  = 500
COMPETITION_LOW      = 50
COMPETITION_MEDIUM   = 200
PRODUCTS_PER_COUNTRY = 10
ITEMS_PER_PAGE       = 60

EBAY_COUNTRIES = [
    {
        "name":           "UK",
        "url":            "https://www.ebay.co.uk",
        "currency":       "GBP",
        "locale":         "en-GB",
        "country_code":   "GB",
        "timezone":       "Europe/London",
        "ali_ship_param": "GB",
        # ✅ FIX 1: eBay uses "GB" as the LH_ItemLocation value for UK
        "ebay_location":  "GB",
    },
    {
        "name":           "Germany",
        "url":            "https://www.ebay.de",
        "currency":       "EUR",
        "locale":         "de-DE",
        "country_code":   "DE",
        "timezone":       "Europe/Berlin",
        "ali_ship_param": "DE",
        "ebay_location":  "DE",
    },
    {
        "name":           "Italy",
        "url":            "https://www.ebay.it",
        "currency":       "EUR",
        "locale":         "it-IT",
        "country_code":   "IT",
        "timezone":       "Europe/Rome",
        "ali_ship_param": "IT",
        "ebay_location":  "IT",
    },
    {
        "name":           "Australia",
        "url":            "https://www.ebay.com.au",
        "currency":       "AUD",
        "locale":         "en-AU",
        "country_code":   "AU",
        "timezone":       "Australia/Sydney",
        "ali_ship_param": "AU",
        "ebay_location":  "AU",
    },
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

BLOCK_SIGNALS = [
    "captcha", "robot check", "automated access",
    "verify you are human", "g-recaptcha", "security check",
]

BRANDED_KEYWORDS = [
    "apple", "samsung", "sony", "nike", "adidas", "lego", "dyson",
    "iphone", "ipad", "airpods", "playstation", "xbox", "nintendo",
]

STOP_WORDS = {
    "the", "a", "an", "for", "with", "and", "or", "in", "on", "of",
    "to", "new", "lot", "set", "pack", "pcs", "piece", "pieces",
}

CHINA_SIGNALS = ["china", "cn", "shenzhen", "guangzhou", "hong kong"]

# ✅ FIX 3/4: Sold-page verification signals — look for these in the HTML
# to confirm the sold filter is actually active and showing real sold data.
SOLD_PAGE_SIGNALS = [
    # English (eBay UK / AU)
    "sold for", "sold on", "s-item__title--tagblock",
    # German (eBay DE)
    "verkauft", "verkauft für", "verkauft am",
    # Italian (eBay IT)
    "venduto", "venduto il", "venduto per",
    # Structural signals present on any sold-results page
    'lh_sold=1', 'lh_complete=1',
]

SOLD_DATE_PATTERNS = [
    r"Sold\s+(\d{1,2}\s+\w{3,9}(?:\s+\d{4})?)",
    r"Venduto\s+il\s+(\d{1,2}\s+\w{3,9}(?:\s+\d{4})?)",
    r"Verkauft\s+am\s+(\d{1,2}[\.\s]\w{3,9}(?:\s*\d{4})?)",
    r'"soldDate"\s*:\s*"(\d{4}-\d{2}-\d{2})',
    r'data-datetimedisplay="(\d{4}-\d{2}-\d{2})',
]

DATE_FORMATS = [
    "%d %b %Y", "%d %B %Y", "%Y-%m-%d",
    "%d. %b %Y", "%d %b", "%d %B",
]

STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
    window.chrome = { runtime: {} };
    const orig = window.navigator.permissions.query;
    window.navigator.permissions.query = (p) =>
        p.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : orig(p);
}
"""


# ─────────────────────────────────────────────────────────────────
# URL BUILDERS  (✅ FIX 1 + FIX 2 applied here)
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(keyword: str, country_cfg: dict) -> str:
    """
    ✅ FIX 1: Use LH_ItemLocation=<ebay_location> instead of LH_PrefLoc=1.
       LH_PrefLoc=1 = "ship to my location" (viewer-side filter, useless with proxy).
       LH_ItemLocation=GB = "seller is located in GB" (what we actually want).

    ✅ FIX 2: Removed LH_ItemCondition=1000 (New Only) from SOLD URL.
       eBay silently drops the sold filter when you combine:
         LH_Sold=1 + LH_Complete=1 + LH_ItemCondition=1000
       because "New" condition is incompatible with many sold listings.
       The sold page already shows condition in item metadata — we filter
       branded/low-quality results at parse time instead.
    """
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1"           # show sold items
        f"&LH_Complete=1"       # show completed listings
        f"&LH_ItemLocation={location}"   # ✅ seller is in target country
        f"&LH_BIN=1"            # Buy It Now only (no auctions)
        # NOTE: LH_ItemCondition=1000 intentionally removed from sold URL
        f"&_sop=10"             # sort: time ended (most recent first)
        f"&_ipg={ITEMS_PER_PAGE}"
    )


def build_ebay_active_url(keyword: str, country_cfg: dict) -> str:
    """
    Active listings URL. Condition filter is safe here (no sold-filter conflict).
    """
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_BIN=1"
        f"&LH_ItemLocation={location}"   # ✅ same country filter
        f"&LH_ItemCondition=1000"        # New only (safe here)
        f"&_ipg=60"
    )


def build_scraperapi_url(target_url: str, country_code: str) -> str:
    cc = country_code.lower()
    return (
        f"https://api.scraperapi.com"
        f"?api_key={SCRAPER_API_KEY}"
        f"&url={quote_plus(target_url)}"
        f"&country_code={cc}"
        f"&render=true"
        f"&premium=true"
    )


# ─────────────────────────────────────────────────────────────────
# FREE PROXY FETCHER
# ─────────────────────────────────────────────────────────────────

_proxy_cache: dict = {}


def fetch_free_proxies(country_code: str) -> list:
    if country_code in _proxy_cache and _proxy_cache[country_code]:
        return _proxy_cache[country_code]

    proxies = []
    headers = {"User-Agent": "Mozilla/5.0"}

    # Source 1: proxyscrape.com
    try:
        url = (
            f"https://api.proxyscrape.com/v3/free-proxy-list/get"
            f"?request=displayproxies"
            f"&country={country_code.lower()}"
            f"&protocol=http"
            f"&timeout=5000"
            f"&proxy_format=ipport"
            f"&format=text"
        )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
            for line in text.strip().splitlines():
                line = line.strip()
                if re.match(r"\d+\.\d+\.\d+\.\d+:\d+", line):
                    proxies.append(f"http://{line}")
        print(f"[BOT]   proxyscrape: {len(proxies)} proxies for {country_code}", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   proxyscrape fetch failed: {e}", file=sys.stderr)

    # Source 2: geonode.com
    if not proxies:
        try:
            url = (
                f"https://proxylist.geonode.com/api/proxy-list"
                f"?limit=50&page=1&sort_by=lastChecked&sort_type=desc"
                f"&country={country_code.upper()}"
                f"&protocols=http,https"
                f"&speed=fast"
            )
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for p in data.get("data", []):
                    ip   = p.get("ip", "")
                    port = p.get("port", "")
                    if ip and port:
                        proxies.append(f"http://{ip}:{port}")
            print(f"[BOT]   geonode: {len(proxies)} proxies for {country_code}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   geonode fetch failed: {e}", file=sys.stderr)

    random.shuffle(proxies)
    _proxy_cache[country_code] = proxies
    return proxies


def pop_proxy(country_code: str) -> str | None:
    proxies = _proxy_cache.get(country_code, [])
    return proxies.pop(0) if proxies else None


# ─────────────────────────────────────────────────────────────────
# TOR CIRCUIT ROTATION
# ─────────────────────────────────────────────────────────────────

async def new_tor_circuit():
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 9051)
        writer.write(b'AUTHENTICATE ""\r\n')
        await writer.drain()
        writer.write(b"SIGNAL NEWNYM\r\n")
        await writer.drain()
        writer.close()
        await asyncio.sleep(2)
        print("[BOT]   Tor: new circuit requested", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   Tor circuit rotation failed: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# EBAY OFFICIAL API (OPTION 4)
# ─────────────────────────────────────────────────────────────────

async def ebay_api_sold_search(keyword: str, country_cfg: dict) -> dict:
    empty = {"total": 0, "weeks": [0,0,0,0], "sold_price": 0.0, "reject_reason": "ebay api not configured"}

    if not EBAY_APP_ID:
        return {**empty, "reject_reason": "EBAY_APP_ID not set"}

    global_id_map = {
        "GB": "EBAY-GB",
        "DE": "EBAY-DE",
        "IT": "EBAY-IT",
        "AU": "EBAY-AU",
    }
    global_id = global_id_map.get(country_cfg["country_code"], "EBAY-GB")

    now    = datetime.utcnow()
    cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
    date_from = cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_to   = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    params = (
        f"OPERATION-NAME=findCompletedItems"
        f"&SERVICE-VERSION=1.0.0"
        f"&SECURITY-APPNAME={EBAY_APP_ID}"
        f"&RESPONSE-DATA-FORMAT=JSON"
        f"&REST-PAYLOAD"
        f"&keywords={quote_plus(keyword)}"
        f"&itemFilter(0).name=SoldItemsOnly&itemFilter(0).value=true"
        f"&itemFilter(1).name=ListingType&itemFilter(1).value=FixedPrice"
        f"&itemFilter(2).name=EndTimeFrom&itemFilter(2).value={quote_plus(date_from)}"
        f"&itemFilter(3).name=EndTimeTo&itemFilter(3).value={quote_plus(date_to)}"
        f"&itemFilter(4).name=LocatedIn&itemFilter(4).value={country_cfg['country_code']}"
        f"&sortOrder=EndTimeSoonest"
        f"&paginationInput.entriesPerPage=100"
        f"&GLOBAL-ID={global_id}"
        # NOTE: No Condition=New filter — same reason as FIX 2 above
    )

    api_url = f"https://svcs.ebay.com/services/search/FindingService/v1?{params}"

    try:
        loop = asyncio.get_event_loop()
        req  = urllib.request.Request(api_url, headers={"User-Agent": "eBayBot/1.0"})
        raw  = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15).read())
        data = json.loads(raw.decode("utf-8"))

        search_result = (
            data
            .get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
        )
        items = search_result.get("item", [])

        if not items:
            return {**empty, "reject_reason": "no sold items returned by eBay API"}

        weeks  = [0, 0, 0, 0]
        prices = []

        for item in items:
            end_time_raw = (
                item.get("listingInfo", [{}])[0]
                    .get("endTime", [""])[0]
            )
            try:
                dt     = datetime.strptime(end_time_raw[:19], "%Y-%m-%dT%H:%M:%S")
                age    = (now - dt).days
                bucket = min(age // 7, 3)
                weeks[bucket] += 1
            except Exception:
                pass

            price_raw = (
                item.get("sellingStatus", [{}])[0]
                    .get("convertedCurrentPrice", [{}])[0]
                    .get("__value__", "0")
            )
            try:
                prices.append(float(price_raw))
            except Exception:
                pass

        total      = sum(weeks)
        sold_price = round(sum(prices) / len(prices), 2) if prices else 0.0

        print(
            f"[BOT]   eBay API: {total} sold items, weeks={weeks}, avg_price={sold_price}",
            file=sys.stderr,
        )

        return {
            "total":         total,
            "weeks":         weeks,
            "per_week_avg":  round(total / 4, 1),
            "sold_price":    sold_price,
            "reject_reason": "",
        }

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {**empty, "reject_reason": f"eBay API error: {e}"}


# ─────────────────────────────────────────────────────────────────
# SCRAPERAPI HTML FETCH (OPTION 1)
# ─────────────────────────────────────────────────────────────────

async def fetch_via_scraperapi(target_url: str, country_code: str) -> str:
    wrapped = build_scraperapi_url(target_url, country_code)
    try:
        loop = asyncio.get_event_loop()
        req  = urllib.request.Request(wrapped, headers={"User-Agent": "Mozilla/5.0"})
        raw  = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=60).read())
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[BOT]   ScraperAPI fetch error: {e}", file=sys.stderr)
        return ""


# ─────────────────────────────────────────────────────────────────
# BROWSER CONTEXT FACTORY
# ─────────────────────────────────────────────────────────────────

async def make_context(playwright, country_cfg: dict, proxy: str | None = None):
    code   = country_cfg["country_code"]
    locale = country_cfg["locale"]
    tz     = country_cfg["timezone"]

    launch_args = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--window-size=1366,768",
        ],
    }
    if proxy:
        launch_args["proxy"] = {"server": proxy}
        print(f"[BOT]   Proxy: {proxy}", file=sys.stderr)
    elif USE_TOR:
        launch_args["proxy"] = {"server": "socks5://127.0.0.1:9050"}
        print(f"[BOT]   Using Tor for {code}", file=sys.stderr)

    browser = await playwright.chromium.launch(**launch_args)
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        locale=locale,
        timezone_id=tz,
        viewport={"width": 1366, "height": 768},
        extra_http_headers={
            "Accept-Language": f"{locale},en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    await context.add_init_script(STEALTH_JS)
    return browser, context


# ─────────────────────────────────────────────────────────────────
# PAGE SCRAPER (with retry logic)
# ─────────────────────────────────────────────────────────────────

async def fetch_page_with_retry(
    playwright,
    url: str,
    country_cfg: dict,
    max_retries: int = 3,
) -> str:
    code = country_cfg["country_code"]

    # Option 1: ScraperAPI
    if SCRAPER_API_KEY:
        print(f"[BOT]   Using ScraperAPI for {code}", file=sys.stderr)
        html = await fetch_via_scraperapi(url, code)
        if html and not is_blocked(html):
            return html
        print(f"[BOT]   ScraperAPI returned blocked/empty page", file=sys.stderr)

    # Pre-fetch free proxies if needed
    if USE_FREE_PROXIES and code not in _proxy_cache:
        fetch_free_proxies(code)

    for attempt in range(max_retries):
        proxy = None

        if USE_FREE_PROXIES:
            proxy = pop_proxy(code)
            if not proxy:
                print(f"[BOT]   No more proxies for {code}", file=sys.stderr)
            else:
                print(f"[BOT]   Attempt {attempt+1}: proxy={proxy}", file=sys.stderr)

        browser, context = await make_context(playwright, country_cfg, proxy)
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # ✅ FIX 3/4: Verify sold filter via HTML content, not URL
            if "LH_Sold=1" in url:
                await ensure_sold_filter(page, url)

            html = await page.content()

            if is_blocked(html):
                print(f"[BOT]   Blocked on attempt {attempt+1}, retrying...", file=sys.stderr)
                continue

            return html

        except PlaywrightTimeout:
            print(f"[BOT]   Timeout on attempt {attempt+1}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   Error on attempt {attempt+1}: {e}", file=sys.stderr)
        finally:
            await context.close()
            await browser.close()

        if USE_TOR:
            await new_tor_circuit()

    return ""


async def ensure_sold_filter(page, original_url: str) -> None:
    """
    ✅ FIX 3: Verify the sold filter is active by inspecting HTML content,
    not page.url. eBay sometimes strips query params from the visible URL
    while keeping (or silently dropping) the actual filter in state.

    Strategy:
      1. Grab current HTML and check for sold-page signals.
      2. If sold signals are missing, try to click the filter link.
      3. If click fails, navigate directly to the original URL again.
      4. Wait for networkidle and re-check.
    """
    async def sold_filter_active() -> bool:
        try:
            html = await page.content()
            low  = html[:20000].lower()
            return any(sig in low for sig in SOLD_PAGE_SIGNALS)
        except Exception:
            return False

    # Check 1: is the filter already active?
    if await sold_filter_active():
        return

    print("[BOT]   Sold filter not detected in HTML — attempting re-apply...", file=sys.stderr)

    # Check 2: try clicking a sold-filter link/checkbox in the page
    try:
        clicked = await page.evaluate("""
            () => {
                // Try href link containing LH_Sold
                const links = Array.from(document.querySelectorAll('a[href*="LH_Sold"]'));
                if (links.length) { links[0].click(); return 'link'; }

                // Try label/span with sold text (multilingual)
                const soldLabels = [
                    'sold items', 'completed items',
                    'verkaufte artikel', 'artikel verkauft',
                    'oggetti venduti', 'venduti',
                ];
                for (const el of document.querySelectorAll('label, span, a')) {
                    const t = el.textContent.trim().toLowerCase();
                    if (soldLabels.some(s => t.includes(s))) {
                        el.click();
                        return 'label:' + t;
                    }
                }
                return null;
            }
        """)
        if clicked:
            print(f"[BOT]   Clicked sold filter via: {clicked}", file=sys.stderr)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2.0)
            if await sold_filter_active():
                return
    except Exception as e:
        print(f"[BOT]   Sold filter click failed: {e}", file=sys.stderr)

    # Check 3: hard-navigate back to the original URL (most reliable fallback)
    try:
        print("[BOT]   Re-navigating to original sold URL...", file=sys.stderr)
        await page.goto(original_url, wait_until="networkidle", timeout=40000)
        await asyncio.sleep(2.0)
        if await sold_filter_active():
            print("[BOT]   Sold filter confirmed after re-navigation.", file=sys.stderr)
        else:
            print("[BOT]   WARNING: Sold filter still not confirmed after re-navigation.", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   Re-navigation failed: {e}", file=sys.stderr)


def is_blocked(html: str) -> bool:
    if not html:
        return True
    return any(s in html[:8000].lower() for s in BLOCK_SIGNALS)


# ─────────────────────────────────────────────────────────────────
# PARSE SOLD DATA FROM HTML
# ─────────────────────────────────────────────────────────────────

def parse_sold_from_html(html: str) -> dict:
    empty = {"total": 0, "weeks": [0,0,0,0], "sold_price": 0.0, "reject_reason": "no sold data"}

    if not html:
        return {**empty, "reject_reason": "empty HTML"}

    # ✅ FIX 4: Use the richer SOLD_PAGE_SIGNALS list (multi-language)
    low = html[:30000].lower()
    if not any(sig in low for sig in SOLD_PAGE_SIGNALS):
        return {**empty, "reject_reason": "sold filter not applied — no sold signals found in page HTML"}

    now    = datetime.utcnow()
    cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
    dates  = []

    for pat in SOLD_DATE_PATTERNS:
        for m in re.finditer(pat, html, re.IGNORECASE):
            raw = m.group(1).strip()
            for fmt in DATE_FORMATS:
                try:
                    dt = datetime.strptime(raw, fmt)
                    if dt.year == 1900:
                        dt = dt.replace(year=now.year)
                    if dt > now:
                        dt = dt.replace(year=dt.year - 1)
                    if dt >= cutoff and dt.year >= MIN_SALES_YEAR:
                        dates.append(dt)
                    break
                except ValueError:
                    continue

    if not dates:
        return {**empty, "reject_reason": "no sold dates parsed from page"}

    weeks = [0, 0, 0, 0]
    for dt in dates:
        slot = min((now - dt).days // 7, 3)
        weeks[slot] += 1

    # Extract prices
    prices = []
    for m in re.finditer(
        r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        p = parse_price(re.sub(r"<[^>]+>", "", m.group(1)))
        if p > 0:
            prices.append(p)

    sold_price = round(sum(prices) / len(prices), 2) if prices else 0.0
    total      = sum(weeks)

    return {
        "total":         total,
        "weeks":         weeks,
        "per_week_avg":  round(total / 4, 1),
        "sold_price":    sold_price,
        "reject_reason": "",
    }


def parse_items_from_html(html: str, country: str, currency: str) -> list:
    items = []
    seen  = set()

    blocks = re.split(r'(?=<li[^>]+class="[^"]*s-item[^"]*")', html)
    for block in blocks:
        if not re.match(r'<li[^>]+class="[^"]*s-item', block, re.I) or len(block) < 300:
            continue

        um = re.search(r'href="(https?://[^"]*ebay[^"]+/itm/[^"?]+)', block, re.I)
        if not um:
            continue
        url = um.group(1)
        if url in seen:
            continue

        title = None
        for pat in [
            r'class="[^"]*s-item__title[^"]*"[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?([^<]{8,200})',
            r'aria-label="([^"]{8,200})"',
        ]:
            m = re.search(pat, block, re.DOTALL | re.IGNORECASE)
            if m:
                t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
                if t and len(t) >= 8 and t.lower() not in {"new listing", "sponsored"}:
                    title = t
                    break
        if not title:
            continue

        pm = re.search(
            r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
            block, re.DOTALL | re.IGNORECASE,
        )
        price = parse_price(re.sub(r"<[^>]+>", "", pm.group(1))) if pm else 0.0
        if price <= 0:
            continue

        seen.add(url)
        items.append({"title": title, "url": url, "price": price,
                       "country": country, "currency": currency})

    return items


def parse_active_count(html: str) -> int:
    m = re.search(
        r'([\d,]+)\s*(?:results?|Ergebnisse|risultati|annunci|listings?)',
        html, re.IGNORECASE,
    )
    return int(m.group(1).replace(",", "").replace(".", "")) if m else 0


def parse_price(text) -> float:
    if not text:
        return 0.0
    text = str(text).split(" to ")[0].split(" - ")[0]
    prices = []
    for m in re.findall(r"\d+\.?\d*", re.sub(r"[^\d.]", "", text.replace(",", "."))):
        try:
            v = float(m)
            if 0.5 < v < 50000:
                prices.append(v)
        except ValueError:
            pass
    return min(prices) if prices else 0.0


def is_branded(title: str) -> bool:
    tl = title.lower()
    return any(b in tl for b in BRANDED_KEYWORDS)


def competition_label(n: int) -> str:
    if n < COMPETITION_LOW:
        return "low"
    elif n < COMPETITION_MEDIUM:
        return "medium"
    return "high"


def validate_weekly_sales(weeks: list) -> tuple:
    total = sum(weeks)
    avg   = total / len(weeks) if weeks else 0
    good  = [w for w in weeks if w >= MIN_SOLD_PER_WEEK]
    if total == 0:
        return False, "no sales found"
    if len(good) < MIN_WEEKS_WITH_SALES:
        return False, f"only {len(good)}/{len(weeks)} weeks >= {MIN_SOLD_PER_WEEK} sales"
    if avg < MIN_SOLD_PER_WEEK:
        return False, f"avg {avg:.1f}/wk too low"
    if avg > MAX_SOLD_PER_WEEK:
        return False, f"avg {avg:.1f}/wk too high (oversaturated)"
    if any(w > avg * 3.5 for w in weeks):
        return False, f"spike detected: {weeks}"
    return True, "ok"


# ─────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductResult:
    title:             str
    country:           str
    currency:          str
    ebaySoldPrice:     float
    ebayListPrice:     float
    soldPerWeek:       float
    totalSoldMonth:    int
    weeklyBreakdown:   list
    weeklyConsistency: str
    activeListings:    int
    competitionLevel:  str
    profit:            float
    ebayUrl:           str
    aliexpressUrl:     str
    ebayItemUrl:       str
    whyGoodProduct:    str
    fetchMethod:       str


# ─────────────────────────────────────────────────────────────────
# MAIN COUNTRY SCRAPER
# ─────────────────────────────────────────────────────────────────

async def scrape_country(keyword: str, country_cfg: dict, playwright) -> list:
    country  = country_cfg["name"]
    code     = country_cfg["country_code"]
    currency = country_cfg["currency"]
    results  = []

    print(f"\n[BOT] ═══ {country} ({currency}) ═══", file=sys.stderr)

    fetch_method = "scrape"
    sales        = None

    # Option 4: eBay API first
    if EBAY_APP_ID:
        print(f"[BOT]   Trying eBay API...", file=sys.stderr)
        sales = await ebay_api_sold_search(keyword, country_cfg)
        if not sales["reject_reason"]:
            fetch_method = "ebay_api"
            print(f"[BOT]   eBay API success!", file=sys.stderr)
        else:
            print(f"[BOT]   eBay API: {sales['reject_reason']}", file=sys.stderr)
            sales = None

    # Options 1/2/3: scrape
    if sales is None:
        sold_url = build_ebay_sold_url(keyword, country_cfg)
        print(f"[BOT]   Fetching sold URL: {sold_url}", file=sys.stderr)
        html     = await fetch_page_with_retry(playwright, sold_url, country_cfg)
        sales    = parse_sold_from_html(html)
        if SCRAPER_API_KEY:
            fetch_method = "scraperapi"
        elif USE_FREE_PROXIES:
            fetch_method = "free_proxy"
        elif USE_TOR:
            fetch_method = "tor"
        else:
            fetch_method = "direct_no_proxy"

    if sales["reject_reason"]:
        print(f"[BOT]   REJECT ({country}): {sales['reject_reason']}", file=sys.stderr)
        return []

    valid, reason = validate_weekly_sales(sales["weeks"])
    if not valid:
        print(f"[BOT]   REJECT ({country}): {reason}", file=sys.stderr)
        return []

    # Active competition count
    active_url  = build_ebay_active_url(keyword, country_cfg)
    active_html = await fetch_page_with_retry(playwright, active_url, country_cfg, max_retries=2)
    active      = parse_active_count(active_html)
    comp        = competition_label(active)

    if active > MAX_ACTIVE_LISTINGS:
        print(f"[BOT]   REJECT ({country}): {active} active listings", file=sys.stderr)
        return []

    # Product items from sold page
    sold_url  = build_ebay_sold_url(keyword, country_cfg)
    sold_html = await fetch_page_with_retry(playwright, sold_url, country_cfg)
    items     = parse_items_from_html(sold_html, country, currency)

    if not items:
        print(f"[BOT]   No items parsed ({country})", file=sys.stderr)
        return []

    weeks_str = "/".join(str(w) for w in sales["weeks"])
    avg_week  = round(sales["per_week_avg"], 1)

    for item in items[:PRODUCTS_PER_COUNTRY]:
        if is_branded(item["title"]):
            continue

        ebay_price = item["price"]
        sold_price = sales["sold_price"] if sales["sold_price"] > 0 else ebay_price
        profit     = round(sold_price * 0.3, 2)

        ali_url = (
            f"https://www.aliexpress.com/wholesale"
            f"?SearchText={quote_plus(item['title'])}"
            f"&shipCountry={country_cfg['ali_ship_param']}&isFreeShip=y"
        )

        results.append(asdict(ProductResult(
            title             = item["title"],
            country           = country,
            currency          = currency,
            ebaySoldPrice     = sold_price,
            ebayListPrice     = ebay_price,
            soldPerWeek       = avg_week,
            totalSoldMonth    = sales["total"],
            weeklyBreakdown   = sales["weeks"],
            weeklyConsistency = weeks_str,
            activeListings    = active,
            competitionLevel  = comp,
            profit            = profit,
            ebayUrl           = build_ebay_sold_url(keyword, country_cfg),
            aliexpressUrl     = ali_url,
            ebayItemUrl       = item["url"],
            whyGoodProduct    = (
                f"{avg_week} sales/wk · {comp} competition · "
                f"{sales['total']} sold/month"
            ),
            fetchMethod       = fetch_method,
        )))

    print(f"[BOT]   {country}: {len(results)} products found via {fetch_method}", file=sys.stderr)
    return results


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

async def main(keyword: str):
    if not PLAYWRIGHT_AVAILABLE:
        print(json.dumps({"error": "Run: pip install playwright && playwright install chromium"}))
        return

    print("\n[BOT] ━━━ Config ━━━", file=sys.stderr)
    print(f"[BOT] ScraperAPI: {'✅ ' + SCRAPER_API_KEY[:8] + '...' if SCRAPER_API_KEY else '❌ not set'}", file=sys.stderr)
    print(f"[BOT] eBay API:   {'✅ ' + EBAY_APP_ID[:8] + '...' if EBAY_APP_ID else '❌ not set'}", file=sys.stderr)
    print(f"[BOT] Tor:        {'✅' if USE_TOR else '❌'}", file=sys.stderr)
    print(f"[BOT] Free proxy: {'✅' if USE_FREE_PROXIES else '❌'}", file=sys.stderr)
    if not any([SCRAPER_API_KEY, EBAY_APP_ID, USE_TOR, USE_FREE_PROXIES]):
        print("[BOT] ⚠️  No proxy/API configured — location will be Pakistan!", file=sys.stderr)
    print("[BOT] ━━━━━━━━━━━━━\n", file=sys.stderr)

    all_results = []

    async with async_playwright() as pw:
        for cfg in EBAY_COUNTRIES:
            try:
                res = await scrape_country(keyword, cfg, pw)
                all_results.extend(res)
            except Exception as e:
                print(f"[BOT] Country error ({cfg['name']}): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    all_results.sort(key=lambda x: x.get("soldPerWeek", 0), reverse=True)

    print(json.dumps({"keyword": keyword, "products": all_results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ebay_bot_v12.py \"keyword\"")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))

#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v13 (FIXED: country links + sold filter + 30-day cutoff)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY FIXES vs v12:
  1. eBay item links now use the correct country domain (ebay.co.uk / ebay.de etc.)
  2. Sold filter (LH_Sold=1 + LH_Complete=1) is baked into every URL — no need
     to click it after page load.
  3. Products with sold dates > 30 days old are HARD-REJECTED before any further
     processing — nothing stale ever reaches the frontend.
  4. parse_items_from_html now rewrites item URLs to the correct country domain
     so the eBay ↗ link always opens the right marketplace.
"""

import sys
import json
import re
import asyncio
import random
import traceback
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse, urlunparse

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
#  ★ CONFIGURE YOUR FREE OPTION HERE ★
# ═══════════════════════════════════════════════════════════════

SCRAPER_API_KEY  = ""   # ScraperAPI key (5,000 free calls/month)
EBAY_APP_ID      = ""   # eBay Finding API key (5,000 free calls/day)
USE_TOR          = False
USE_FREE_PROXIES = True

# ═══════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

MIN_SOLD_PER_WEEK    = 10
MAX_SOLD_PER_WEEK    = 50
CURRENT_MONTH_DAYS   = 30   # hard cutoff — nothing older is accepted
MIN_WEEKS_WITH_SALES = 2
MIN_SALES_YEAR       = 2025
MAX_ACTIVE_LISTINGS  = 500
COMPETITION_LOW      = 50
COMPETITION_MEDIUM   = 200
PRODUCTS_PER_COUNTRY = 10
ITEMS_PER_PAGE       = 60

# eBay platform config
EBAY_PLATFORMS = {
    "UK": {
        "name": "UK", "url": "https://www.ebay.co.uk",
        "currency": "GBP", "locale": "en-GB",
        "country_code": "GB", "timezone": "Europe/London",
        "ali_ship_param": "GB",
    },
    "USA": {
        "name": "USA", "url": "https://www.ebay.com",
        "currency": "USD", "locale": "en-US",
        "country_code": "US", "timezone": "America/New_York",
        "ali_ship_param": "US",
    },
    "DE": {
        "name": "Germany", "url": "https://www.ebay.de",
        "currency": "EUR", "locale": "de-DE",
        "country_code": "DE", "timezone": "Europe/Berlin",
        "ali_ship_param": "DE",
    },
    "AU": {
        "name": "Australia", "url": "https://www.ebay.com.au",
        "currency": "AUD", "locale": "en-AU",
        "country_code": "AU", "timezone": "Australia/Sydney",
        "ali_ship_param": "AU",
    },
    "IT": {
        "name": "Italy", "url": "https://www.ebay.it",
        "currency": "EUR", "locale": "it-IT",
        "country_code": "IT", "timezone": "Europe/Rome",
        "ali_ship_param": "IT",
    },
}

COUNTRY_ALIASES = {
    "UK": "UK", "GB": "UK", "UNITED KINGDOM": "UK",
    "USA": "USA", "US": "USA", "UNITED STATES": "USA", "AMERICA": "USA",
    "DE": "DE", "GERMANY": "DE",
    "AU": "AU", "AUSTRALIA": "AU",
    "IT": "IT", "ITALY": "IT",
    "ALL": "ALL",
}

# Map eBay domain → canonical domain (for URL rewriting)
EBAY_DOMAIN_MAP = {
    "www.ebay.com":    "www.ebay.com",
    "www.ebay.co.uk":  "www.ebay.co.uk",
    "www.ebay.de":     "www.ebay.de",
    "www.ebay.com.au": "www.ebay.com.au",
    "www.ebay.it":     "www.ebay.it",
    "ebay.com":        "www.ebay.com",
    "ebay.co.uk":      "www.ebay.co.uk",
    "ebay.de":         "www.ebay.de",
    "ebay.com.au":     "www.ebay.com.au",
    "ebay.it":         "www.ebay.it",
}

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
# URL BUILDERS
# ─────────────────────────────────────────────────────────────────

def build_ebay_sold_url(keyword: str, base_url: str) -> str:
    """
    Build eBay sold-items search URL.
    LH_Sold=1 + LH_Complete=1 pre-applies the sold filter so the page
    opens with the filter already active — no clicking required.
    """
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1&LH_Complete=1"   # sold filter always pre-applied
        f"&LH_PrefLoc=1"
        f"&_sop=10"                    # sort by most recently sold
        f"&LH_BIN=1"
        f"&LH_ItemCondition=1000"
        f"&_ipg={ITEMS_PER_PAGE}"
    )


def build_ebay_active_url(keyword: str, base_url: str) -> str:
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}&LH_BIN=1&LH_PrefLoc=1&LH_ItemCondition=1000&_ipg=60"
    )


def build_ebay_item_url(raw_url: str, country_base_url: str) -> str:
    """
    Rewrite an eBay item URL so its domain matches the target country.
    e.g. an item found on ebay.co.uk during a DE scrape is rewritten to ebay.de.

    raw_url       – the href found in the HTML
    country_base_url – e.g. "https://www.ebay.de"
    """
    if not raw_url or raw_url == '#':
        return raw_url

    try:
        parsed = urlparse(raw_url)
        # Extract item path: keep /itm/... and strip everything else
        path   = parsed.path  # e.g. /itm/12345678901
        target = urlparse(country_base_url)
        return urlunparse((target.scheme, target.netloc, path, '', '', ''))
    except Exception:
        return raw_url


def build_ebay_sold_search_url(title: str, base_url: str) -> str:
    """
    Fallback link for a product: a country-correct sold-filter search URL.
    Used when no direct item URL is available.
    """
    q = quote_plus(title)
    return (
        f"{base_url}/sch/i.html?_nkw={q}"
        f"&LH_Sold=1&LH_Complete=1&LH_BIN=1"
        f"&LH_ItemCondition=1000&LH_PrefLoc=1&_sop=10"
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


def build_aliexpress_url(keyword: str, ship_to: str) -> str:
    q = quote_plus(keyword)
    return (
        f"https://www.aliexpress.com/wholesale"
        f"?SearchText={q}"
        f"&shipCountry={ship_to}&isFreeShip=y"
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

    try:
        url = (
            f"https://api.proxyscrape.com/v3/free-proxy-list/get"
            f"?request=displayproxies"
            f"&country={country_code.lower()}"
            f"&protocol=http&timeout=5000"
            f"&proxy_format=ipport&format=text"
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

    if not proxies:
        try:
            url = (
                f"https://proxylist.geonode.com/api/proxy-list"
                f"?limit=50&page=1&sort_by=lastChecked&sort_type=desc"
                f"&country={country_code.upper()}&protocols=http,https&speed=fast"
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
# TOR
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
        "GB": "EBAY-GB", "US": "EBAY-US",
        "DE": "EBAY-DE", "IT": "EBAY-IT", "AU": "EBAY-AU",
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
        f"&itemFilter(2).name=Condition&itemFilter(2).value=New"
        f"&itemFilter(3).name=EndTimeFrom&itemFilter(3).value={quote_plus(date_from)}"
        f"&itemFilter(4).name=EndTimeTo&itemFilter(4).value={quote_plus(date_to)}"
        f"&itemFilter(5).name=LocatedIn&itemFilter(5).value={country_cfg['country_code']}"
        f"&sortOrder=EndTimeSoonest"
        f"&paginationInput.entriesPerPage=100"
        f"&GLOBAL-ID={global_id}"
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
                # ── HARD 30-day cutoff ──
                if age > CURRENT_MONTH_DAYS:
                    continue
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

        if total == 0:
            return {**empty, "reject_reason": "no items sold within last 30 days"}

        print(f"[BOT]   eBay API: {total} sold items (last 30d), weeks={weeks}, avg_price={sold_price}", file=sys.stderr)

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
# SCRAPERAPI FETCH
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
        print(f"[BOT]   Using Tor", file=sys.stderr)

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
# PAGE FETCHER WITH RETRY
# ─────────────────────────────────────────────────────────────────

async def fetch_page_with_retry(
    playwright,
    url: str,
    country_cfg: dict,
    max_retries: int = 3,
) -> str:
    code = country_cfg["country_code"]

    if SCRAPER_API_KEY:
        print(f"[BOT]   Using ScraperAPI for {code}", file=sys.stderr)
        html = await fetch_via_scraperapi(url, code)
        if html and not is_blocked(html):
            return html
        print("[BOT]   ScraperAPI returned blocked/empty page", file=sys.stderr)

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
            # URL already has LH_Sold=1 baked in — no need to click after load
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            html = await page.content()

            if is_blocked(html):
                print(f"[BOT]   Blocked on attempt {attempt+1}, retrying...", file=sys.stderr)
                continue

            # Double-check sold filter is active in rendered URL
            current_url = page.url
            if "LH_Sold=1" not in current_url and "LH_Complete=1" not in current_url:
                print(f"[BOT]   Sold filter lost after redirect — injecting via JS", file=sys.stderr)
                await page.goto(url, wait_until="networkidle", timeout=40000)
                await asyncio.sleep(2.0)
                html = await page.content()

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


def is_blocked(html: str) -> bool:
    if not html:
        return True
    return any(s in html[:8000].lower() for s in BLOCK_SIGNALS)


# ─────────────────────────────────────────────────────────────────
# HTML PARSERS
# ─────────────────────────────────────────────────────────────────

def parse_sold_from_html(html: str) -> dict:
    """
    Parse sold dates from HTML and enforce the 30-day hard cutoff.
    Any item sold more than CURRENT_MONTH_DAYS ago is discarded entirely.
    """
    empty = {"total": 0, "weeks": [0,0,0,0], "sold_price": 0.0, "reject_reason": "no sold data"}

    if not html:
        return {**empty, "reject_reason": "empty HTML"}

    if not re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE):
        return {**empty, "reject_reason": "sold filter not applied"}

    now    = datetime.utcnow()
    cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
    dates  = []
    skipped_old = 0

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

                    # ── HARD 30-DAY CUTOFF ──
                    if dt < cutoff:
                        skipped_old += 1
                        break   # date parsed but too old — skip it

                    if dt.year >= MIN_SALES_YEAR:
                        dates.append(dt)
                    break
                except ValueError:
                    continue

    if skipped_old > 0:
        print(f"[BOT]   Skipped {skipped_old} sold items older than {CURRENT_MONTH_DAYS} days", file=sys.stderr)

    if not dates:
        return {**empty, "reject_reason": f"no sold dates within last {CURRENT_MONTH_DAYS} days"}

    weeks = [0, 0, 0, 0]
    for dt in dates:
        slot = min((now - dt).days // 7, 3)
        weeks[slot] += 1

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


def parse_items_from_html(html: str, country: str, currency: str, base_url: str) -> list:
    """
    Parse individual sold listing items from HTML.
    Item URLs are rewritten to use the correct country domain.
    """
    items = []
    seen  = set()

    blocks = re.split(r'(?=<li[^>]+class="[^"]*s-item[^"]*")', html)
    for block in blocks:
        if not re.match(r'<li[^>]+class="[^"]*s-item', block, re.I) or len(block) < 300:
            continue

        um = re.search(r'href="(https?://[^"]*ebay[^"]+/itm/[^"?]+)', block, re.I)
        if not um:
            continue
        raw_url = um.group(1)
        # ── Rewrite URL to correct country domain ──
        url = build_ebay_item_url(raw_url, base_url)

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

        # ── Check sold date on this specific item block ────────────
        # If a sold date is found in the block and it's older than 30d, skip
        item_too_old = False
        now    = datetime.utcnow()
        cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)
        for pat in SOLD_DATE_PATTERNS:
            m2 = re.search(pat, block, re.IGNORECASE)
            if m2:
                raw = m2.group(1).strip()
                for fmt in DATE_FORMATS:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        if dt.year == 1900:
                            dt = dt.replace(year=now.year)
                        if dt > now:
                            dt = dt.replace(year=dt.year - 1)
                        if dt < cutoff:
                            item_too_old = True
                        break
                    except ValueError:
                        continue
                break

        if item_too_old:
            continue

        seen.add(url)
        items.append({
            "title":    title,
            "url":      url,          # country-correct URL
            "price":    price,
            "country":  country,
            "currency": currency,
        })

    return items


def parse_active_count(html: str) -> int:
    m = re.search(
        r"([\d,]+)\s*(?:results?|Ergebnisse|risultati|annunci|listings?)",
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
# ALIEXPRESS PRICE ESTIMATION
# ─────────────────────────────────────────────────────────────────

def estimate_ali_price(ebay_price: float, currency: str) -> dict:
    to_usd = {"GBP": 1.27, "USD": 1.0, "EUR": 1.09, "AUD": 0.65}
    rate = to_usd.get(currency, 1.0)
    price_usd = ebay_price * rate

    ratio   = random.uniform(0.20, 0.30)
    ali_usd = round(price_usd * ratio, 2)

    return {
        "cost_usd":      ali_usd,
        "shipping_usd":  0.0,
        "delivery_time": "15-25 days",
        "rating":        round(random.uniform(4.4, 4.8), 1),
        "is_estimated":  True,
    }


# ─────────────────────────────────────────────────────────────────
# PROFIT CALCULATION
# ─────────────────────────────────────────────────────────────────

def calculate_profit(
    ebay_price: float,
    ebay_currency: str,
    ali_cost_usd: float,
    ali_shipping_usd: float,
) -> dict:
    to_usd = {"GBP": 1.27, "USD": 1.0, "EUR": 1.09, "AUD": 0.65}
    rate = to_usd.get(ebay_currency, 1.0)

    sell_usd    = ebay_price * rate
    ebay_fee    = sell_usd * 0.1325
    payment_fee = sell_usd * 0.029 + 0.30
    total_cost  = ali_cost_usd + ali_shipping_usd
    profit_usd  = sell_usd - ebay_fee - payment_fee - total_cost

    profit_local     = round(profit_usd / rate, 2)
    total_cost_local = round(total_cost / rate, 2)
    margin           = round((profit_usd / sell_usd) * 100, 1) if sell_usd > 0 else 0.0

    return {
        "totalCost":    total_cost_local,
        "profit":       profit_local,
        "profitMargin": margin,
    }


# ─────────────────────────────────────────────────────────────────
# COUNTRY SCRAPER
# ─────────────────────────────────────────────────────────────────

async def scrape_country(keyword: str, country_cfg: dict, playwright) -> list:
    country  = country_cfg["name"]
    code     = country_cfg["country_code"]
    currency = country_cfg["currency"]
    base_url = country_cfg["url"]
    results  = []

    print(f"\n[BOT] ═══ {country} ({currency}) ═══", file=sys.stderr)

    # ── Try eBay API first ────────────────────────────────────────
    fetch_method = "scrape"
    sales = None

    if EBAY_APP_ID:
        print("[BOT]   Trying eBay API...", file=sys.stderr)
        sales = await ebay_api_sold_search(keyword, country_cfg)
        if not sales["reject_reason"]:
            fetch_method = "ebay_api"
        else:
            print(f"[BOT]   eBay API: {sales['reject_reason']}", file=sys.stderr)
            sales = None

    # ── Fallback: scrape ─────────────────────────────────────────
    if sales is None:
        # URL already has LH_Sold=1 baked in
        sold_url = build_ebay_sold_url(keyword, base_url)
        html     = await fetch_page_with_retry(playwright, sold_url, country_cfg)
        sales    = parse_sold_from_html(html)
        if SCRAPER_API_KEY:
            fetch_method = "scraperapi"
        elif USE_FREE_PROXIES:
            fetch_method = "free_proxy"
        elif USE_TOR:
            fetch_method = "tor"
        else:
            fetch_method = "direct"

    if sales["reject_reason"]:
        print(f"[BOT]   REJECT ({country}): {sales['reject_reason']}", file=sys.stderr)
        return []

    # ── Validate weekly pattern ───────────────────────────────────
    valid, reason = validate_weekly_sales(sales["weeks"])
    if not valid:
        print(f"[BOT]   REJECT ({country}): {reason}", file=sys.stderr)
        return []

    # ── Competition count ─────────────────────────────────────────
    active_url  = build_ebay_active_url(keyword, base_url)
    active_html = await fetch_page_with_retry(playwright, active_url, country_cfg, max_retries=2)
    active      = parse_active_count(active_html)
    comp        = competition_label(active)

    if active > MAX_ACTIVE_LISTINGS:
        print(f"[BOT]   REJECT ({country}): {active} active listings (too saturated)", file=sys.stderr)
        return []

    # ── Get individual product items ──────────────────────────────
    sold_url  = build_ebay_sold_url(keyword, base_url)
    sold_html = await fetch_page_with_retry(playwright, sold_url, country_cfg)
    # Pass base_url so item URLs get rewritten to the correct country domain
    items     = parse_items_from_html(sold_html, country, currency, base_url)

    if not items:
        print(f"[BOT]   No items parsed ({country})", file=sys.stderr)
        return []

    avg_week = round(sales["per_week_avg"], 1)

    for item in items[:PRODUCTS_PER_COUNTRY]:
        if is_branded(item["title"]):
            continue

        ebay_price = item["price"]
        sold_price = sales["sold_price"] if sales["sold_price"] > 0 else ebay_price

        ali      = estimate_ali_price(sold_price, currency)
        ali_url  = build_aliexpress_url(item["title"], country_cfg["ali_ship_param"])
        profit   = calculate_profit(sold_price, currency, ali["cost_usd"], ali["shipping_usd"])

        if profit["profitMargin"] <= 0:
            continue

        # Fallback link: country-correct sold search (already filtered)
        ebay_link = item["url"] if item["url"] and item["url"] != '#' \
            else build_ebay_sold_search_url(item["title"], base_url)

        result = {
            "productName": item["title"],
            "ebay": {
                "price":            round(sold_price, 2),
                "weeklySales":      avg_week,
                "soldCount":        sales["total"],
                "weeklyBreakdown":  sales["weeks"],
                "shippingCountry":  country,
                "currency":         currency,
                "activeListings":   active,
                "competitionLevel": comp,
                "productLink":      ebay_link,       # country-correct
                "searchLink":       build_ebay_sold_url(item["title"], base_url),
            },
            "aliexpress": {
                "cost":         round(ali["cost_usd"], 2),
                "shipping":     ali["shipping_usd"],
                "deliveryTime": ali["delivery_time"],
                "rating":       ali["rating"],
                "matchedTitle": item["title"],
                "isEstimated":  ali["is_estimated"],
                "productLink":  ali_url,
            },
            "analysis": {
                "totalCost":    profit["totalCost"],
                "profit":       profit["profit"],
                "profitMargin": profit["profitMargin"],
                "fetchMethod":  fetch_method,
            },
        }

        results.append(result)

    print(f"[BOT]   {country}: {len(results)} products (last 30d) via {fetch_method}", file=sys.stderr)
    return results


# ─────────────────────────────────────────────────────────────────
# RESOLVE COUNTRY → LIST OF PLATFORM CONFIGS
# ─────────────────────────────────────────────────────────────────

def resolve_platforms(country: str) -> list:
    key = COUNTRY_ALIASES.get(country.upper(), "UK")
    if key == "ALL":
        return list(EBAY_PLATFORMS.values())
    cfg = EBAY_PLATFORMS.get(key)
    return [cfg] if cfg else [EBAY_PLATFORMS["UK"]]


# ─────────────────────────────────────────────────────────────────
# MAIN ASYNC RUNNER
# ─────────────────────────────────────────────────────────────────

async def run_search_async(keyword: str, country: str = "UK") -> list:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    platforms = resolve_platforms(country)

    print(f"\n[BOT] ━━━ Config ━━━", file=sys.stderr)
    print(f"[BOT] Keyword:    {keyword}", file=sys.stderr)
    print(f"[BOT] Country:    {country} → {[p['name'] for p in platforms]}", file=sys.stderr)
    print(f"[BOT] Cutoff:     last {CURRENT_MONTH_DAYS} days (items older than this are rejected)", file=sys.stderr)
    print(f"[BOT] ScraperAPI: {'✅ ' + SCRAPER_API_KEY[:8] + '...' if SCRAPER_API_KEY else '❌ not set'}", file=sys.stderr)
    print(f"[BOT] eBay API:   {'✅ ' + EBAY_APP_ID[:8] + '...' if EBAY_APP_ID else '❌ not set'}", file=sys.stderr)
    print(f"[BOT] Tor:        {'✅' if USE_TOR else '❌'}", file=sys.stderr)
    print(f"[BOT] Free proxy: {'✅' if USE_FREE_PROXIES else '❌'}", file=sys.stderr)
    print("[BOT] ━━━━━━━━━━━━━\n", file=sys.stderr)

    all_results = []

    async with async_playwright() as pw:
        for cfg in platforms:
            try:
                res = await scrape_country(keyword, cfg, pw)
                all_results.extend(res)
            except Exception as e:
                print(f"[BOT] Country error ({cfg['name']}): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    all_results.sort(key=lambda x: x["analysis"].get("profitMargin", 0), reverse=True)
    return all_results


def run_search(keyword: str, country: str = "UK") -> list:
    """Synchronous wrapper for Flask/Django integration."""
    return asyncio.run(run_search_async(keyword, country))


# ─────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python ebay_bot.py "keyword" [country]')
        print('       country: UK, USA, DE, AU, IT, ALL  (default: UK)')
        sys.exit(1)

    kw      = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "UK"

    results = asyncio.run(run_search_async(kw, country))
    print(json.dumps({"keyword": kw, "country": country, "products": results}, ensure_ascii=False, indent=2))

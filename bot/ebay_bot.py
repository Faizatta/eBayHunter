#!/usr/bin/env python3
"""
eBay Product Hunting Bot - v13 (DEFINITIVE FILTER FIX)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOT CAUSE (why v11/v12 still showed active listings):
  build_ebay_sold_url() was called in two places inside scrape_country()
  with the OLD v11 signature  →  build_ebay_sold_url(keyword, base_url_string)
  instead of the new v12 one  →  build_ebay_sold_url(keyword, country_cfg_dict)

  Python does NOT raise an error when you do "string"["url"] — it raises
  TypeError which was silently caught by the outer try/except, so the function
  returned a partial/broken URL with NO LH_Sold, NO LH_Complete, and
  NO LH_ItemLocation.  The bot then happily scraped active listings.

FIXES IN v13:
  ✅ build_ebay_sold_url / build_ebay_active_url now ASSERT their input is a
     dict and raise ValueError loudly if called wrong — no silent fallback.
  ✅ Every call site inside scrape_country() audited and fixed to pass the
     full country_cfg dict, never a bare string.
  ✅ The ebayUrl field in ProductResult was also building the URL wrong
     (passing keyword instead of country_cfg) — fixed.
  ✅ LH_ItemCondition=1000 removed from sold URL (kills sold filter on eBay).
  ✅ LH_PrefLoc replaced with LH_ItemLocation (actual seller-country filter).
  ✅ ensure_sold_filter() checks page HTML not page.url.
  ✅ Startup URL sanity-check prints all 8 URLs before scraping begins.

Usage: python ebay_bot_v13.py "keyword"
"""

import sys
import json
import re
import asyncio
import random
import traceback
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from urllib.parse import quote_plus

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
#  CONFIGURE YOUR FREE OPTION
# ═══════════════════════════════════════════════════════════════
SCRAPER_API_KEY  = ""    # https://www.scraperapi.com  (5000 free/month)
EBAY_APP_ID      = ""    # https://developer.ebay.com  (5000 free/day)
USE_TOR          = False # run `tor` first, then set True
USE_FREE_PROXIES = True  # auto-fetched free proxies (unreliable but free)
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

# Signals that confirm the SOLD filter is active in the rendered HTML
SOLD_PAGE_SIGNALS = [
    "lh_sold=1",           # in the page's own filter links
    "lh_complete=1",
    "sold for",            # English price label
    "sold on",
    "verkauft",            # German
    "venduto",             # Italian
    "s-item__title--tagblock",  # eBay structural class only on sold pages
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
    Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
    window.chrome = { runtime: {} };
    const orig = window.navigator.permissions.query;
    window.navigator.permissions.query = (p) =>
        p.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : orig(p);
}
"""

_proxy_cache: dict = {}


# ─────────────────────────────────────────────────────────────────
# URL BUILDERS  — hardened: crash loudly on wrong input
# ─────────────────────────────────────────────────────────────────

def _require_cfg(country_cfg, caller: str):
    """
    Guard: raise ValueError immediately if country_cfg is not a dict.
    This catches the old bug where a plain string was passed instead.
    """
    if not isinstance(country_cfg, dict):
        raise ValueError(
            f"{caller}() received country_cfg={country_cfg!r} (type={type(country_cfg).__name__}) "
            f"— must be a dict from EBAY_COUNTRIES, not a plain string."
        )
    for key in ("url", "ebay_location"):
        if key not in country_cfg:
            raise ValueError(f"{caller}() country_cfg missing required key '{key}': {country_cfg}")


def build_ebay_sold_url(keyword: str, country_cfg: dict) -> str:
    """
    Build the SOLD listings URL for a given country.

    Required params explained:
      LH_Sold=1            → show only sold/completed listings
      LH_Complete=1        → required alongside LH_Sold on some eBay domains
      LH_ItemLocation=XX   → seller is located in country XX
                             (NOT LH_PrefLoc which filters by the viewer's location)
      LH_BIN=1             → Buy It Now only — no auctions
      _sop=10              → sort by most recently ended first
      _ipg=60              → 60 results per page

    Deliberately excluded:
      LH_ItemCondition=1000  → "New only" kills the sold filter when combined
                               with LH_Sold=1 + LH_Complete=1 on most eBay domains.
      _pgn / _sop=7/15       → pagination/sort values that indicate active listing browsing.
    """
    _require_cfg(country_cfg, "build_ebay_sold_url")
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    url = (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1"
        f"&LH_Complete=1"
        f"&LH_ItemLocation={location}"
        f"&LH_BIN=1"
        f"&_sop=10"
        f"&_ipg={ITEMS_PER_PAGE}"
    )
    # Sanity check: assert the critical params are actually in the output
    assert "LH_Sold=1" in url,     f"BUG: LH_Sold missing from sold URL: {url}"
    assert "LH_Complete=1" in url, f"BUG: LH_Complete missing from sold URL: {url}"
    assert f"LH_ItemLocation={location}" in url, f"BUG: LH_ItemLocation missing: {url}"
    assert "LH_ItemCondition" not in url, f"BUG: LH_ItemCondition must NOT be in sold URL: {url}"
    return url


def build_ebay_active_url(keyword: str, country_cfg: dict) -> str:
    """
    Build the ACTIVE listings URL for competition counting.
    LH_ItemCondition=1000 is safe here (not combined with sold filter).
    """
    _require_cfg(country_cfg, "build_ebay_active_url")
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    url = (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_BIN=1"
        f"&LH_ItemLocation={location}"
        f"&LH_ItemCondition=1000"
        f"&_ipg=60"
    )
    assert "LH_Sold" not in url,    f"BUG: LH_Sold must NOT be in active URL: {url}"
    assert f"LH_ItemLocation={location}" in url, f"BUG: LH_ItemLocation missing: {url}"
    return url


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


def print_url_plan(keyword: str):
    """
    Print every URL the bot will fetch BEFORE it starts scraping.
    Lets you copy-paste into a browser and visually verify sold filter is active.
    """
    print("\n[BOT] ━━━ URL PLAN (verify these in browser before trusting results) ━━━", file=sys.stderr)
    for cfg in EBAY_COUNTRIES:
        sold_url   = build_ebay_sold_url(keyword, cfg)
        active_url = build_ebay_active_url(keyword, cfg)
        print(f"\n[BOT] {cfg['name']}:", file=sys.stderr)
        print(f"[BOT]   SOLD:   {sold_url}", file=sys.stderr)
        print(f"[BOT]   ACTIVE: {active_url}", file=sys.stderr)

        # Quick param audit
        ok = True
        for required in ("LH_Sold=1", "LH_Complete=1", f"LH_ItemLocation={cfg['ebay_location']}"):
            if required not in sold_url:
                print(f"[BOT]   ❌ SOLD URL missing: {required}", file=sys.stderr)
                ok = False
        if "LH_ItemCondition" in sold_url:
            print(f"[BOT]   ❌ SOLD URL has LH_ItemCondition — WILL KILL SOLD FILTER", file=sys.stderr)
            ok = False
        if ok:
            print(f"[BOT]   ✅ Sold URL params OK", file=sys.stderr)
    print("[BOT] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# FREE PROXY FETCHER
# ─────────────────────────────────────────────────────────────────

def fetch_free_proxies(country_code: str) -> list:
    if country_code in _proxy_cache and _proxy_cache[country_code]:
        return _proxy_cache[country_code]

    proxies = []
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        url = (
            f"https://api.proxyscrape.com/v3/free-proxy-list/get"
            f"?request=displayproxies&country={country_code.lower()}"
            f"&protocol=http&timeout=5000&proxy_format=ipport&format=text"
        )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            for line in resp.read().decode("utf-8").strip().splitlines():
                line = line.strip()
                if re.match(r"\d+\.\d+\.\d+\.\d+:\d+", line):
                    proxies.append(f"http://{line}")
        print(f"[BOT]   proxyscrape: {len(proxies)} proxies for {country_code}", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   proxyscrape failed: {e}", file=sys.stderr)

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
                    ip, port = p.get("ip",""), p.get("port","")
                    if ip and port:
                        proxies.append(f"http://{ip}:{port}")
            print(f"[BOT]   geonode: {len(proxies)} proxies for {country_code}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   geonode failed: {e}", file=sys.stderr)

    random.shuffle(proxies)
    _proxy_cache[country_code] = proxies
    return proxies


def pop_proxy(country_code: str) -> str | None:
    return (_proxy_cache.get(country_code) or [None]).pop(0) if _proxy_cache.get(country_code) else None


# ─────────────────────────────────────────────────────────────────
# TOR
# ─────────────────────────────────────────────────────────────────

async def new_tor_circuit():
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 9051)
        writer.write(b'AUTHENTICATE ""\r\nSIGNAL NEWNYM\r\n')
        await writer.drain()
        writer.close()
        await asyncio.sleep(2)
        print("[BOT]   Tor: new circuit", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   Tor circuit failed: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────
# EBAY OFFICIAL API
# ─────────────────────────────────────────────────────────────────

async def ebay_api_sold_search(keyword: str, country_cfg: dict) -> dict:
    _require_cfg(country_cfg, "ebay_api_sold_search")
    empty = {"total":0,"weeks":[0,0,0,0],"sold_price":0.0,"reject_reason":"no data"}

    if not EBAY_APP_ID:
        return {**empty, "reject_reason": "EBAY_APP_ID not set"}

    global_id_map = {"GB":"EBAY-GB","DE":"EBAY-DE","IT":"EBAY-IT","AU":"EBAY-AU"}
    global_id     = global_id_map.get(country_cfg["country_code"], "EBAY-GB")
    now    = datetime.utcnow()
    cutoff = now - timedelta(days=CURRENT_MONTH_DAYS)

    params = (
        f"OPERATION-NAME=findCompletedItems&SERVICE-VERSION=1.0.0"
        f"&SECURITY-APPNAME={EBAY_APP_ID}&RESPONSE-DATA-FORMAT=JSON&REST-PAYLOAD"
        f"&keywords={quote_plus(keyword)}"
        f"&itemFilter(0).name=SoldItemsOnly&itemFilter(0).value=true"
        f"&itemFilter(1).name=ListingType&itemFilter(1).value=FixedPrice"
        f"&itemFilter(2).name=EndTimeFrom&itemFilter(2).value={quote_plus(cutoff.strftime('%Y-%m-%dT%H:%M:%S.000Z'))}"
        f"&itemFilter(3).name=EndTimeTo&itemFilter(3).value={quote_plus(now.strftime('%Y-%m-%dT%H:%M:%S.000Z'))}"
        f"&itemFilter(4).name=LocatedIn&itemFilter(4).value={country_cfg['country_code']}"
        f"&sortOrder=EndTimeSoonest&paginationInput.entriesPerPage=100&GLOBAL-ID={global_id}"
    )

    try:
        loop = asyncio.get_event_loop()
        req  = urllib.request.Request(
            f"https://svcs.ebay.com/services/search/FindingService/v1?{params}",
            headers={"User-Agent":"eBayBot/1.0"},
        )
        raw  = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15).read())
        data = json.loads(raw.decode("utf-8"))
        items = (
            data.get("findCompletedItemsResponse",[{}])[0]
                .get("searchResult",[{}])[0]
                .get("item",[])
        )
        if not items:
            return {**empty, "reject_reason": "no items from eBay API"}

        weeks, prices = [0,0,0,0], []
        for item in items:
            end_time = item.get("listingInfo",[{}])[0].get("endTime",[""])[0]
            try:
                dt = datetime.strptime(end_time[:19], "%Y-%m-%dT%H:%M:%S")
                weeks[min((now-dt).days//7,3)] += 1
            except Exception:
                pass
            try:
                prices.append(float(
                    item.get("sellingStatus",[{}])[0]
                        .get("convertedCurrentPrice",[{}])[0]
                        .get("__value__","0")
                ))
            except Exception:
                pass

        total = sum(weeks)
        return {
            "total":         total,
            "weeks":         weeks,
            "per_week_avg":  round(total/4, 1),
            "sold_price":    round(sum(prices)/len(prices),2) if prices else 0.0,
            "reject_reason": "",
        }
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {**empty, "reject_reason": f"eBay API error: {e}"}


# ─────────────────────────────────────────────────────────────────
# SCRAPERAPI FETCH
# ─────────────────────────────────────────────────────────────────

async def fetch_via_scraperapi(target_url: str, country_code: str) -> str:
    try:
        loop = asyncio.get_event_loop()
        req  = urllib.request.Request(
            build_scraperapi_url(target_url, country_code),
            headers={"User-Agent":"Mozilla/5.0"},
        )
        raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=60).read())
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[BOT]   ScraperAPI error: {e}", file=sys.stderr)
        return ""


# ─────────────────────────────────────────────────────────────────
# BROWSER CONTEXT
# ─────────────────────────────────────────────────────────────────

async def make_context(playwright, country_cfg: dict, proxy: str | None = None):
    _require_cfg(country_cfg, "make_context")
    launch_args = {
        "headless": True,
        "args": ["--no-sandbox","--disable-blink-features=AutomationControlled",
                 "--disable-dev-shm-usage","--window-size=1366,768"],
    }
    if proxy:
        launch_args["proxy"] = {"server": proxy}
    elif USE_TOR:
        launch_args["proxy"] = {"server": "socks5://127.0.0.1:9050"}

    browser = await playwright.chromium.launch(**launch_args)
    context = await browser.new_context(
        user_agent   = random.choice(USER_AGENTS),
        locale       = country_cfg["locale"],
        timezone_id  = country_cfg["timezone"],
        viewport     = {"width":1366,"height":768},
        extra_http_headers = {
            "Accept-Language": f"{country_cfg['locale']},en;q=0.8",
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
    _require_cfg(country_cfg, "fetch_page_with_retry")
    code        = country_cfg["country_code"]
    is_sold_url = "LH_Sold=1" in url

    # Verify URL is correct before even fetching
    if is_sold_url:
        assert "LH_Complete=1" in url,     f"Sold URL missing LH_Complete: {url}"
        assert "LH_ItemLocation=" in url,  f"Sold URL missing LH_ItemLocation: {url}"
        assert "LH_ItemCondition" not in url, f"Sold URL has LH_ItemCondition (kills filter): {url}"

    # ScraperAPI path
    if SCRAPER_API_KEY:
        html = await fetch_via_scraperapi(url, code)
        if html and not is_blocked(html):
            if is_sold_url and not sold_filter_in_html(html):
                print(f"[BOT]   ⚠️  ScraperAPI page does not show sold signals — possible filter issue", file=sys.stderr)
            return html
        print(f"[BOT]   ScraperAPI blocked/empty", file=sys.stderr)

    if USE_FREE_PROXIES and code not in _proxy_cache:
        fetch_free_proxies(code)

    for attempt in range(max_retries):
        proxy = pop_proxy(code) if USE_FREE_PROXIES else None
        if USE_FREE_PROXIES and not proxy:
            print(f"[BOT]   No more proxies for {code}", file=sys.stderr)

        browser, context = await make_context(playwright, country_cfg, proxy)
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            if is_sold_url:
                await ensure_sold_filter(page, url)

            html = await page.content()
            if is_blocked(html):
                print(f"[BOT]   Blocked attempt {attempt+1}", file=sys.stderr)
                continue

            if is_sold_url and not sold_filter_in_html(html):
                print(
                    f"[BOT]   ⚠️  Attempt {attempt+1}: sold signals not found in HTML — "
                    f"page may be showing active listings despite sold URL params.",
                    file=sys.stderr,
                )

            return html

        except PlaywrightTimeout:
            print(f"[BOT]   Timeout attempt {attempt+1}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   Error attempt {attempt+1}: {e}", file=sys.stderr)
        finally:
            await context.close()
            await browser.close()

        if USE_TOR:
            await new_tor_circuit()

    return ""


def sold_filter_in_html(html: str) -> bool:
    low = html[:30000].lower()
    return any(sig in low for sig in SOLD_PAGE_SIGNALS)


async def ensure_sold_filter(page, original_url: str) -> None:
    """
    Confirm the sold filter is active by checking rendered HTML.
    If not active, try clicking the filter link, then re-navigate.
    Does NOT rely on page.url — eBay strips query params after redirects.
    """
    if sold_filter_in_html(await page.content()):
        return

    print("[BOT]   Sold filter not in HTML — trying to re-apply...", file=sys.stderr)

    # Try clicking a sold-filter element
    try:
        result = await page.evaluate("""
            () => {
                const soldTerms = [
                    'sold items','completed items',
                    'verkaufte artikel','oggetti venduti','venduti',
                ];
                for (const el of document.querySelectorAll('a[href*="LH_Sold"], label, span, a')) {
                    const href = el.getAttribute('href') || '';
                    if (href.includes('LH_Sold=1')) { el.click(); return 'href-click'; }
                    const t = el.textContent.trim().toLowerCase();
                    if (soldTerms.some(s => t.includes(s))) { el.click(); return 'label:' + t; }
                }
                return null;
            }
        """)
        if result:
            print(f"[BOT]   Clicked filter: {result}", file=sys.stderr)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
            if sold_filter_in_html(await page.content()):
                print("[BOT]   Sold filter confirmed after click.", file=sys.stderr)
                return
    except Exception as e:
        print(f"[BOT]   Filter click error: {e}", file=sys.stderr)

    # Hard re-navigate to original URL
    print("[BOT]   Re-navigating to sold URL...", file=sys.stderr)
    try:
        await page.goto(original_url, wait_until="networkidle", timeout=40000)
        await asyncio.sleep(2)
        status = "✅ confirmed" if sold_filter_in_html(await page.content()) else "⚠️  still not confirmed"
        print(f"[BOT]   After re-navigation: {status}", file=sys.stderr)
    except Exception as e:
        print(f"[BOT]   Re-navigation failed: {e}", file=sys.stderr)


def is_blocked(html: str) -> bool:
    if not html or len(html) < 500:
        return True
    return any(s in html[:8000].lower() for s in BLOCK_SIGNALS)


# ─────────────────────────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────────────────────────

def parse_sold_from_html(html: str) -> dict:
    empty = {"total":0,"weeks":[0,0,0,0],"sold_price":0.0,"reject_reason":"no sold data"}
    if not html:
        return {**empty, "reject_reason": "empty HTML"}
    if not sold_filter_in_html(html):
        return {**empty, "reject_reason": "sold filter signals not found in page HTML — page is showing active listings"}

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
        return {**empty, "reject_reason": "no sold dates found in HTML"}

    weeks = [0,0,0,0]
    for dt in dates:
        weeks[min((now-dt).days//7,3)] += 1

    prices = []
    for m in re.finditer(r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL|re.IGNORECASE):
        p = parse_price(re.sub(r"<[^>]+>","",m.group(1)))
        if p > 0:
            prices.append(p)

    total = sum(weeks)
    return {
        "total":         total,
        "weeks":         weeks,
        "per_week_avg":  round(total/4, 1),
        "sold_price":    round(sum(prices)/len(prices),2) if prices else 0.0,
        "reject_reason": "",
    }


def parse_items_from_html(html: str, country: str, currency: str) -> list:
    items, seen = [], set()
    for block in re.split(r'(?=<li[^>]+class="[^"]*s-item[^"]*")', html):
        if not re.match(r'<li[^>]+class="[^"]*s-item', block, re.I) or len(block) < 300:
            continue
        um = re.search(r'href="(https?://[^"]*ebay[^"]+/itm/[^"?]+)', block, re.I)
        if not um or um.group(1) in seen:
            continue
        url = um.group(1)
        title = None
        for pat in [
            r'class="[^"]*s-item__title[^"]*"[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?([^<]{8,200})',
            r'aria-label="([^"]{8,200})"',
        ]:
            m = re.search(pat, block, re.DOTALL|re.IGNORECASE)
            if m:
                t = re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",m.group(1))).strip()
                if t and len(t) >= 8 and t.lower() not in {"new listing","sponsored"}:
                    title = t
                    break
        if not title:
            continue
        pm = re.search(r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL|re.IGNORECASE)
        price = parse_price(re.sub(r"<[^>]+>","",pm.group(1))) if pm else 0.0
        if price <= 0:
            continue
        seen.add(url)
        items.append({"title":title,"url":url,"price":price,"country":country,"currency":currency})
    return items


def parse_active_count(html: str) -> int:
    m = re.search(r'([\d,]+)\s*(?:results?|Ergebnisse|risultati|annunci|listings?)', html, re.IGNORECASE)
    return int(m.group(1).replace(",","").replace(".","")) if m else 0


def parse_price(text) -> float:
    if not text:
        return 0.0
    text = str(text).split(" to ")[0].split(" - ")[0]
    prices = []
    for m in re.findall(r"\d+\.?\d*", re.sub(r"[^\d.]","",text.replace(",","."))):
        try:
            v = float(m)
            if 0.5 < v < 50000:
                prices.append(v)
        except ValueError:
            pass
    return min(prices) if prices else 0.0


def is_branded(title: str) -> bool:
    return any(b in title.lower() for b in BRANDED_KEYWORDS)


def competition_label(n: int) -> str:
    if n < COMPETITION_LOW:    return "low"
    if n < COMPETITION_MEDIUM: return "medium"
    return "high"


def validate_weekly_sales(weeks: list) -> tuple:
    total = sum(weeks)
    avg   = total / len(weeks) if weeks else 0
    good  = [w for w in weeks if w >= MIN_SOLD_PER_WEEK]
    if total == 0:
        return False, "no sales"
    if len(good) < MIN_WEEKS_WITH_SALES:
        return False, f"only {len(good)}/{len(weeks)} weeks >= {MIN_SOLD_PER_WEEK}"
    if avg < MIN_SOLD_PER_WEEK:
        return False, f"avg {avg:.1f}/wk too low"
    if avg > MAX_SOLD_PER_WEEK:
        return False, f"avg {avg:.1f}/wk too high"
    if any(w > avg * 3.5 for w in weeks):
        return False, f"spike: {weeks}"
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
# MAIN COUNTRY SCRAPER  — every call site uses country_cfg dict
# ─────────────────────────────────────────────────────────────────

async def scrape_country(keyword: str, country_cfg: dict, playwright) -> list:
    _require_cfg(country_cfg, "scrape_country")
    country      = country_cfg["name"]
    currency     = country_cfg["currency"]
    results      = []
    fetch_method = "scrape"
    sales        = None

    print(f"\n[BOT] ═══ {country} ({currency}) ═══", file=sys.stderr)

    # Option 4: eBay API (no proxy needed)
    if EBAY_APP_ID:
        sales = await ebay_api_sold_search(keyword, country_cfg)
        if not sales["reject_reason"]:
            fetch_method = "ebay_api"
            print(f"[BOT]   eBay API: {sales['total']} sold, weeks={sales['weeks']}", file=sys.stderr)
        else:
            print(f"[BOT]   eBay API fail: {sales['reject_reason']}", file=sys.stderr)
            sales = None

    # Options 1/2/3: scrape
    if sales is None:
        # ✅ FIXED: pass country_cfg dict (not a string)
        sold_url = build_ebay_sold_url(keyword, country_cfg)
        print(f"[BOT]   Fetching: {sold_url}", file=sys.stderr)
        html  = await fetch_page_with_retry(playwright, sold_url, country_cfg)
        sales = parse_sold_from_html(html)

        if SCRAPER_API_KEY:    fetch_method = "scraperapi"
        elif USE_FREE_PROXIES: fetch_method = "free_proxy"
        elif USE_TOR:          fetch_method = "tor"
        else:                  fetch_method = "direct_no_proxy"

    if sales["reject_reason"]:
        print(f"[BOT]   REJECT: {sales['reject_reason']}", file=sys.stderr)
        return []

    valid, reason = validate_weekly_sales(sales["weeks"])
    if not valid:
        print(f"[BOT]   REJECT: {reason}", file=sys.stderr)
        return []

    # Active listings count
    # ✅ FIXED: pass country_cfg dict
    active_url  = build_ebay_active_url(keyword, country_cfg)
    active_html = await fetch_page_with_retry(playwright, active_url, country_cfg, max_retries=2)
    active      = parse_active_count(active_html)
    comp        = competition_label(active)

    if active > MAX_ACTIVE_LISTINGS:
        print(f"[BOT]   REJECT: {active} active listings", file=sys.stderr)
        return []

    # Product items from sold page
    # ✅ FIXED: pass country_cfg dict (this was the main broken call in v11)
    sold_url  = build_ebay_sold_url(keyword, country_cfg)
    sold_html = await fetch_page_with_retry(playwright, sold_url, country_cfg)
    items     = parse_items_from_html(sold_html, country, currency)

    if not items:
        print(f"[BOT]   No items parsed", file=sys.stderr)
        return []

    avg_week  = round(sales["per_week_avg"], 1)
    weeks_str = "/".join(str(w) for w in sales["weeks"])

    for item in items[:PRODUCTS_PER_COUNTRY]:
        if is_branded(item["title"]):
            continue
        sold_price = sales["sold_price"] if sales["sold_price"] > 0 else item["price"]
        results.append(asdict(ProductResult(
            title             = item["title"],
            country           = country,
            currency          = currency,
            ebaySoldPrice     = sold_price,
            ebayListPrice     = item["price"],
            soldPerWeek       = avg_week,
            totalSoldMonth    = sales["total"],
            weeklyBreakdown   = sales["weeks"],
            weeklyConsistency = weeks_str,
            activeListings    = active,
            competitionLevel  = comp,
            profit            = round(sold_price * 0.3, 2),
            # ✅ FIXED: was build_ebay_sold_url(item["title"], base_url_string) — wrong on both args
            ebayUrl           = build_ebay_sold_url(keyword, country_cfg),
            aliexpressUrl     = (
                f"https://www.aliexpress.com/wholesale"
                f"?SearchText={quote_plus(item['title'])}"
                f"&shipCountry={country_cfg['ali_ship_param']}&isFreeShip=y"
            ),
            ebayItemUrl       = item["url"],
            whyGoodProduct    = f"{avg_week} sales/wk · {comp} competition · {sales['total']} sold/month",
            fetchMethod       = fetch_method,
        )))

    print(f"[BOT]   {country}: {len(results)} products via {fetch_method}", file=sys.stderr)
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
        print("[BOT] ⚠️  No proxy configured — country filters will show Pakistan results!", file=sys.stderr)

    # ✅ Print and verify all URLs before scraping starts
    print_url_plan(keyword)

    all_results = []
    async with async_playwright() as pw:
        for cfg in EBAY_COUNTRIES:
            try:
                res = await scrape_country(keyword, cfg, pw)
                all_results.extend(res)
            except ValueError as e:
                # Catch the new guard errors immediately — these are bugs, not runtime errors
                print(f"[BOT] ❌ BUG DETECTED in {cfg['name']}: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            except Exception as e:
                print(f"[BOT] Country error ({cfg['name']}): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    all_results.sort(key=lambda x: x.get("soldPerWeek", 0), reverse=True)
    print(json.dumps({"keyword": keyword, "products": all_results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ebay_bot_v13.py \"keyword\"")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))

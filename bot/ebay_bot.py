#!/usr/bin/env python3
"""
ebay_url_test.py — verify that sold URLs are built correctly before running the bot.

Run this first:
  python ebay_url_test.py "GYM Original"

It prints every URL the bot will use and opens them in your browser so you can
visually confirm they show SOLD items, not active listings.
"""

import sys
import webbrowser
from urllib.parse import quote_plus

EBAY_COUNTRIES = [
    {"name": "UK",        "url": "https://www.ebay.co.uk", "currency": "GBP", "locale": "en-GB", "country_code": "GB", "timezone": "Europe/London",    "ali_ship_param": "GB", "ebay_location": "GB"},
    {"name": "Germany",   "url": "https://www.ebay.de",    "currency": "EUR", "locale": "de-DE", "country_code": "DE", "timezone": "Europe/Berlin",    "ali_ship_param": "DE", "ebay_location": "DE"},
    {"name": "Italy",     "url": "https://www.ebay.it",    "currency": "EUR", "locale": "it-IT", "country_code": "IT", "timezone": "Europe/Rome",      "ali_ship_param": "IT", "ebay_location": "IT"},
    {"name": "Australia", "url": "https://www.ebay.com.au","currency": "AUD", "locale": "en-AU", "country_code": "AU", "timezone": "Australia/Sydney", "ali_ship_param": "AU", "ebay_location": "AU"},
]

ITEMS_PER_PAGE = 60


def build_ebay_sold_url(keyword: str, country_cfg: dict) -> str:
    """
    Correct sold URL — verified parameter list:

    LH_Sold=1           → show only sold/completed listings
    LH_Complete=1       → required alongside LH_Sold on some eBay domains
    LH_ItemLocation=XX  → seller must be in country XX  (not LH_PrefLoc which filters by buyer)
    LH_BIN=1            → Buy It Now only (no auctions)
    _sop=10             → sort by most recently ended
    _ipg=60             → 60 results per page

    INTENTIONALLY EXCLUDED:
    LH_ItemCondition=1000  → "New only" — combining this with LH_Sold=1 causes
                             eBay to silently drop the sold filter on most domains.
    LH_PrefLoc=1           → wrong parameter — filters by viewer location, not seller.
    """
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_Sold=1"
        f"&LH_Complete=1"
        f"&LH_ItemLocation={location}"
        f"&LH_BIN=1"
        f"&_sop=10"
        f"&_ipg={ITEMS_PER_PAGE}"
    )


def build_ebay_active_url(keyword: str, country_cfg: dict) -> str:
    base_url = country_cfg["url"]
    location = country_cfg["ebay_location"]
    q = quote_plus(keyword)
    return (
        f"{base_url}/sch/i.html"
        f"?_nkw={q}"
        f"&LH_BIN=1"
        f"&LH_ItemLocation={location}"
        f"&LH_ItemCondition=1000"
        f"&_ipg=60"
    )


def check_url_params(url: str, label: str) -> list[str]:
    """Return a list of problems found in the URL."""
    problems = []

    if label == "SOLD":
        if "LH_Sold=1" not in url:
            problems.append("❌ MISSING LH_Sold=1 — page will show active listings, not sold!")
        if "LH_Complete=1" not in url:
            problems.append("❌ MISSING LH_Complete=1 — sold filter may not apply on all eBay domains")
        if "LH_ItemCondition=1000" in url:
            problems.append("❌ LH_ItemCondition=1000 present — this silently kills the sold filter!")
        if "LH_PrefLoc" in url:
            problems.append("❌ LH_PrefLoc present — filters by viewer location (you), not seller country!")
        if "LH_ItemLocation=" not in url:
            problems.append("❌ MISSING LH_ItemLocation — no country filter at all!")

    if label == "ACTIVE":
        if "LH_Sold=1" in url:
            problems.append("⚠️  LH_Sold=1 on active URL — this will show sold items instead!")
        if "LH_ItemLocation=" not in url:
            problems.append("❌ MISSING LH_ItemLocation — no country filter!")
        if "LH_PrefLoc" in url:
            problems.append("❌ LH_PrefLoc present — wrong filter!")

    return problems


def main(keyword: str):
    print(f"\n{'═'*70}")
    print(f"  eBay URL Checker — keyword: \"{keyword}\"")
    print(f"{'═'*70}\n")

    all_ok = True

    for cfg in EBAY_COUNTRIES:
        name     = cfg["name"]
        sold_url = build_ebay_sold_url(keyword, cfg)
        act_url  = build_ebay_active_url(keyword, cfg)

        print(f"{'─'*70}")
        print(f"  {name}")
        print(f"{'─'*70}")

        # Check SOLD URL
        print(f"\n  [SOLD URL]")
        print(f"  {sold_url}\n")
        issues = check_url_params(sold_url, "SOLD")
        if issues:
            all_ok = False
            for i in issues:
                print(f"  {i}")
        else:
            print(f"  ✅ All sold filter params correct")
            print(f"  ✅ LH_Sold=1 present")
            print(f"  ✅ LH_Complete=1 present")
            print(f"  ✅ LH_ItemLocation={cfg['ebay_location']} present")
            print(f"  ✅ LH_ItemCondition=1000 absent (safe)")
            print(f"  ✅ LH_PrefLoc absent (safe)")

        # Check ACTIVE URL
        print(f"\n  [ACTIVE URL]")
        print(f"  {act_url}\n")
        issues = check_url_params(act_url, "ACTIVE")
        if issues:
            all_ok = False
            for i in issues:
                print(f"  {i}")
        else:
            print(f"  ✅ Active listing params correct")

        print()

    print(f"{'═'*70}")
    if all_ok:
        print("  ✅ ALL URLs look correct — safe to run the bot.")
    else:
        print("  ❌ PROBLEMS FOUND — fix URLs before running the bot.")
    print(f"{'═'*70}\n")

    # Ask user if they want to open the sold URLs in browser to visually verify
    try:
        ans = input("Open SOLD URLs in browser to visually verify? [y/N]: ").strip().lower()
        if ans == "y":
            for cfg in EBAY_COUNTRIES:
                url = build_ebay_sold_url(keyword, cfg)
                print(f"Opening {cfg['name']}: {url}")
                webbrowser.open(url)
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "GYM Original"
    main(kw)

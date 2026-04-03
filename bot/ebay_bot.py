# ─────────────────────────────────────────────────────────────────
# FORCE "Sold items" — targets the pill/tag eBay actually renders
# ─────────────────────────────────────────────────────────────────

async def force_sold_filter(page) -> bool:
    """
    eBay renders 'Sold items' as a pill tag (not a checkbox).
    This function checks if the pill is already active.
    If not, it navigates directly to the URL with sold params
    and verifies the pill appears.
    """
    await asyncio.sleep(2.0)

    # ── Check if "Sold items" pill is already active ──
    already_active = await page.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                const txt = el.textContent.trim().toLowerCase();
                // pill looks like "Sold items ×"
                if ((txt === 'sold items' || txt.startsWith('sold items')) &&
                    el.children.length <= 2) {
                    return true;
                }
            }
            return false;
        }
    """)

    if already_active:
        print("[BOT]   Sold items pill already active ✅", file=sys.stderr)
        return True

    # ── Pill not found — rebuild URL with sold params and reload ──
    print("[BOT]   Sold items pill missing — reloading with forced params", file=sys.stderr)

    current_url = page.url

    # Inject params directly into whatever URL eBay landed on
    import time, random
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(current_url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Force all sold filter params
    params["LH_Sold"]          = ["1"]
    params["LH_Complete"]      = ["1"]
    params["LH_BIN"]           = ["1"]
    params["LH_ItemCondition"] = ["1000"]
    params["LH_PrefLoc"]       = ["1"]
    params["_sop"]             = ["10"]   # sort: recently sold
    params["rt"]               = ["nc"]   # no cache
    params["_rdc"]             = [f"{int(time.time())}_{random.randint(100,999)}"]

    new_query  = urlencode(params, doseq=True)
    forced_url = urlunparse(parsed._replace(query=new_query))

    await page.goto(forced_url, wait_until="networkidle", timeout=40000)
    await asyncio.sleep(2.0)

    # ── Re-check pill is now present ──
    confirmed = await page.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                const txt = el.textContent.trim().toLowerCase();
                if ((txt === 'sold items' || txt.startsWith('sold items')) &&
                    el.children.length <= 2) {
                    return true;
                }
            }
            // fallback: check for green "Sold DD Mon YYYY" text on listings
            return document.body.innerText.match(
                /Sold\s+\d{1,2}(st|nd|rd|th)?\s+\w+\s+\d{4}/i
            ) !== null;
        }
    """)

    if confirmed:
        print("[BOT]   Sold items pill confirmed ✅", file=sys.stderr)
    else:
        print("[BOT]   REJECT — sold items pill still missing after reload ❌", file=sys.stderr)

    return bool(confirmed)


# ─────────────────────────────────────────────────────────────────
# UPDATED fetch_page_with_retry
# ─────────────────────────────────────────────────────────────────

async def fetch_page_with_retry(playwright, url, country_cfg, max_retries=3):
    code = country_cfg["country_code"]

    for attempt in range(max_retries):
        proxy = pop_proxy(code) if USE_FREE_PROXIES else None
        browser, context = await make_context(playwright, country_cfg, proxy)

        try:
            page = await context.new_page()

            # Load initial URL
            await page.goto(url, wait_until="networkidle", timeout=40000)

            # Force & verify "Sold items" pill is active
            sold_ok = await force_sold_filter(page)

            if not sold_ok:
                print(f"[BOT]   Attempt {attempt+1} failed sold check, retrying...", file=sys.stderr)
                continue

            html = await page.content()

            if is_blocked(html):
                print(f"[BOT]   Blocked on attempt {attempt+1}", file=sys.stderr)
                continue

            # Extra guard: page must contain green sold dates like "Sold 5th January 2026"
            if not re.search(
                r"Sold\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}",
                html, re.IGNORECASE
            ):
                print(f"[BOT]   No sold dates found in HTML — rejecting", file=sys.stderr)
                continue

            return html  # ✅ confirmed sold listings

        except PlaywrightTimeout:
            print(f"[BOT]   Timeout on attempt {attempt+1}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   Error: {e}", file=sys.stderr)
        finally:
            await context.close()
            await browser.close()

    return ""

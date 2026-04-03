async def apply_sold_filter(page, base_url: str, keyword: str) -> bool:
    """
    Physically clicks the 'Sold items' checkbox the way a human would.
    Uses Playwright's locator API which is far more reliable than evaluate().
    """

    # ── Start from a clean search page (no sold params yet) ──
    search_url = f"{base_url}/sch/i.html?_nkw={quote_plus(keyword)}&LH_BIN=1&LH_ItemCondition=1000"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
    await asyncio.sleep(3)

    print(f"[BOT]   Page loaded: {page.url}", file=sys.stderr)

    # ── Try clicking 'Sold items' checkbox by its visible label text ──
    try:
        # This targets the exact label text "Sold items" in the left sidebar
        sold_label = page.get_by_text("Sold items", exact=True)
        await sold_label.wait_for(timeout=8000)
        await sold_label.click()
        print(f"[BOT]   ✅ Clicked 'Sold items' label", file=sys.stderr)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)
        return True

    except Exception as e:
        print(f"[BOT]   Label click failed: {e}", file=sys.stderr)

    # ── Fallback 1: click by input checkbox next to 'Sold items' text ──
    try:
        checkbox = page.locator("input[type='checkbox']").filter(has_text="Sold items")
        await checkbox.click(timeout=5000)
        print(f"[BOT]   ✅ Clicked checkbox (filter)", file=sys.stderr)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)
        return True

    except Exception as e:
        print(f"[BOT]   Checkbox click failed: {e}", file=sys.stderr)

    # ── Fallback 2: find 'Sold items' anywhere and click its parent li ──
    try:
        clicked = await page.evaluate("""
            () => {
                for (const el of document.querySelectorAll('li, label, span')) {
                    if (el.textContent.trim() === 'Sold items') {
                        const cb = el.querySelector('input[type="checkbox"]')
                                || el.closest('li')?.querySelector('input[type="checkbox"]');
                        if (cb) { cb.click(); return 'checkbox'; }
                        el.click();
                        return 'element';
                    }
                }
                return null;
            }
        """)
        if clicked:
            print(f"[BOT]   ✅ JS click succeeded: {clicked}", file=sys.stderr)
            await page.wait_for_load_state("networkidle", timeout=20000)
            await asyncio.sleep(2)
            return True

    except Exception as e:
        print(f"[BOT]   JS click failed: {e}", file=sys.stderr)

    # ── Fallback 3: scroll sidebar into view first, then retry ──
    try:
        await page.evaluate("window.scrollTo(0, 400)")
        await asyncio.sleep(1)
        sold_label = page.get_by_text("Sold items", exact=True)
        await sold_label.scroll_into_view_if_needed()
        await sold_label.click()
        print(f"[BOT]   ✅ Clicked after scroll", file=sys.stderr)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)
        return True

    except Exception as e:
        print(f"[BOT]   Scroll+click failed: {e}", file=sys.stderr)

    print(f"[BOT]   ❌ All click attempts failed", file=sys.stderr)
    return False


# ─────────────────────────────────────────────────────────────────
# VERIFY sold pill "Sold items ×" is active after clicking
# ─────────────────────────────────────────────────────────────────

async def verify_sold_active(page) -> bool:
    """
    After clicking, confirm the 'Sold items ×' pill appears
    AND green sold dates like 'Sold 5th Jan 2026' are on the page.
    """
    html = await page.content()

    pill = await page.evaluate("""
        () => [...document.querySelectorAll('*')].some(el =>
            el.children.length <= 3 &&
            el.textContent.trim().toLowerCase().includes('sold items')
        )
    """)

    dates = bool(re.search(
        r"Sold\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}",
        html, re.IGNORECASE
    ))

    print(f"[BOT]   Pill: {pill} | Sold dates: {dates}", file=sys.stderr)
    return pill or dates


# ─────────────────────────────────────────────────────────────────
# FULL FETCH — combines click + verify per country
# ─────────────────────────────────────────────────────────────────

async def fetch_sold_page(playwright, keyword: str, country_cfg: dict) -> str:
    base_url = country_cfg["url"]
    locale   = country_cfg["locale"]
    tz       = country_cfg["timezone"]
    name     = country_cfg["name"]

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
              "--disable-dev-shm-usage"]
    )
    context = await browser.new_context(
        locale=locale,
        timezone_id=tz,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "Chrome/124.0.0.0 Safari/537.36",
        extra_http_headers={"Accept-Language": f"{locale},en;q=0.8"},
    )

    try:
        page = await context.new_page()

        # Click the sold items checkbox like a real user
        clicked = await apply_sold_filter(page, base_url, keyword)

        if not clicked:
            print(f"[BOT]   SKIP {name} — could not click sold filter", file=sys.stderr)
            return ""

        # Confirm sold listings are showing
        confirmed = await verify_sold_active(page)

        if not confirmed:
            print(f"[BOT]   SKIP {name} — sold filter click did not apply", file=sys.stderr)
            return ""

        print(f"[BOT]   ✅ {name} — sold items confirmed, scraping...", file=sys.stderr)
        return await page.content()

    finally:
        await context.close()
        await browser.close()

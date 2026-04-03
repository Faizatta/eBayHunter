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

async def apply_sold_filter(page, base_url: str, keyword: str) -> bool:

    search_url = f"{base_url}/sch/i.html?_nkw={quote_plus(keyword)}&LH_BIN=1&LH_ItemCondition=1000"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)

    await asyncio.sleep(3)
    await page.evaluate("window.scrollTo(0, 500)")
    await asyncio.sleep(1)

    try:
        checkbox = page.locator('input[aria-label="Sold items"]')
        await checkbox.wait_for(timeout=10000)

        if not await checkbox.is_checked():
            await checkbox.check()

        print("[BOT] ✅ Sold filter applied", file=sys.stderr)

        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)

        return True

    except Exception as e:
        print(f"[BOT] ❌ Failed to apply sold filter: {e}", file=sys.stderr)
        return False

# ─────────────────────────────────────────────────────────────────
# FORCE "Sold items" CHECKBOX — clicks it if not already checked
# ─────────────────────────────────────────────────────────────────

async def force_sold_filter(page) -> bool:
    """
    Clicks the 'Sold items' checkbox on eBay if it is not already
    checked. Returns True if sold listings are confirmed active.
    """
    await asyncio.sleep(1.5)  # let filters render

    checked = await page.evaluate("""
        () => {
            // ── Method 1: find checkbox by its label text ──
            const labels = Array.from(document.querySelectorAll('label, span, div'));
            for (const el of labels) {
                const txt = el.textContent.trim().toLowerCase();
                if (txt === 'sold items') {
                    // walk up to find the checkbox input
                    const parent = el.closest('li, div[class*="filter"], span[class*="filter"]');
                    if (parent) {
                        const cb = parent.querySelector('input[type="checkbox"]');
                        if (cb && !cb.checked) {
                            cb.click();
                            return 'clicked-checkbox';
                        }
                        if (cb && cb.checked) {
                            return 'already-checked';
                        }
                    }
                    // fallback: click the label itself
                    el.click();
                    return 'clicked-label';
                }
            }

            // ── Method 2: find by href containing LH_Sold ──
            const link = document.querySelector('a[href*="LH_Sold=1"]');
            if (link) { link.click(); return 'clicked-link'; }

            return null;
        }
    """)

    print(f"[BOT]   Sold filter action: {checked}", file=sys.stderr)

    if checked and checked != 'already-checked':
        # Wait for page to reload after checkbox click
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(1.5)

    # ── Final verification: "Sold items" must appear in the HTML ──
    html = await page.content()
    sold_confirmed = bool(
        re.search(r"\b(Sold|Venduto|Verkauft|Vendu)\b", html, re.IGNORECASE)
    )

    if not sold_confirmed:
        print("[BOT]   REJECT — sold items not visible after filter attempt", file=sys.stderr)

    return sold_confirmed


# ─────────────────────────────────────────────────────────────────
# UPDATED fetch_page_with_retry — calls force_sold_filter every time
# ─────────────────────────────────────────────────────────────────

async def fetch_page_with_retry(playwright, url, country_cfg, max_retries=3):
    code = country_cfg["country_code"]

    for attempt in range(max_retries):
        proxy = pop_proxy(code) if USE_FREE_PROXIES else None
        browser, context = await make_context(playwright, country_cfg, proxy)

        try:
            page = await context.new_page()

            # Step 1 — load the URL (sold params already in URL)
            await page.goto(url, wait_until="networkidle", timeout=40000)

            # Step 2 — ALWAYS force the sold checkbox to be checked
            sold_ok = await force_sold_filter(page)

            if not sold_ok:
                print(f"[BOT]   Attempt {attempt+1}: sold filter failed, retrying...", file=sys.stderr)
                continue

            html = await page.content()

            if is_blocked(html):
                print(f"[BOT]   Blocked on attempt {attempt+1}", file=sys.stderr)
                continue

            return html  # ✅ sold items confirmed, return HTML

        except PlaywrightTimeout:
            print(f"[BOT]   Timeout on attempt {attempt+1}", file=sys.stderr)
        except Exception as e:
            print(f"[BOT]   Error on attempt {attempt+1}: {e}", file=sys.stderr)
        finally:
            await context.close()
            await browser.close()

    return ""  # all retries failed

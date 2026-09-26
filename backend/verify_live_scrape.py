"""
verify_live_scrape.py — Local residential-IP scraper verification tool.
"""

import asyncio
import os
import re
import shutil
import sys
import time
import urllib.parse
from playwright.async_api import async_playwright

from app.product_matcher import extract_valid_prices

DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug_scrapes")
PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".browser_profile")


def clear_browser_profile():
    """
    Wipes the persistent .browser_profile directory. Use this when a prior
    run got escalated to a CAPTCHA — the profile's saved cookies mark that
    session as tainted, so every subsequent run reusing it re-triggers the
    same challenge immediately, even after the underlying rate-limit window
    has passed. Equivalent to the `Remove-Item -Recurse -Force` PowerShell
    command, but callable from Python / cross-platform.
    """
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
        print(f"[Profile] Cleared tainted session at {PROFILE_DIR}")
    else:
        print("[Profile] No existing profile to clear.")


async def _wait_for_manual_captcha_solve(page):
    """
    Since this script runs headless=False specifically so a human can watch
    it, this makes that actually useful: pause execution and let the user
    solve the CAPTCHA by hand in the visible browser window, then resume
    once they confirm. input() blocks the whole interpreter, so it's run
    in a thread executor to avoid freezing the asyncio event loop.
    """
    print("\n" + "=" * 70)
    print("  ACTION NEEDED: A CAPTCHA challenge is showing in the browser window.")
    print("  1. Switch to the Chromium window Playwright opened.")
    print("  2. Solve the 'I'm not a robot' / picture challenge yourself.")
    print("  3. Come back here and press Enter once the page shows results.")
    print("=" * 70)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input, "  Press Enter after solving... ")
    await asyncio.sleep(1.5)

SHOPEE_CARD_SELECTORS = [
    "div.shopee-search-item-result__item",
    "div.col-xs-2-4",
    "li.shopee-search-item-result__item",
    "div[data-sqe='item']",
]
SHOPEE_TITLE_SELECTORS = "div.whitespace-normal, div._10Wbs-, div[data-sqe='name']"
SHOPEE_PRICE_SELECTORS = "span.ZEgDH9, span._3277Mc, div.v-margin, span[data-sqe='price']"

LAZADA_CARD_SELECTORS = [
    "div[data-tracking='product-card']",
    "div._95X4G",
    "div.Bm37W",
]
LAZADA_TITLE_SELECTORS = "div.RfADt a, a[title], div.title--wF4fy"
LAZADA_PRICE_SELECTORS = "span.ooOxS, span.currency, div.price--NVloM"


async def _save_debug_artifacts(page, label: str):
    if page.is_closed():
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = os.path.join(DEBUG_DIR, f"{label}_{stamp}.png")
    html_path = os.path.join(DEBUG_DIR, f"{label}_{stamp}.html")
    try:
        await page.screenshot(path=screenshot_path, full_page=True)
        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  [Debug] Saved screenshot -> {screenshot_path}")
        print(f"  [Debug] Saved page HTML  -> {html_path}")
    except Exception as e:
        print(f"  [Debug] Note: {e}")


async def _find_working_selector(page, selector_candidates: list, timeout_ms: int = 5000):
    for sel in selector_candidates:
        if page.is_closed():
            return None
        try:
            await page.wait_for_selector(sel, timeout=timeout_ms)
            return sel
        except Exception:
            continue
    return None


async def verify_platform_live(platform: str, product_query: str, min_price: int, max_price: int):
    print(f"\n==================================================================")
    print(f"  LIVE {platform.upper()} EXTRACTION TEST: '{product_query}'")
    print(f"  Price Bounds: RM {min_price} - RM {max_price}")
    print(f"==================================================================\n")

    encoded = urllib.parse.quote(product_query)
    if platform == "Shopee":
        url = f"https://shopee.com.my/search?keyword={encoded}&minPrice={min_price}&maxPrice={max_price}"
        card_candidates = SHOPEE_CARD_SELECTORS
        title_sel = SHOPEE_TITLE_SELECTORS
        price_sel = SHOPEE_PRICE_SELECTORS
    else:
        url = f"https://www.lazada.com.my/catalog/?q={encoded}&price={min_price}-{max_price}"
        card_candidates = LAZADA_CARD_SELECTORS
        title_sel = LAZADA_TITLE_SELECTORS
        price_sel = LAZADA_PRICE_SELECTORS

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-MY",
            timezone_id="Asia/Kuala_Lumpur",
            args=["--disable-blink-features=AutomationControlled"]
        )

        # 1. Pre-seed standard Shopee language cookies so modal is suppressed
        if platform == "Shopee":
            await context.add_cookies([
                {"name": "SPC_LANGUAGE", "value": "en", "domain": ".shopee.com.my", "path": "/"},
                {"name": "shopee_web_lang", "value": "en", "domain": ".shopee.com.my", "path": "/"},
            ])

        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("delete navigator.__proto__.webdriver;")

        print(f"[Browser] Navigating to: {url}")
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

        # 2. Click English if modal still appears
        if platform == "Shopee":
            try:
                # Robust locator matching the exact button text
                english_locators = [
                    page.get_by_text("English", exact=True),
                    page.get_by_role("button", name=re.compile("English", re.I)),
                    page.locator("button:has-text('English')"),
                    page.locator("div.language-selection button"),
                ]
                for loc in english_locators:
                    if await loc.count() > 0 and await loc.first.is_visible():
                        print("[Browser] Language modal found. Clicking 'English'...")
                        await loc.first.click()
                        await asyncio.sleep(2.5)
                        break
            except Exception:
                pass

        # 3. Check for real captcha challenge
        current_url = page.url.lower()
        title_text = (await page.title()).lower()
        captcha_present = "captcha" in current_url or "recaptcha" in current_url or await page.locator("iframe[src*='recaptcha']").count() > 0
        blocked_present = "punish" in current_url or "attention required" in title_text

        if captcha_present:
            await _save_debug_artifacts(page, f"{platform.lower()}_checkpoint")
            await _wait_for_manual_captcha_solve(page)
            # Re-check after the user says they solved it — either the page
            # already navigated to results, or we retry the search URL once.
            still_captcha = "captcha" in page.url.lower() or "recaptcha" in page.url.lower()
            if still_captcha:
                print("[Browser] Retrying the search URL now that the session should be cleared...")
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(2.0)
        elif blocked_present:
            print(f"[!] Hard block detected (not a solvable CAPTCHA) — likely IP-level rate limit.")
            print(f"[!] Try clear_browser_profile() and/or restarting your router for a fresh IP.")
            await _save_debug_artifacts(page, f"{platform.lower()}_checkpoint")
            await context.close()
            return

        # 4. Find matching product card selector
        working_selector = await _find_working_selector(page, card_candidates)
        if not working_selector:
            print(f"[!] No known card selector matched within timeout.")
            await _save_debug_artifacts(page, f"{platform.lower()}_no_selector_match")
            await context.close()
            return

        print(f"[DOM Scanner] Using selector: '{working_selector}'")
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(1.5)

        cards = await page.query_selector_all(working_selector)
        print(f"[DOM Scanner] Detected {len(cards)} raw product cards on page.\n")

        if len(cards) == 0:
            await _save_debug_artifacts(page, f"{platform.lower()}_zero_cards")
            await context.close()
            return

        candidates = []
        for card in cards[:15]:
            title_elem = await card.query_selector(title_sel)
            price_elem = await card.query_selector(price_sel)
            if not title_elem or not price_elem:
                continue

            raw_title = (await title_elem.inner_text()).strip()
            raw_price = (await price_elem.inner_text()).replace("RM", "").replace(",", "").strip()
            try:
                price_val = float(raw_price.split("-")[-1].strip()) if "-" in raw_price else float(raw_price)
            except ValueError:
                continue

            candidates.append((raw_title, price_val))

        await context.close()

        result = extract_valid_prices(candidates, product_query, min_price, max_price)

        print(f"[Matcher] Required tokens for this query: {result['required_tokens']}")
        print(f"[Matcher] {len(candidates)} raw candidates -> {result['sample_count']} genuinely matching\n")

        for title, price in result["matched"]:
            print(f"  [MATCHED]   RM {price:,.2f} -> {title[:65]}")
        for title, price in result["rejected_mismatch"]:
            print(f"  [REJECTED - wrong product]  RM {price:,.2f} -> {title[:65]}")
        for title, price in result["outliers_trimmed"]:
            print(f"  [REJECTED - price outlier]  RM {price:,.2f} -> {title[:65]}")

        print(f"\n------------------------------------------------------------------")
        if result["median_price"] is not None:
            print(f"  Median (matched only): RM {result['median_price']:,.2f}")
            print(f"  Trustworthy (>= 2 samples): {result['is_trustworthy']}")
        else:
            print(f"  No genuinely matching listings survived filtering.")
        print(f"------------------------------------------------------------------\n")


if __name__ == "__main__":
    if "--clear-profile" in sys.argv:
        clear_browser_profile()
        sys.exit(0)

    asyncio.run(verify_platform_live("Shopee", "RTX 4060 8GB", 1000, 1800))
    asyncio.run(verify_platform_live("Lazada", "RTX 4060 8GB", 1000, 1800))
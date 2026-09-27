"""
backend/tests/test_cdp_shopee.py — Real Chrome CDP Extraction Test.

Connects directly to your running Google Chrome browser over port 9222.
Uses class-immune regex and img[alt] title extraction.
"""

import asyncio
import os
import re
import sys
import urllib.parse
from playwright.async_api import async_playwright

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.product_matcher import extract_valid_prices

EXCLUDED = ["bracket", "holder", "stand", "cable", "heatsink", "thermal pad", "backplate", "box only"]


async def scrape_shopee_via_cdp(query: str, min_price: int, max_price: int):
    print("\n==================================================================")
    print(f"  CDP LIVE SHOPEE TEST: '{query}'")
    print(f"  Target: http://localhost:9222 (Real Google Chrome)")
    print("==================================================================\n")

    encoded = urllib.parse.quote(query)
    shopee_url = f"https://shopee.com.my/search?keyword={encoded}&minPrice={min_price}&maxPrice={max_price}"

    async with async_playwright() as p:
        try:
            print("[CDP] Connecting to real Chrome instance...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
        except Exception as e:
            print(f"[!] Could not connect to Chrome on port 9222: {e}")
            print("    Make sure Chrome was launched with: --remote-debugging-port=9222")
            return

        print(f"[CDP] Navigating to: {shopee_url}")
        await page.goto(shopee_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2.5)

        # -------------------------------------------------------------
        # 1. INTERACTIVE CAPTCHA CHECK
        # -------------------------------------------------------------
        current_url = page.url.lower()
        title_text = (await page.title()).lower()

        if any(x in current_url for x in ["verify", "captcha", "checkpoint", "is_logged_in=false"]) or "robot" in title_text:
            print("\n" + "=" * 65)
            print("  [!] CAPTCHA / VERIFICATION DETECTED IN CHROME WINDOW")
            print("  1. Switch to your open Chrome browser window.")
            print("  2. Solve the puzzle / 'I'm not a robot' challenge yourself.")
            print("  3. Wait until the page reloads and displays the search results.")
            print("=" * 65)
            await asyncio.to_thread(input, "\n>> Press [ENTER] in this terminal AFTER you solve it: ")
            await asyncio.sleep(2.0)

        # -------------------------------------------------------------
        # 2. SCROLL TO TRIGGER LAZY-LOADED CARDS
        # -------------------------------------------------------------
        print("[CDP] Scrolling page to trigger lazy-loaded cards...")
        await page.mouse.wheel(0, 800)
        await asyncio.sleep(1.5)

        card_selectors = [
            "li.shopee-search-item-result__item",
            "div.shopee-search-item-result__item",
            "div.col-xs-2-4",
            "div[data-sqe='item']"
        ]

        working_selector = None
        for sel in card_selectors:
            try:
                await page.wait_for_selector(sel, timeout=4000)
                working_selector = sel
                break
            except Exception:
                continue

        if not working_selector:
            print(f"[!] No product cards matched. Current page URL: {page.url}")
            return

        cards = await page.query_selector_all(working_selector)
        print(f"[CDP] Total raw cards found on page: {len(cards)}\n")

        # -------------------------------------------------------------
        # 3. CLASS-IMMUNE EXTRACTION (img[alt] + RM regex)
        # -------------------------------------------------------------
        candidates = []

        for card in cards[:25]:
            raw_title = None

            # Strategy A: Shopee embeds the full product title in the img[alt] attribute
            img = await card.query_selector("img[alt]")
            if img:
                alt = await img.get_attribute("alt")
                if alt and len(alt.strip()) > 8:
                    raw_title = alt.strip()

            # Strategy B: Fallback to text container
            if not raw_title:
                name_elem = await card.query_selector("div[data-sqe='name'], div.line-clamp-2, div.whitespace-normal")
                if name_elem:
                    raw_title = (await name_elem.inner_text()).strip()

            # Price Strategy: Regex matches RM amounts directly from card text
            card_text = await card.inner_text()
            price_matches = re.findall(r'RM\s*([\d,]+(?:\.\d+)?)', card_text)

            if not raw_title or not price_matches:
                continue

            try:
                # The first RM match is always the active promotional/selling price
                price_val = float(price_matches[0].replace(",", "").strip())
            except ValueError:
                continue

            candidates.append((raw_title, price_val))

        print(f"[CDP] Successfully extracted {len(candidates)} listings from DOM!")

        # -------------------------------------------------------------
        # 4. RUN THROUGH PRODUCT MATCHER
        # -------------------------------------------------------------
        result = extract_valid_prices(candidates, query, min_price, max_price)

        print(f"[Matcher] Required tokens: {result['required_tokens']}")
        print(f"[Matcher] {len(candidates)} candidates -> {result['sample_count']} genuinely matching:\n")

        for title, price in result["matched"]:
            print(f"  [MATCHED] RM {price:,.2f} -> {title[:65]}")
        for title, price in result["rejected_mismatch"]:
            print(f"  [REJECTED - wrong product] RM {price:,.2f} -> {title[:65]}")
        for title, price in result["outliers_trimmed"]:
            print(f"  [REJECTED - price outlier] RM {price:,.2f} -> {title[:65]}")

        print("\n------------------------------------------------------------------")
        if result["median_price"] is not None:
            print(f"  LIVE SHOPEE MEDIAN PRICE: RM {result['median_price']:,.2f}")
            print(f"  Trustworthy (>= 2 samples): {result['is_trustworthy']}")
        else:
            print("  No genuinely matching listings survived filtering.")
        print("------------------------------------------------------------------\n")


if __name__ == "__main__":
    asyncio.run(scrape_shopee_via_cdp("RRTX 5070 12GB", 2500, 4500))
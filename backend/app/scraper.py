"""
backend/app/scraper.py — Truthful E-Commerce Data Pipeline for EcoBuild.

Two-pass architecture: Lazada (bot-detection evasion only, no login needed)
and Shopee (requires an authenticated session — Shopee's guest /search is
hard-walled behind login, this is a different problem from Lazada's
velocity-based bot detection). Each platform gets its OWN persistent
browser profile so a Shopee login, once done manually, survives across
runs instead of requiring re-login every single time.

Run modes:
  python -m app.scraper                # automated/headless (GitHub Actions).
                                        # Shopee has no logged-in profile on
                                        # a cloud runner, so it automatically
                                        # falls back to ESTIMATED (derived
                                        # from Lazada's live price).
  python -m app.scraper --manual       # visible browser, prompts for manual
                                        # CAPTCHA solving AND for one-time
                                        # Shopee login (persists after that
                                        # via the saved .browser_profile_shopee).
"""

import asyncio
import os
import random
import re
import statistics
import sys
import urllib.parse
from datetime import datetime
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright

from .database import SessionLocal
from . import models
from .product_matcher import extract_valid_prices

DISCONTINUED_MODELS = {
    "rtx_3060_ti_twin", "rtx_3060_dual", "rx_6600_sapphire", "rx_6700_xt_qick", "arc_a750_le"
}

# Only these categories have genuinely volatile Malaysian retail pricing
# worth the request budget of live scraping. Ancillary parts (cases,
# coolers, PSUs, RAM, storage) have historically stable street prices in
# MY retail and are set to ESTIMATED directly — "Smart Targeted Batching":
# ~56 items (27 GPUs + ~29 CPUs) per platform pass instead of ~140.
LIVE_SCRAPE_CATEGORIES = {"GPU", "CPU"}

APP_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
LAZADA_PROFILE_DIR = os.path.join(BACKEND_DIR, ".browser_profile_lazada")
SHOPEE_PROFILE_DIR = os.path.join(BACKEND_DIR, ".browser_profile_shopee")

CAPTCHA_MARKERS = ["recaptcha", "g-recaptcha", "captcha-delivery", "hcaptcha"]
CHECKPOINT_MARKERS = ["punish", "verify", "checkpoint", "attention required"]
SHOPEE_LOGIN_MARKERS = ["login required", "is_logged_in=false", "/buyer/login", "/verify/traffic"]

PLATFORM_CONFIG = {
    "Lazada": {
        "requires_login": False,
        "card_selectors": [
            "div[data-tracking='product-card']",
            "div._95X4G",
            "div.Bm37W",
        ],
        "title_selector": "div.RfADt a, a[title], div.title--wF4fy",
        "price_selector": "span.ooOxS, span.currency, div.price--NVloM",
        "search_url": lambda q, lo, hi: f"https://www.lazada.com.my/catalog/?q={urllib.parse.quote(q)}&price={lo}-{hi}",
        "profile_dir": LAZADA_PROFILE_DIR,
    },
    "Shopee": {
        "requires_login": True,
        "card_selectors": [
            "div.shopee-search-item-result__item",
            "div.col-xs-2-4",
            "li.shopee-search-item-result__item",
            "div[data-sqe='item']",
        ],
        "title_selector": "div.whitespace-normal, div._10Wbs-, div[data-sqe='name']",
        "price_selector": "span.ZEgDH9, span._3277Mc, div.v-margin, span[data-sqe='price']",
        "search_url": lambda q, lo, hi: f"https://shopee.com.my/search?keyword={urllib.parse.quote(q)}&minPrice={lo}&maxPrice={hi}",
        "profile_dir": SHOPEE_PROFILE_DIR,
    },
}


async def _human_pause():
    """
    Variable pacing that avoids the uniform, clock-precise interval that
    makes automated traffic trivially detectable. Occasionally takes a
    longer "reading" pause (as a real person comparing listings would),
    rather than every gap being drawn from the same narrow range.
    """
    if random.random() < 0.15:
        await asyncio.sleep(random.uniform(6.0, 11.0))
    else:
        await asyncio.sleep(random.uniform(2.5, 5.0))


async def _human_scroll(page):
    """Multi-step scroll with pauses, rather than one instant jump."""
    try:
        steps = random.randint(2, 4)
        for _ in range(steps):
            await page.mouse.wheel(0, random.randint(200, 450))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.mouse.move(random.randint(200, 900), random.randint(150, 600))
    except Exception:
        pass


async def _wait_for_manual_input(prompt_lines: list, confirm_text: str = "  Press Enter to continue... "):
    print("\n" + "=" * 70)
    for line in prompt_lines:
        print(f"  {line}")
    print("=" * 70)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input, confirm_text)
    await asyncio.sleep(1.5)


async def _is_shopee_authenticated(context, page) -> bool:
    """
    Checks for genuine authentication by verifying Shopee's persistent
    user ID cookie ('SPC_U') and checking for guest/login redirect walls.
    """
    cookies = await context.cookies(["https://shopee.com.my"])
    user_id_cookie = next((c for c in cookies if c["name"] == "SPC_U"), None)
    
    # If SPC_U is missing, empty, or '-' (Shopee's guest placeholder), not logged in
    if not user_id_cookie or not user_id_cookie["value"] or user_id_cookie["value"] == "-":
        return False

    current_url = page.url.lower()
    if any(x in current_url for x in ["login", "buyer/login", "verify/traffic", "is_logged_in=false"]):
        return False

    return True


async def _ensure_shopee_login(context, page, manual_mode: bool) -> bool:
    """
    Ensures an authenticated Shopee session exists in the persistent profile.
    If unauthenticated and --manual is passed, opens the login page and pauses
    for the user to log into a throwaway account.
    """
    print("[Shopee] Checking login session via persistent profile...")
    try:
        await page.goto("https://shopee.com.my/user/account", timeout=20000, wait_until="domcontentloaded")
        await asyncio.sleep(2.0)
    except Exception as e:
        print(f"[Shopee] Could not reach account check page: {e}")

    # Accurate check using cookies and current URL
    if await _is_shopee_authenticated(context, page):
        print("[Shopee] Authenticated session confirmed from saved profile.")
        return True

    if not manual_mode:
        print("\n[Shopee Notice] No active login session found, and running in automated mode.")
        print("[Shopee Notice] Skipping live Shopee extraction (ESTIMATED fallback active).")
        print("[Shopee Notice] To log in once with your throwaway account, run: python sync_to_cloud.py --manual\n")
        return False

    # Manual mode: Navigate directly to the login portal and wait for the user
    login_url = "https://shopee.com.my/buyer/login"
    print(f"\n[Shopee] Navigating to login portal: {login_url}")
    try:
        await page.goto(login_url, timeout=25000, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)
    except Exception:
        pass

    await _wait_for_manual_input([
        "==================================================================",
        "  ACTION REQUIRED IN THE CHROMIUM BROWSER WINDOW:",
        "  1. Switch to the open browser window.",
        "  2. Log into your DISPOSABLE / THROWAWAY Shopee account.",
        "  3. Complete any OTP / SMS / Puzzle verification.",
        "  4. Once you see the Shopee homepage or your account page, come back here.",
        "==================================================================",
    ], confirm_text="  Press [ENTER] here AFTER you have successfully logged in: ")

    # Verify that login succeeded
    try:
        await page.goto("https://shopee.com.my/user/account", timeout=20000, wait_until="domcontentloaded")
        await asyncio.sleep(2.0)
    except Exception:
        pass

    if not await _is_shopee_authenticated(context, page):
        print("[Shopee] Authentication could not be confirmed. Skipping Shopee live queries this run.")
        return False

    print("[Shopee] Login confirmed! Session cookies saved to disk for future runs.")
    return True


def clean_search_query(name: str) -> str:
    """
    Strips parentheses and verbose catalog marketing descriptions so
    marketplace search engines return real product listings.
    Example: 'Samsung 980 Pro 1TB Gen4 NVMe (DRAM Cache)' -> 'Samsung 980 Pro 1TB'
    """
    clean = re.sub(r'\(.*?\)', '', name)
    buzzwords = [
        r'\bCompact Glass MATX\b', r'\bATX Mid-Tower\b', r'\bHigh Airflow\b',
        r'\bFull Mesh\b', r'\bReal Walnut\b', r'\bPanoramic\b', r'\bMicro-ATX\b',
        r'\bGaming NVMe\b', r'\bMax Performance\b', r'\bHeatsink Edition\b',
        r'\bSingle Tower Air\b', r'\bDual Tower Air\b', r'\bPCIe 4\.0\b',
        r'\b80\+ Bronze\b', r'\b80\+ Gold\b', r'\b80\+ Platinum\b', r'\b80\+ White\b',
        r'\bFull Modular\b', r'\bNon-Modular\b', r'\bMATX\b', r'\bITX\b', r'\bATX\b'
    ]
    for word in buzzwords:
        clean = re.sub(word, '', clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


async def scrape_platform_live(platform: str, page, category: str, model_key: str, raw_name: str,
                                 base_price: float, manual_mode: bool = False, _is_retry: bool = False) -> dict:
    """
    Generic live-extraction routine shared by Lazada and Shopee — same
    CAPTCHA handling, same strict product matching, same outlier trimming.
    Only the URL template and DOM selectors differ (see PLATFORM_CONFIG).
    """
    cfg = PLATFORM_CONFIG[platform]
    search_term = clean_search_query(raw_name)
    min_floor = int(base_price * 0.60)
    max_ceil = int(base_price * 2.20)
    url = cfg["search_url"](search_term, min_floor, max_ceil)

    try:
        print(f"[{platform}/{category}] Searching '{search_term}' (Price: RM {min_floor} - {max_ceil})...")
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1.0, 2.0))

        page_url_lower = page.url.lower()
        page_title_lower = (await page.title()).lower()

        if any(m in page_url_lower or m in page_title_lower for m in CAPTCHA_MARKERS):
            if manual_mode and not _is_retry:
                await _wait_for_manual_input([
                    f"ACTION NEEDED while scraping '{platform}: {search_term}':",
                    "1. Switch to the visible Chromium window.",
                    "2. Solve the CAPTCHA / 'I'm not a robot' challenge yourself.",
                    "3. Come back here and press Enter once the page shows results.",
                    "(Press Enter with nothing typed to skip and mark this item ESTIMATED instead.)",
                ])
                return await scrape_platform_live(platform, page, category, model_key, raw_name, base_price,
                                                    manual_mode=manual_mode, _is_retry=True)

            print(f"  [CAPTCHA Wall Detected] '{search_term}' on {platform} — anti-bot engine escalated to an "
                  f"active challenge. Not a code bug; needs a manual solve or a fresh IP/profile.")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                    "sample_count": 0, "is_available": False, "captcha_hit": True, "login_lost": False, "blocked_hit": True}

        if platform == "Shopee" and any(m in page_url_lower or m in page_title_lower for m in SHOPEE_LOGIN_MARKERS):
            # Mid-run session loss is a DIFFERENT failure than a CAPTCHA —
            # no amount of solving anything fixes it, it needs a fresh login.
            print(f"  [Shopee Session Lost] '{search_term}' — the logged-in session appears to have expired "
                  f"mid-run. Re-run with --manual to log in again.")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                    "sample_count": 0, "is_available": False, "captcha_hit": False, "login_lost": True, "blocked_hit": True}

        if any(m in page_url_lower or m in page_title_lower for m in CHECKPOINT_MARKERS):
            print(f"  [!] Security redirect intercepted for '{search_term}' on {platform}")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                    "sample_count": 0, "is_available": False, "captcha_hit": False, "login_lost": False, "blocked_hit": True}

        await _human_scroll(page)

        working_selector = None
        for sel in cfg["card_selectors"]:
            try:
                await page.wait_for_selector(sel, timeout=6000)
                working_selector = sel
                break
            except Exception:
                continue

        if not working_selector:
            print(f"  [○] 0 listings found for '{search_term}' on {platform} (Preserving MSRP)")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                    "sample_count": 0, "is_available": False, "captcha_hit": False, "login_lost": False, "blocked_hit": False}

        cards = await page.query_selector_all(working_selector)
        candidates = []

        for card in cards[:12]:
            title_elem = await card.query_selector(cfg["title_selector"])
            price_elem = await card.query_selector(cfg["price_selector"])
            if not title_elem or not price_elem:
                continue

            raw_title = (await title_elem.inner_text()).strip()
            raw_price = (await price_elem.inner_text()).replace("RM", "").replace(",", "").strip()

            try:
                price_val = float(raw_price.split("-")[-1].strip()) if "-" in raw_price else float(raw_price)
            except ValueError:
                continue

            candidates.append((raw_title, price_val))

        result = extract_valid_prices(candidates, search_term, min_floor, max_ceil)

        if result["median_price"] is not None and result["sample_count"] > 0:
            print(f"  [● LIVE] {platform} MATCHED {result['sample_count']} listings! Median: RM {result['median_price']:.2f}")
            return {
                "status": "LIVE", "price_rm": result["median_price"], "shipping_rm": 4.50,
                "sample_count": result["sample_count"], "is_available": True,
                "captcha_hit": False, "login_lost": False, "blocked_hit": False,
            }

        print(f"  [○] No genuine matches survived filtering for '{search_term}' on {platform} (Preserving MSRP)")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                "sample_count": 0, "is_available": False, "captcha_hit": False, "login_lost": False, "blocked_hit": False}

    except Exception as e:
        print(f"  [!] Scrape error on '{search_term}' ({platform}): {e}")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
                "sample_count": 0, "is_available": False, "captcha_hit": False, "login_lost": False, "blocked_hit": False}


def _unavailable_stub(base_price: float) -> dict:
    return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0,
            "sample_count": 0, "is_available": False}


async def run_global_scraper_pipeline(manual_mode: bool = False):
    db: Session = SessionLocal()
    try:
        gpus = list(db.query(models.GPU).all())
        categories = [
            ("CPU", models.CPU, "cpu_id"),
            ("Motherboard", models.Motherboard, "mobo_id"),
            ("Cooler", models.Cooler, "cooler_id"),
            ("Case", models.Case, "case_id"),
            ("RAM", models.RAM, "ram_id"),
            ("Storage", models.Storage, "storage_id"),
            ("PSU", models.PSU, "psu_id"),
        ]

        print(f"\n==================================================================")
        print(f"[Pipeline] Initializing Comprehensive Live Market Sync...")
        print(f"[Pipeline] Mode: {'MANUAL (visible browser, CAPTCHA + login solving enabled)' if manual_mode else 'AUTOMATED (headless)'}")
        print(f"==================================================================\n")

        # -------------------------------------------------------------
        # A. ANCILLARY CATEGORIES — stable MY retail pricing, ESTIMATED
        #    directly, zero network requests, for BOTH platforms.
        # -------------------------------------------------------------
        for cat_name, model_cls, id_col in categories:
            if cat_name in LIVE_SCRAPE_CATEGORIES:
                continue
            items = list(db.query(model_cls).all())
            print(f"--- {cat_name} ({len(items)} items): stable MY retail pricing — marking ESTIMATED without live query ---")
            for item in items:
                model_id = getattr(item, id_col)
                base_price = float(item.price)
                _upsert_price(db, model_id, "Shopee", base_price, 0.0, True, 0, "ESTIMATED")
                _upsert_price(db, model_id, "Lazada", base_price, 0.0, True, 0, "ESTIMATED")

        # -------------------------------------------------------------
        # Build the flat, shuffled list of LIVE items (GPU + CPU).
        # Shuffled order: a fixed, predictable sequence is itself a
        # detectable automation signature.
        # -------------------------------------------------------------
        live_items = []  # (category, model_key, search_term, base_price)

        for gpu in gpus:
            if getattr(gpu, 'is_legacy', False) or gpu.gpu_id in DISCONTINUED_MODELS:
                for plat in ["Shopee", "Lazada"]:
                    _upsert_price(db, gpu.gpu_id, plat, float(gpu.price), 0.0, False, 0, "UNAVAILABLE")
                continue
            term = getattr(gpu, 'chipset_search_term', None) or gpu.name
            live_items.append(("GPU", gpu.gpu_id, term, float(gpu.price)))

        cpu_items = list(db.query(models.CPU).all())
        for item in cpu_items:
            live_items.append(("CPU", item.cpu_id, item.name, float(item.price)))

        random.shuffle(live_items)
        print(f"\n[Pipeline] {len(live_items)} volatile-pricing items queued for live scraping per platform.\n")

        async with async_playwright() as p:
            # ===========================================================
            # PASS 1: LAZADA — pure bot-detection evasion, no login needed.
            # ===========================================================
            print("=" * 70)
            print("  PASS 1 / 2: LAZADA")
            print("=" * 70)

            lazada_results = {}
            laz_context = await p.chromium.launch_persistent_context(
                user_data_dir=LAZADA_PROFILE_DIR,
                headless=not manual_mode,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-MY",
                timezone_id="Asia/Kuala_Lumpur",
                args=["--disable-blink-features=AutomationControlled"],
            )
            laz_page = laz_context.pages[0] if laz_context.pages else await laz_context.new_page()

            lazada_blocked = False
            search_count = 0
            for category, model_key, term, base_price in live_items:
                search_count += 1
                if search_count % 6 == 0:
                    try:
                        old_page = laz_page
                        laz_page = await laz_context.new_page()
                        await old_page.close()
                    except Exception as e:
                        print(f"[Tab Rotation Note] {e}, continuing with current page.")

                if not lazada_blocked:
                    res = await scrape_platform_live("Lazada", laz_page, category, model_key, term, base_price, manual_mode=manual_mode)
                    if res.get("captcha_hit"):
                        print("\n[Circuit Breaker] Lazada CAPTCHA wall hit. Stopping further Lazada queries this run.\n")
                        lazada_blocked = True
                    elif res.get("blocked_hit"):
                        print("\n[Circuit Breaker] Lazada security intercept detected. Pausing further live Lazada queries to protect IP reputation.\n")
                        lazada_blocked = True
                    else:
                        await _human_pause()
                else:
                    res = _unavailable_stub(base_price)

                lazada_results[model_key] = res
                _upsert_price(db, model_key, "Lazada", res["price_rm"], res["shipping_rm"], res["is_available"], res["sample_count"], res["status"])

            await laz_context.close()

            # ===========================================================
            # PASS 2: SHOPEE — requires an authenticated session.
            # ===========================================================
            print("\n" + "=" * 70)
            print("  PASS 2 / 2: SHOPEE")
            print("=" * 70)

            shop_context = await p.chromium.launch_persistent_context(
                user_data_dir=SHOPEE_PROFILE_DIR,
                headless=not manual_mode,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-MY",
                timezone_id="Asia/Kuala_Lumpur",
                args=["--disable-blink-features=AutomationControlled"],
            )
            shop_page = shop_context.pages[0] if shop_context.pages else await shop_context.new_page()

            shopee_usable = await _ensure_shopee_login(shop_context, shop_page, manual_mode)
            shopee_blocked = not shopee_usable

            search_count = 0
            for category, model_key, term, base_price in live_items:
                if not shopee_blocked:
                    search_count += 1
                    if search_count % 6 == 0:
                        try:
                            old_page = shop_page
                            shop_page = await shop_context.new_page()
                            await old_page.close()
                        except Exception as e:
                            print(f"[Tab Rotation Note] {e}, continuing with current page.")

                    res = await scrape_platform_live("Shopee", shop_page, category, model_key, term, base_price, manual_mode=manual_mode)
                    if res.get("captcha_hit"):
                        print("\n[Circuit Breaker] Shopee CAPTCHA wall hit. Stopping further Shopee queries this run.\n")
                        shopee_blocked = True
                    elif res.get("login_lost") or res.get("blocked_hit"):
                        print("\n[Circuit Breaker] Shopee session/security issue detected. Stopping further Shopee queries.\n")
                        shopee_blocked = True
                    else:
                        await _human_pause()
                else:
                    # Shopee unusable this run — derive from Lazada's LIVE
                    # price where we have one (same rationale as before:
                    # authorized MY distributors cross-list near-identical
                    # prices), otherwise just preserve MSRP.
                    laz_res = lazada_results.get(model_key)
                    if laz_res and laz_res.get("status") == "LIVE":
                        res = {"status": "ESTIMATED", "price_rm": laz_res["price_rm"], "shipping_rm": 3.50,
                               "sample_count": 0, "is_available": True}
                    else:
                        res = _unavailable_stub(base_price)
                        res["status"] = "ESTIMATED"
                        res["is_available"] = True

                _upsert_price(db, model_key, "Shopee", res["price_rm"], res["shipping_rm"], res["is_available"], res["sample_count"], res["status"])

            await shop_context.close()

        print("\n==================================================================")
        print("[Pipeline] Full Synchronization Finished: Database updated.")
        print("==================================================================\n")

    finally:
        db.close()


def _upsert_price(db: Session, model_key: str, platform: str, price: float, shipping: float, is_avail: bool, samples: int, status: str):
    existing = db.query(models.ScrapedPrice).filter(
        models.ScrapedPrice.model_key == model_key,
        models.ScrapedPrice.platform == platform
    ).first()

    if existing:
        existing.price_rm = price
        existing.shipping_rm = shipping
        existing.is_available = is_avail
        existing.sample_count = samples
        existing.data_status = status
        existing.last_verified_at = datetime.utcnow()
    else:
        db.add(models.ScrapedPrice(
            model_key=model_key,
            platform=platform,
            price_rm=price,
            shipping_rm=shipping,
            is_available=is_avail,
            sample_count=samples,
            data_status=status,
            last_verified_at=datetime.utcnow()
        ))
    db.commit()


if __name__ == "__main__":
    _manual = "--manual" in sys.argv
    asyncio.run(run_global_scraper_pipeline(manual_mode=_manual))
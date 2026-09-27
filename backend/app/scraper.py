"""
backend/app/scraper.py — Unified E-Commerce Pipeline for EcoBuild.

Extraction Architecture:
- Lazada: Visible/Headless persistent context with humanized pacing & circuit breaker.
- Shopee: Connects over CDP (port 9222) to authentic Google Chrome, bypassing
  login walls and extracting verified DOM listings.
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

LIVE_SCRAPE_CATEGORIES = {"GPU", "CPU"}

LAZADA_PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", ".browser_profile_lazada")

LAZADA_CARD_SELECTORS = [
    "div[data-tracking='product-card']",
    "div._95X4G",
    "div.Bm37W",
]
LAZADA_TITLE_SELECTORS = "div.RfADt a, a[title], div.title--wF4fy"
LAZADA_PRICE_SELECTORS = "span.ooOxS, span.currency, div.price--NVloM"


def clean_search_query(name: str) -> str:
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


async def scrape_lazada_live(page, category: str, model_key: str, raw_name: str, base_price: float) -> dict:
    search_term = clean_search_query(raw_name)
    min_floor = int(base_price * 0.60)
    max_ceil = int(base_price * 2.20)
    encoded = urllib.parse.quote(search_term)
    url = f"https://www.lazada.com.my/catalog/?q={encoded}&price={min_floor}-{max_ceil}"

    try:
        print(f"[Lazada/{category}] Searching '{search_term}' (Floor: RM {min_floor})...")
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1.2, 2.0))

        if any(x in page.url.lower() for x in ["punish", "verify", "captcha"]):
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False, "blocked": True}

        await page.evaluate("window.scrollBy(0, 700)")
        await asyncio.sleep(1.0)

        working_selector = None
        for sel in LAZADA_CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                working_selector = sel
                break
            except Exception:
                continue

        if not working_selector:
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False, "blocked": False}

        cards = await page.query_selector_all(working_selector)
        candidates = []

        for card in cards[:15]:
            title_elem = await card.query_selector(LAZADA_TITLE_SELECTORS)
            price_elem = await card.query_selector(LAZADA_PRICE_SELECTORS)
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
            print(f"  [● LIVE LAZADA] MATCHED {result['sample_count']} listings! Median: RM {result['median_price']:.2f}")
            return {
                "status": "LIVE",
                "price_rm": result["median_price"],
                "shipping_rm": 4.50,
                "sample_count": result["sample_count"],
                "is_available": True,
                "blocked": False
            }

        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False, "blocked": False}

    except Exception as e:
        print(f"  [!] Lazada error on '{search_term}': {e}")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False, "blocked": False}


async def scrape_shopee_cdp(page, category: str, model_key: str, raw_name: str, base_price: float) -> dict:
    search_term = clean_search_query(raw_name)
    min_floor = int(base_price * 0.60)
    max_ceil = int(base_price * 2.20)
    encoded = urllib.parse.quote(search_term)
    url = f"https://shopee.com.my/search?keyword={encoded}&minPrice={min_floor}&maxPrice={max_ceil}"

    try:
        print(f"[Shopee/{category}] Searching '{search_term}' (Floor: RM {min_floor})...")
        await page.goto(url, timeout=25000, wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

        await page.mouse.wheel(0, 800)
        await asyncio.sleep(1.2)

        if "is_logged_in=false" in page.url.lower():
            print("  [!] Shopee login session expired.")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

        card_selectors = [
            "li.shopee-search-item-result__item",
            "div.shopee-search-item-result__item",
            "div.col-xs-2-4",
            "div[data-sqe='item']"
        ]

        working_selector = None
        for sel in card_selectors:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                working_selector = sel
                break
            except Exception:
                continue

        if not working_selector:
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

        cards = await page.query_selector_all(working_selector)
        candidates = []

        for card in cards[:20]:
            raw_title = None
            img = await card.query_selector("img[alt]")
            if img:
                alt = await img.get_attribute("alt")
                if alt and len(alt.strip()) > 8:
                    raw_title = alt.strip()

            if not raw_title:
                name_elem = await card.query_selector("div[data-sqe='name'], div.line-clamp-2")
                if name_elem:
                    raw_title = (await name_elem.inner_text()).strip()

            card_text = await card.inner_text()
            price_matches = re.findall(r'RM\s*([\d,]+(?:\.\d+)?)', card_text)

            if not raw_title or not price_matches:
                continue

            try:
                price_val = float(price_matches[0].replace(",", "").strip())
            except ValueError:
                continue

            candidates.append((raw_title, price_val))

        result = extract_valid_prices(candidates, search_term, min_floor, max_ceil)

        if result["median_price"] is not None and result["sample_count"] > 0:
            print(f"  [● LIVE SHOPEE] MATCHED {result['sample_count']} listings! Median: RM {result['median_price']:.2f}")
            return {
                "status": "LIVE",
                "price_rm": result["median_price"],
                "shipping_rm": 4.50,
                "sample_count": result["sample_count"],
                "is_available": True
            }

        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

    except Exception as e:
        print(f"  [!] Shopee error on '{search_term}': {e}")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}


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

        print("\n==================================================================")
        print("[Pipeline] Initializing Dual-Platform E-Commerce Sync...")
        print(f"[Pipeline] Mode: {'MANUAL (Visible Browser)' if manual_mode else 'HEADLESS'}")
        print("==================================================================\n")

        # 1. Ancillary categories set to ESTIMATED (Stable street prices)
        for cat_name, model_cls, id_col in categories:
            if cat_name in LIVE_SCRAPE_CATEGORIES:
                continue
            items = list(db.query(model_cls).all())
            print(f"--- {cat_name} ({len(items)} items): Stable retail baseline — marking ESTIMATED ---")
            for item in items:
                model_id = getattr(item, id_col)
                base_price = float(item.price)
                _upsert_price(db, model_id, "Shopee", base_price, 0.0, True, 0, "ESTIMATED")
                _upsert_price(db, model_id, "Lazada", base_price, 0.0, True, 0, "ESTIMATED")

        # 2. Queue Volatile Hardware (GPU + CPU)
        live_items = []
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

        async with async_playwright() as p:
            # ============================================================
            # A. SHOPEE VIA CHROME CDP (Port 9222)
            # ============================================================
            shopee_cdp_available = False
            shopee_page = None
            cdp_browser = None

            try:
                print("\n[Shopee Pass] Probing Chrome CDP on port 9222...")
                cdp_browser = await p.chromium.connect_over_cdp("http://localhost:9222", timeout=3000)
                context = cdp_browser.contexts[0]
                shopee_page = context.pages[0] if context.pages else await context.new_page()
                shopee_cdp_available = True
                print("[Shopee Pass] Connected to Real Chrome via CDP. Live Shopee extraction active!\n")
            except Exception:
                print("[Shopee Pass] Chrome on port 9222 not running. Shopee live extraction skipped (will calibrate from Lazada).\n")

            # ============================================================
            # B. LAZADA VIA PERSISTENT CONTEXT
            # ============================================================
            print("[Lazada Pass] Initializing Lazada browser context...")
            laz_context = await p.chromium.launch_persistent_context(
                user_data_dir=LAZADA_PROFILE_DIR,
                headless=not manual_mode,  # Visible window if manual_mode=True
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-MY",
                timezone_id="Asia/Kuala_Lumpur",
                args=["--disable-blink-features=AutomationControlled"]
            )
            laz_page = laz_context.pages[0] if laz_context.pages else await laz_context.new_page()

            lazada_blocked = False
            search_count = 0

            # --- RUN LIVE EXTRACTION LOOP ---
            for category, model_key, term, base_price in live_items:
                # 1. Scrape Shopee (if CDP connected)
                if shopee_cdp_available and shopee_page:
                    shop_res = await scrape_shopee_cdp(shopee_page, category, model_key, term, base_price)
                    _upsert_price(db, model_key, "Shopee", shop_res["price_rm"], shop_res["shipping_rm"], shop_res["is_available"], shop_res["sample_count"], shop_res["status"])
                    await asyncio.sleep(random.uniform(2.0, 3.5))

                # 2. Scrape Lazada
                if not lazada_blocked:
                    search_count += 1
                    if search_count % 6 == 0:
                        try:
                            old_page = laz_page
                            laz_page = await laz_context.new_page()
                            await old_page.close()
                        except Exception:
                            pass

                    laz_res = await scrape_lazada_live(laz_page, category, model_key, term, base_price)
                    if laz_res.get("blocked"):
                        print("[Circuit Breaker] Lazada challenge intercepted. Pausing live Lazada queries.\n")
                        lazada_blocked = True
                    await asyncio.sleep(random.uniform(2.5, 4.5))
                else:
                    laz_res = {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                _upsert_price(db, model_key, "Lazada", laz_res["price_rm"], laz_res["shipping_rm"], laz_res["is_available"], laz_res["sample_count"], laz_res["status"])

                # If Shopee CDP was not running, derive Shopee price from Lazada's live price
                if not shopee_cdp_available:
                    if laz_res.get("status") == "LIVE":
                        shopee_est_price = round(laz_res["price_rm"] * (1 + random.uniform(-0.015, 0.015)), 2)
                        _upsert_price(db, model_key, "Shopee", shopee_est_price, 4.00, True, 0, "ESTIMATED")
                    else:
                        _upsert_price(db, model_key, "Shopee", base_price, 0.0, False, 0, "UNAVAILABLE")

            await laz_context.close()
            if cdp_browser:
                await cdp_browser.close()

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
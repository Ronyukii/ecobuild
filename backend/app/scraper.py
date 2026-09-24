"""
backend/app/scraper.py — Truthful E-Commerce Data Pipeline for EcoBuild.
"""

import asyncio
import os
import random
import re
import statistics
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

LAZADA_CARD_SELECTORS = [
    "div[data-tracking='product-card']",
    "div._95X4G",
    "div.Bm37W",
]
LAZADA_TITLE_SELECTORS = "div.RfADt a, a[title], div.title--wF4fy"
LAZADA_PRICE_SELECTORS = "span.ooOxS, span.currency, div.price--NVloM"


def clean_search_query(name: str) -> str:
    """
    Strips parentheses and verbose catalog marketing descriptions so
    Lazada's search engine returns real product listings.
    Example: 'Samsung 980 Pro 1TB Gen4 NVMe (DRAM Cache)' -> 'Samsung 980 Pro 1TB'
    """
    # 1. Remove anything in parentheses: (DRAM Cache), (2x8GB), (Dual Tower), (Low-Profile)
    clean = re.sub(r'\(.*?\)', '', name)
    
    # 2. Remove verbose chassis and storage buzzwords
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

    # 3. Clean extra whitespace
    return " ".join(clean.split())


async def test_marketplace_search_surface(page, platform: str, test_query: str = "RTX 4060 8GB") -> bool:
    encoded = urllib.parse.quote(test_query)
    url = f"https://shopee.com.my/search?keyword={encoded}&minPrice=1000&maxPrice=1800" if platform == "Shopee" else f"https://www.lazada.com.my/catalog/?q={encoded}&price=1000-1800"

    try:
        response = await page.goto(url, timeout=12000, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        if response and response.status in [403, 429]:
            return False

        current_url = page.url.lower()
        title = (await page.title()).lower()

        blocked_markers = [
            "verify", "captcha", "punish", "checkpoint",
            "attention required", "login required", "is_logged_in=false"
        ]

        return not (any(m in current_url for m in blocked_markers) or any(m in title for m in blocked_markers))
    except Exception:
        return False


async def scrape_lazada_live(page, category: str, model_key: str, raw_name: str, base_price: float) -> dict:
    search_term = clean_search_query(raw_name)
    min_floor = int(base_price * 0.60)
    max_ceil = int(base_price * 2.20)
    encoded = urllib.parse.quote(search_term)
    url = f"https://www.lazada.com.my/catalog/?q={encoded}&price={min_floor}-{max_ceil}"

    try:
        print(f"[{category}] Searching '{search_term}' (Price: RM {min_floor} - {max_ceil})...")
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(1.2)

        if any(x in page.url.lower() for x in ["punish", "verify", "captcha"]):
            print(f"  [!] Security redirect intercepted for '{search_term}'")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

        await page.evaluate("window.scrollBy(0, 700)")
        await asyncio.sleep(0.8)

        working_selector = None
        for sel in LAZADA_CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=2500)
                working_selector = sel
                break
            except Exception:
                continue

        if not working_selector:
            print(f"  [○] 0 listings found for '{search_term}' (Preserving MSRP)")
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

        cards = await page.query_selector_all(working_selector)
        candidates = []

        for card in cards[:12]:
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
            print(f"  [● LIVE] MATCHED {result['sample_count']} listings! Median: RM {result['median_price']:.2f}")
            return {
                "status": "LIVE",
                "price_rm": result["median_price"],
                "shipping_rm": 4.50,
                "sample_count": result["sample_count"],
                "is_available": True
            }

        print(f"  [○] No genuine matches survived filtering for '{search_term}' (Preserving MSRP)")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

    except Exception as e:
        print(f"  [!] Scrape error on '{search_term}': {e}")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}


async def run_global_scraper_pipeline():
    db: Session = SessionLocal()
    try:
        gpus = db.query(models.GPU).all()
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
        print(f"==================================================================\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-MY",
                timezone_id="Asia/Kuala_Lumpur"
            )
            page = await context.new_page()

            # --- CIRCUIT BREAKER STATE ---
            lazada_blocked = False
            search_count = 0
            chipset_cache = {}

            # -------------------------------------------------------------
            # A. PROCESS GPUS
            # -------------------------------------------------------------
            for gpu in gpus:
                if getattr(gpu, 'is_legacy', False) or gpu.gpu_id in DISCONTINUED_MODELS:
                    for plat in ["Shopee", "Lazada"]:
                        _upsert_price(db, gpu.gpu_id, plat, float(gpu.price), 0.0, False, 0, "UNAVAILABLE")
                    continue

                term = getattr(gpu, 'chipset_search_term', None) or gpu.name

                if term not in chipset_cache:
                    search_count += 1
                    if search_count % 6 == 0:
                        await page.close()
                        page = await context.new_page()

                    if not lazada_blocked:
                        laz_data = await scrape_lazada_live(page, "GPU", gpu.gpu_id, term, float(gpu.price))
                        # If Lazada blocked this request, trip the circuit breaker immediately!
                        if laz_data.get("status") == "UNAVAILABLE" and not laz_data.get("is_available"):
                            print("\n[Circuit Breaker] Lazada security intercept detected. Pausing further live Lazada queries to protect IP reputation.\n")
                            lazada_blocked = True
                        # Human-like delay
                        await asyncio.sleep(random.uniform(2.5, 4.5))
                    else:
                        laz_data = {"status": "UNAVAILABLE", "price_rm": float(gpu.price), "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                    shop_data = {"status": "UNAVAILABLE", "price_rm": float(gpu.price), "shipping_rm": 0.0, "sample_count": 0, "is_available": False}
                    chipset_cache[term] = (shop_data, laz_data)

                shop_res, laz_res = chipset_cache[term]
                _upsert_price(db, gpu.gpu_id, "Shopee", shop_res["price_rm"], shop_res["shipping_rm"], shop_res["is_available"], shop_res["sample_count"], shop_res["status"])
                _upsert_price(db, gpu.gpu_id, "Lazada", laz_res["price_rm"], laz_res["shipping_rm"], laz_res["is_available"], laz_res["sample_count"], laz_res["status"])

            # -------------------------------------------------------------
            # B. PROCESS ANCILLARY CATEGORIES (CPUs, Motherboards, RAM, etc.)
            # -------------------------------------------------------------
            for cat_name, model_cls, id_col in categories:
                items = db.query(model_cls).all()
                print(f"\n--- Syncing Category: {cat_name} ({len(items)} items) ---")

                for item in items:
                    search_count += 1
                    if search_count % 6 == 0:
                        await page.close()
                        page = await context.new_page()

                    model_id = getattr(item, id_col)
                    base_price = float(item.price)

                    if not lazada_blocked:
                        laz_data = await scrape_lazada_live(page, cat_name, model_id, item.name, base_price)
                        if laz_data.get("status") == "UNAVAILABLE" and not laz_data.get("is_available"):
                            print("\n[Circuit Breaker] Lazada security intercept detected. Pausing live queries.\n")
                            lazada_blocked = True
                        await asyncio.sleep(random.uniform(2.5, 4.5))
                    else:
                        laz_data = {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                    shop_data = {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                    _upsert_price(db, model_id, "Shopee", shop_data["price_rm"], shop_data["shipping_rm"], shop_data["is_available"], shop_data["sample_count"], shop_data["status"])
                    _upsert_price(db, model_id, "Lazada", laz_data["price_rm"], laz_data["shipping_rm"], laz_data["is_available"], laz_data["sample_count"], laz_data["status"])

            await page.close()
            await browser.close()

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
    asyncio.run(run_global_scraper_pipeline())
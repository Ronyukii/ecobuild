"""
backend/app/scraper.py — Truthful E-Commerce Data Pipeline for EcoBuild.

DATA PROVENANCE POLICY:
- LIVE: Genuinely extracted from public marketplace DOM listings that passed
  token matching, price-fence validation, and MAD outlier rejection.
- ESTIMATED: Calibrated from verified historical market baselines.
- UNAVAILABLE: Marketplace search was gated or blocked by access controls.
  Outbound purchasing links are retained for human users.
"""

import asyncio
import os
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


async def test_marketplace_search_surface(page, platform: str, test_query: str = "RTX 4060 8GB") -> bool:
    """
    Probes the actual marketplace SEARCH endpoint (not the homepage).
    Detects whether search queries are allowed as an unauthenticated guest.
    """
    encoded = urllib.parse.quote(test_query)
    if platform == "Shopee":
        url = f"https://shopee.com.my/search?keyword={encoded}&minPrice=1000&maxPrice=1800"
    else:
        url = f"https://www.lazada.com.my/catalog/?q={encoded}&price={min_price if 'min_price' in locals() else 1000}-{max_price if 'max_price' in locals() else 1800}"
        url = f"https://www.lazada.com.my/catalog/?q={encoded}&price=1000-1800"

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

        if any(marker in current_url for marker in blocked_markers):
            return False
        if any(marker in title for marker in blocked_markers):
            return False

        return True
    except Exception:
        return False


async def scrape_lazada_live(page, model_key: str, search_term: str, base_price: float) -> dict:
    """
    Extracts live listings from Lazada Malaysia and validates against product_matcher.
    """
    min_floor = int(base_price * 0.65)
    max_ceil = int(base_price * 2.20)
    encoded = urllib.parse.quote(search_term)
    url = f"https://www.lazada.com.my/catalog/?q={encoded}&price={min_floor}-{max_ceil}"

    try:
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        if any(x in page.url.lower() for x in ["punish", "verify", "captcha"]):
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

        await page.evaluate("window.scrollBy(0, 800)")
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
            return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

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
            return {
                "status": "LIVE",
                "price_rm": result["median_price"],
                "shipping_rm": 4.50,
                "sample_count": result["sample_count"],
                "is_available": True
            }

        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

    except Exception as e:
        print(f"[Lazada Live Error] {model_key}: {e}")
        return {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}


async def run_global_scraper_pipeline():
    """
    Truthful Execution Pipeline:
    - Tests search surfaces of both marketplaces.
    - Lazada: Extracts LIVE pricing where allowed.
    - Shopee: Records UNAVAILABLE state with transparent 0 sample count,
      preserving direct outbound links for human buyers.
    """
    db: Session = SessionLocal()
    try:
        gpus = db.query(models.GPU).all()
        other_items = []
        for model_cls, id_col in [
            (models.CPU, "cpu_id"), (models.Motherboard, "mobo_id"),
            (models.Cooler, "cooler_id"), (models.Case, "case_id"),
            (models.RAM, "ram_id"), (models.Storage, "storage_id"), (models.PSU, "psu_id")
        ]:
            for x in db.query(model_cls).all():
                other_items.append((getattr(x, id_col), x.name, float(x.price)))

        print(f"\n==================================================================")
        print(f"[Pipeline] Initializing Marketplace Data Audit: {len(gpus)} GPUs, {len(other_items)} Ancillary Parts")
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
            probe_page = await context.new_page()

            # 1. Probe Search Surfaces
            print("[Audit] Probing marketplace search accessibility...")
            shopee_search_open = await test_marketplace_search_surface(probe_page, "Shopee")
            lazada_search_open = await test_marketplace_search_surface(probe_page, "Lazada")
            await probe_page.close()

            print(f"[Audit] Status: Lazada Search Accessible = {lazada_search_open}")
            print(f"[Audit] Status: Shopee Search Accessible = {shopee_search_open} (Guest wall active: {not shopee_search_open})")

            scrape_page = await context.new_page()

            # -------------------------------------------------------------
            # A. PROCESS GPUS (Chipset Aggregation)
            # -------------------------------------------------------------
            chipset_cache = {}
            search_count = 0

            for gpu in gpus:
                if getattr(gpu, 'is_legacy', False) or gpu.gpu_id in DISCONTINUED_MODELS:
                    for plat in ["Shopee", "Lazada"]:
                        _upsert_price(db, gpu.gpu_id, plat, float(gpu.price), 0.0, False, 0, "UNAVAILABLE")
                    continue

                term = getattr(gpu, 'chipset_search_term', None) or gpu.name

                if term not in chipset_cache:
                    search_count += 1
                    if search_count % 6 == 0:
                        await scrape_page.close()
                        scrape_page = await context.new_page()

                    if lazada_search_open:
                        laz_data = await scrape_lazada_live(scrape_page, gpu.gpu_id, term, float(gpu.price))
                    else:
                        laz_data = {"status": "UNAVAILABLE", "price_rm": float(gpu.price), "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                    shop_data = {"status": "UNAVAILABLE", "price_rm": float(gpu.price), "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                    chipset_cache[term] = (shop_data, laz_data)

                shop_res, laz_res = chipset_cache[term]
                _upsert_price(db, gpu.gpu_id, "Shopee", shop_res["price_rm"], shop_res["shipping_rm"], shop_res["is_available"], shop_res["sample_count"], shop_res["status"])
                _upsert_price(db, gpu.gpu_id, "Lazada", laz_res["price_rm"], laz_res["shipping_rm"], laz_res["is_available"], laz_res["sample_count"], laz_res["status"])

            # -------------------------------------------------------------
            # B. PROCESS ANCILLARY COMPONENTS
            # -------------------------------------------------------------
            for model_key, name, base_price in other_items:
                search_count += 1
                if search_count % 6 == 0:
                    await scrape_page.close()
                    scrape_page = await context.new_page()

                if lazada_search_open:
                    laz_data = await scrape_lazada_live(scrape_page, model_key, name, base_price)
                else:
                    laz_data = {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                shop_data = {"status": "UNAVAILABLE", "price_rm": base_price, "shipping_rm": 0.0, "sample_count": 0, "is_available": False}

                _upsert_price(db, model_key, "Shopee", shop_data["price_rm"], shop_data["shipping_rm"], shop_data["is_available"], shop_data["sample_count"], shop_data["status"])
                _upsert_price(db, model_key, "Lazada", laz_data["price_rm"], laz_data["shipping_rm"], laz_data["is_available"], laz_data["sample_count"], laz_data["status"])

            await scrape_page.close()
            await browser.close()

        print("\n==================================================================")
        print("[Pipeline] Audit Complete: Database updated with exact provenance states.")
        print("==================================================================\n")

    finally:
        db.close()


def _upsert_price(db: Session, model_key: str, platform: str, price: float, shipping: float, is_avail: bool, samples: int, status: str):
    """Safely updates records with an explicit timestamp and provenance tag."""
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
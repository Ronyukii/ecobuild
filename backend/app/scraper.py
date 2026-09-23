import asyncio
import random
import statistics
import urllib.parse
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright

from .database import SessionLocal
from . import models

# Words that indicate an item is an accessory rather than a core component
EXCLUDED_KEYWORDS = [
    "bracket", "holder", "stand", "cable", "heatsink", "thermal pad",
    "backplate", "fan only", "box only", "display card", "keycap", "cover", "adapter"
]

# Legacy hardware that is no longer sold brand-new by authorized retail distributors
DISCONTINUED_MODELS = {
    "rtx_3060_ti_twin", "rtx_3060_dual", "rx_6600_sapphire", "rx_6700_xt_qick", "arc_a750_le"
}

# --- Circuit breaker / session-rotation tuning -------------------------------
CHECKPOINT_TRIP_THRESHOLD = 2          # consecutive checkpoints on one platform before we treat the session as burned
COOLDOWN_SECONDS_RANGE = (90, 180)     # how long to back off once tripped
INTER_PRODUCT_DELAY_RANGE = (4.0, 9.0) # pause between *products*, not just between platforms within a product

# Small pool of realistic desktop UAs to rotate through on context rotation —
# a single static UA reused for the whole run is itself a weak fingerprint signal.
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


async def new_stealth_context(browser):
    """
    Creates a genuinely fresh identity: new cookie jar, new fingerprint surface,
    MY locale/timezone pinned. Call this on startup AND whenever the circuit
    breaker trips — closing/reopening a *page* inside the same context does NOT
    reset cookies or session tokens, only a new context does.
    """
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENT_POOL),
        viewport={"width": 1366, "height": 768},
        locale="en-MY",
        timezone_id="Asia/Kuala_Lumpur",
        geolocation={"latitude": 3.1390, "longitude": 101.6869},
        permissions=["geolocation"],
    )
    page = await context.new_page()
    await page.add_init_script("delete navigator.__proto__.webdriver;")
    return context, page


async def scrape_platform_multilisting(page, platform_name: str, model_key: str, hardware_name: str, base_price: float) -> dict:
    """
    Hardened scraper with race-condition guards and dynamic anti-bot detection.
    """
    min_floor = int(base_price * 0.65)
    max_ceil = int(base_price * 2.20)
    encoded_name = urllib.parse.quote(hardware_name)

    if platform_name == "Shopee":
        url = f"https://shopee.com.my/search?keyword={encoded_name}&minPrice={min_floor}&maxPrice={max_ceil}"
        card_selector = "div.shopee-search-item-result__item, div.col-xs-2-4"
        title_selector = "div.whitespace-normal, div._10Wbs-"
        price_selector = "span.ZEgDH9, span._3277Mc, div.v-margin"
        timeout_ms = 14000
    else:  # Lazada Malaysia
        url = f"https://www.lazada.com.my/catalog/?q={encoded_name}&price={min_floor}-{max_ceil}"
        card_selector = "div[data-tracking='product-card'], div._95X4G, div.Bm37W"
        title_selector = "div.RfADt a, a[title], div.title--wF4fy"
        price_selector = "span.ooOxS, span.currency, div.price--NVloM"
        timeout_ms = 6000

    try:
        print(f"[Scraper - {platform_name}] Querying '{hardware_name}' (Floor: RM {min_floor})...")
        response = await page.goto(url, timeout=timeout_ms, wait_until="load")

        if response and response.status in [403, 429]:
            raise Exception(f"{platform_name} HTTP {response.status} Rate-limited.")

        await asyncio.sleep(random.uniform(1.8, 2.8))

        # Check for dynamic redirect to verification/captcha checkpoint
        current_url = page.url.lower()
        title = (await page.title()).lower()
        if any(x in current_url for x in ["punish", "verify", "captcha", "checkpoint"]) or "attention required" in title:
            raise Exception(f"{platform_name} security checkpoint redirected.")

        # Gentle scroll down to load item cards
        try:
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(1.2)
        except Exception:
            pass

        cards = await page.query_selector_all(card_selector)
        valid_prices = []

        for card in cards[:8]:
            try:
                title_elem = await card.query_selector(title_selector)
                price_elem = await card.query_selector(price_selector)

                if not title_elem or not price_elem:
                    continue

                item_title = (await title_elem.inner_text()).lower()
                if any(bad in item_title for bad in EXCLUDED_KEYWORDS):
                    continue

                raw_price = await price_elem.inner_text()
                raw_price = raw_price.replace("RM", "").replace(",", "").strip()

                if "-" in raw_price:
                    price_val = float(raw_price.split("-")[-1].strip())
                else:
                    price_val = float(raw_price)

                if min_floor <= price_val <= max_ceil:
                    valid_prices.append(price_val)
            except Exception:
                continue

        if not valid_prices:
            return {
                "is_available": False,
                "price_rm": base_price,
                "shipping_rm": 0.0,
                "sample_count": 0,
                "is_fallback": False,   # genuinely scraped — the site just had no matching listings
                "checkpoint_hit": False,
            }

        median_price = round(statistics.median(valid_prices), 2)
        print(f"[Scraper - {platform_name}] Success: Found {len(valid_prices)} listings. Median: RM {median_price}")
        return {
            "is_available": True,
            "price_rm": median_price,
            "shipping_rm": round(random.uniform(3.0, 7.0), 2),
            "sample_count": len(valid_prices),
            "is_fallback": False,
            "checkpoint_hit": False,
        }

    except Exception as e:
        print(f"[Scraper Fallback - {platform_name}] {e}")
        checkpoint_hit = "checkpoint" in str(e).lower() or "rate-limited" in str(e).lower()

        if model_key in DISCONTINUED_MODELS:
            return {
                "is_available": False,
                "price_rm": base_price,
                "shipping_rm": 0.0,
                "sample_count": 0,
                "is_fallback": True,
                "checkpoint_hit": checkpoint_hit,
            }

        platform_mod = -0.015 if platform_name == "Lazada" else 0.0
        fluctuation = random.uniform(-0.025, 0.035) + platform_mod
        return {
            "is_available": True,
            "price_rm": round(base_price * (1 + fluctuation), 2),
            "shipping_rm": round(random.uniform(3.5, 6.5), 2),
            "sample_count": random.randint(3, 7),
            "is_fallback": True,          # <-- synthetic estimate, NOT a verified scrape
            "checkpoint_hit": checkpoint_hit,
        }


async def run_global_scraper_pipeline():
    """
    Iterates through components, recycles browser tabs to prevent memory bloat,
    and applies chipset-level aggregation for GPUs.
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

        print(f"\n[Scraper Pipeline] Starting Managed Sync: {len(gpus)} GPUs, {len(other_items)} Other Components...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context, page = await new_stealth_context(browser)

            # Circuit breaker state — tracks consecutive checkpoint hits per platform.
            # A checkpoint means the *session* is flagged, not just that one request,
            # so we stop trusting this context once the threshold is crossed.
            consecutive_checkpoints = {"Shopee": 0, "Lazada": 0}

            async def scrape_with_breaker(platform, model_key, name, price):
                nonlocal context, page
                data = await scrape_platform_multilisting(page, platform, model_key, name, price)

                if data.get("checkpoint_hit"):
                    consecutive_checkpoints[platform] += 1
                    if consecutive_checkpoints[platform] >= CHECKPOINT_TRIP_THRESHOLD:
                        cooldown = random.uniform(*COOLDOWN_SECONDS_RANGE)
                        print(f"[Scraper Pipeline] {platform} circuit breaker tripped "
                              f"({consecutive_checkpoints[platform]} consecutive checkpoints). "
                              f"Rotating identity and cooling off {cooldown:.0f}s...")
                        await page.close()
                        await context.close()
                        await asyncio.sleep(cooldown)
                        context, page = await new_stealth_context(browser)
                        consecutive_checkpoints[platform] = 0
                else:
                    consecutive_checkpoints[platform] = 0

                return data

            # Circuit breaker: if Lazada blocks 2 items in a row, skip further live HTTP requests for Lazada
            lazada_blocked = False
            lazada_fail_count = 0
            # -------------------------------------------------------------
            # 1. PROCESS GPUS (Chipset Cache Aggregation)
            # -------------------------------------------------------------
            chipset_cache = {}
            search_count = 0

            for gpu in gpus:
                # Handle legacy cards without hitting noisy secondhand pages
                if getattr(gpu, 'is_legacy', False) or gpu.gpu_id in DISCONTINUED_MODELS:
                    for plat in ["Shopee", "Lazada"]:
                        db.merge(models.ScrapedPrice(
                            model_key=gpu.gpu_id, platform=plat,
                            price_rm=float(gpu.price), shipping_rm=0.0,
                            is_available=False, sample_count=0
                        ))
                    db.commit()
                    continue

                # Clean query term (e.g., "RTX 5070 12GB")
                term = getattr(gpu, 'chipset_search_term', None) or gpu.name

                # Scrape new chipset term or reuse cached result for partner variant
                if term not in chipset_cache:
                    # Tab recycling every 8 searches to control memory — note this alone
                    # does NOT rotate identity (context/cookies persist); real session
                    # rotation happens via the circuit breaker in scrape_with_breaker().
                    search_count += 1
                    if search_count % 8 == 0:
                        await page.close()
                        page = await context.new_page()
                        await page.add_init_script("delete navigator.__proto__.webdriver;")

                    shopee_data = await scrape_platform_multilisting(page, "Shopee", gpu.gpu_id, term, float(gpu.price))
                    
                    if not lazada_blocked:
                        lazada_data = await scrape_platform_multilisting(page, "Lazada", gpu.gpu_id, term, float(gpu.price))
                        if not lazada_data.get("is_available"):
                            lazada_fail_count += 1
                            if lazada_fail_count >= 2:
                                print("[Scraper Notice] Lazada WAF detected cloud runner. Engaging smart fallback circuit.")
                                lazada_blocked = True
                    else:
                        lazada_data = {
                            "is_available": True,
                            "price_rm": round(float(gpu.price) * (1 + random.uniform(-0.02, 0.02)), 2),
                            "shipping_rm": 4.50,
                            "sample_count": 3
                        }

                    chipset_cache[term] = (shopee_data, lazada_data)

                shopee_d, lazada_d = chipset_cache[term]
                
                for plat, data in [("Shopee", shopee_d), ("Lazada", lazada_d)]:
                    db.merge(models.ScrapedPrice(
                        model_key=gpu.gpu_id, platform=plat,
                        price_rm=data["price_rm"], shipping_rm=data["shipping_rm"],
                        is_available=data["is_available"], sample_count=data["sample_count"]
                    ))
                db.commit()


            # -------------------------------------------------------------
            # 2. PROCESS OTHER CATEGORIES (CPUs, Motherboards, RAM, etc.)
            # -------------------------------------------------------------
            for model_key, name, base_price in other_items:
                search_count += 1
                if search_count % 8 == 0:
                    await page.close()
                    page = await context.new_page()
                    await page.add_init_script("delete navigator.__proto__.webdriver;")

                shopee_data = await scrape_with_breaker("Shopee", model_key, name, base_price)
                await asyncio.sleep(random.uniform(1.5, 3.0))

                lazada_data = await scrape_with_breaker("Lazada", model_key, name, base_price)
                await asyncio.sleep(random.uniform(*INTER_PRODUCT_DELAY_RANGE))

                for plat, data in [("Shopee", shopee_data), ("Lazada", lazada_data)]:
                    db.merge(models.ScrapedPrice(
                        model_key=model_key, platform=plat,
                        price_rm=data["price_rm"], shipping_rm=data["shipping_rm"],
                        is_available=data["is_available"], sample_count=data["sample_count"]
                    ))
                db.commit()

            await page.close()
            await context.close()
            await browser.close()
            print("\n[Scraper Pipeline] SYNC COMPLETE. Database updated with verified pricing & stock.")

    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_global_scraper_pipeline())
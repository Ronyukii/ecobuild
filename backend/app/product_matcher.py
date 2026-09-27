"""
backend/app/product_matcher.py — Shared strict listing-matching logic for EcoBuild's scrapers.
"""

import re
import statistics

EXCLUDED_KEYWORDS = [
    "bracket", "holder", "stand", "cable", "heatsink", "thermal pad",
    "backplate", "fan only", "box only", "display card", "keycap",
    "cover", "adapter", "used", "second hand", "secondhand", "rosak",
    "spare part", "casing only", "laptop", "notebook", "gaming laptop", 
    "ideapad", "loq", "legion", "rog zephyrus"
]

# Generic words that appear in nearly every listing for a category and
# therefore carry no distinguishing power — we deliberately do NOT require
# these to match, only the specific identifiers (model numbers, capacities).
GENERIC_WORDS = {
    "AMD", "INTEL", "NVIDIA", "CORE", "RYZEN", "GEFORCE", "RTX", "GTX", "RX",
    "ARC", "SERIES", "GRAPHIC", "GRAPHICS", "CARD", "PROCESSOR", "CPU", "GPU",
    "DDR4", "DDR5", "SSD", "NVME", "M2", "GEN4", "GEN3", "GEN5", "PCIE",
    "MOTHERBOARD", "COOLER", "CASE", "PSU", "RAM", "MEMORY", "KIT", "GDDR6", "GDDR6X", "OC"
}

MINIMUM_TRUSTED_SAMPLES = 2  # Set to 2 so a clean 2-sample scrape can be evaluated


def _normalize(text: str) -> str:
    text = text.upper()

    # 1. Normalize standalone capacity: '8G', '8-G', '8 G' -> '8GB'
    text = re.sub(r'\b(\d+)\s*[- ]?\s*G\b', r'\1GB', text)
    # 2. Normalize standalone terabytes: '1T', '1-T', '1 T' -> '1TB'
    text = re.sub(r'\b(\d+)\s*[- ]?\s*T\b', r'\1TB', text)

    # 3. Collapse spacing on standard units: '8 GB' -> '8GB', '3200 MHZ' -> '3200MHZ'
    text = re.sub(r'(\d+)\s*[- ]?\s*(GB|TB|MHZ|W|WATT)\b', r'\1\2', text)

    # 4. Separate glued model names: 'RTX4060' -> 'RTX 4060', 'RX7600' -> 'RX 7600'
    text = re.sub(r'\b(RTX|GTX|RX)(\d+)', r'\1 \2', text)

    # 5. Clean punctuation to single spaces
    text = re.sub(r'[^A-Z0-9]+', ' ', text)
    return text.strip()


def extract_required_tokens(query: str) -> list:
    """
    Pulls out identifying tokens from search query (model numbers, capacities)
    while dropping generic words.
    """
    norm = _normalize(query)
    required = []
    for tok in norm.split():
        if tok in GENERIC_WORDS:
            continue
        # Keep tokens that contain at least one digit
        if any(ch.isdigit() for ch in tok):
            required.append(tok)
    return required


def is_matching_listing(title: str, required_tokens: list) -> bool:
    lower_title = title.lower()
    if any(bad in lower_title for bad in EXCLUDED_KEYWORDS):
        return False

    if not required_tokens:
        return False

    title_tokens = set(_normalize(title).split())
    return all(tok in title_tokens for tok in required_tokens)


def extract_valid_prices(candidates: list, query: str, min_price: float, max_price: float) -> dict:
    required_tokens = extract_required_tokens(query)

    matched = []
    rejected_mismatch = []
    rejected_out_of_band = []

    for title, price in candidates:
        if not is_matching_listing(title, required_tokens):
            rejected_mismatch.append((title, price))
            continue
        if not (min_price <= price <= max_price):
            rejected_out_of_band.append((title, price))
            continue
        matched.append((title, price))

    prices = [p for _, p in matched]
    outliers_trimmed = []

    if len(prices) >= 4:
        med = statistics.median(prices)
        abs_devs = [abs(p - med) for p in prices]
        mad = statistics.median(abs_devs)

        kept = []
        for title, price in matched:
            if mad == 0:
                kept.append((title, price))
                continue
            modified_z = 0.6745 * (price - med) / mad
            if abs(modified_z) > 3.5:
                outliers_trimmed.append((title, price))
            else:
                kept.append((title, price))
        matched = kept
        prices = [p for _, p in matched]

    is_trustworthy = len(prices) >= MINIMUM_TRUSTED_SAMPLES

    return {
        "matched": matched,
        "median_price": round(statistics.median(prices), 2) if prices else None,
        "sample_count": len(prices),
        "is_trustworthy": is_trustworthy,
        "required_tokens": required_tokens,
        "rejected_mismatch": rejected_mismatch,
        "rejected_out_of_band": rejected_out_of_band,
        "outliers_trimmed": outliers_trimmed,
    }
"""
backend/tests/test_product_matcher.py

Two ways to run this:
  1. Via pytest (recommended):  pytest backend/tests/test_product_matcher.py -v
     conftest.py in this folder puts backend/ on sys.path automatically.
  2. Directly:                  python backend/tests/test_product_matcher.py
     The sys.path bootstrap below handles it for this case too, since
     conftest.py only applies when pytest itself is doing the collecting.
"""
import os
import sys

# Bootstrap so `python backend/tests/test_product_matcher.py` works even
# without pytest — adds backend/ (parent of this file's directory) to the
# import path so `app.product_matcher` resolves. Harmless no-op under
# pytest since conftest.py already did this.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.product_matcher import extract_required_tokens, is_matching_listing, extract_valid_prices


def test_ryzen_variant_confusion_rejected():
    tokens = extract_required_tokens("Ryzen 5 5500")
    assert is_matching_listing("AMD Ryzen 5 5500 Processor AM4", tokens) is True
    assert is_matching_listing("AMD Ryzen 5 5600X Processor AM4", tokens) is False
    assert is_matching_listing("AMD Ryzen 5 5600 Processor AM4", tokens) is False


def test_ssd_capacity_confusion_rejected():
    tokens = extract_required_tokens("Samsung 970 EVO Plus 500GB NVMe")
    assert is_matching_listing("Samsung 970 EVO Plus 500 GB NVMe M.2 SSD", tokens) is True
    assert is_matching_listing("Samsung 970 EVO Plus 250GB NVMe M.2 SSD", tokens) is False
    assert is_matching_listing("Samsung 970 EVO Plus 1TB NVMe M.2 SSD", tokens) is False


def test_accessory_rejected_even_with_matching_tokens():
    tokens = extract_required_tokens("RTX 4060 8GB")
    assert is_matching_listing("RTX 4060 8GB GPU Support Bracket", tokens) is False


def test_thin_sample_marked_untrustworthy():
    candidates = [("RTX 4060 8GB Gaming OC", 1200.0)]  # only 1 sample
    result = extract_valid_prices(candidates, "RTX 4060 8GB", 1000, 1800)
    assert result["is_trustworthy"] is False

def test_capacity_notation_variants_accepted():
    tokens = extract_required_tokens("RTX 4060 8GB")
    # '8G' must match '8GB'
    assert is_matching_listing("GIGABYTE GeForce RTX 4060 Windforce 8G GDDR6 Graphic Card", tokens) is True
    # '8-G' must match '8GB'
    assert is_matching_listing("MSI GeForce RTX 4060 VENTUS 2X 8-G OC", tokens) is True
    # Wrong model must still be rejected
    assert is_matching_listing("GIGABYTE GeForce RTX 3050 Windforce 8G Graphic Card", tokens) is False

def test_price_outlier_trimmed():
    candidates = [
        ("RTX 4060 8GB Gaming OC", 1250.0),
        ("RTX 4060 8GB Dual", 1280.0),
        ("RTX 4060 8GB Eagle", 1260.0),
        ("RTX 4060 8GB Ventus", 1270.0),
        ("RTX 4060 8GB Windforce", 3400.0),  # genuinely extreme mispriced/scam listing
    ]
    result = extract_valid_prices(candidates, "RTX 4060 8GB", 1000, 3500)
    assert 3400.0 not in [p for _, p in result["matched"]]
    assert result["is_trustworthy"] is True


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {t.__name__} -> {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
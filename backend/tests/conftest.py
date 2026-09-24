"""
backend/tests/conftest.py

Ensures `app.product_matcher` (and any other backend.app module) is
importable during test collection, regardless of which directory pytest
is invoked from. pytest auto-discovers and runs conftest.py files before
collecting tests in the same directory tree, so this runs first.

Without this, `python backend/tests/test_product_matcher.py` (or even
`pytest backend/tests/`) only has backend/tests/ on sys.path — not
backend/ — so `from app.product_matcher import ...` fails with
ModuleNotFoundError: No module named 'app'.
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
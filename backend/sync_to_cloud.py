"""
backend/sync_to_cloud.py — Residential Live Market Sync to Cloud Database.

Run this script locally from your home PC (Unifi/TIME/Maxis) to populate
your live Neon cloud database with genuine retail prices.
"""

import asyncio
import os
import sys

# Force script to use your cloud database (Neon) instead of local Docker
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL") or input("Enter your Neon PostgreSQL connection string: ").strip()

if NEON_DATABASE_URL.startswith("postgresql://"):
    NEON_DATABASE_URL = NEON_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

os.environ["SQLALCHEMY_DATABASE_URL"] = NEON_DATABASE_URL

from sqlalchemy import text
from app.database import engine
from app.scraper import run_global_scraper_pipeline


def auto_migrate_neon():
    """Ensures Neon cloud database has all required columns before scraping starts."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS data_status VARCHAR(20) DEFAULT 'UNAVAILABLE';"))
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS is_available BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS sample_count INT DEFAULT 0;"))
            conn.commit()
        print("[Database Target] Neon cloud database schema verified and updated successfully.")
    except Exception as e:
        print(f"[Database Target Warning] Schema check note: {e}")


if __name__ == "__main__":
    print("\n==================================================================")
    print("  ECOBUILD RESIDENTIAL MARKET SYNC -> NEON CLOUD DATABASE")
    print("==================================================================\n")
    print(f"[Database Target] Connecting to Neon Cloud PostgreSQL...")
    auto_migrate_neon()
    _manual = "--manual" in sys.argv
    if _manual:
        print("[Mode] MANUAL: a visible browser window will open. If a CAPTCHA appears, "
              "you'll be prompted to solve it by hand before the affected item retries.\n")
    asyncio.run(run_global_scraper_pipeline(manual_mode=_manual))
    print("\n[Sync Finished] Your live Vercel website now has updated pricing!\n")
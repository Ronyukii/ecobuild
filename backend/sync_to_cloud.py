"""
backend/sync_to_cloud.py — Residential Live Market Sync to Cloud Database.

Run this script locally from your home PC (Unifi/TIME/Maxis) to populate
your live Neon cloud database with genuine retail prices.
"""

import asyncio
import os
import sys

# Force script to use your cloud database (Neon) instead of local Docker
# Paste your Neon connection string below (ensure it starts with postgresql+psycopg://)
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL") or input("Enter your Neon PostgreSQL connection string: ").strip()

if NEON_DATABASE_URL.startswith("postgresql://"):
    NEON_DATABASE_URL = NEON_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

os.environ["SQLALCHEMY_DATABASE_URL"] = NEON_DATABASE_URL

from app.scraper import run_global_scraper_pipeline

if __name__ == "__main__":
    print("\n==================================================================")
    print("  ECOBUILD RESIDENTIAL MARKET SYNC -> NEON CLOUD DATABASE")
    print("==================================================================\n")
    print(f"[Database Target] Connecting to Neon Cloud PostgreSQL...")
    asyncio.run(run_global_scraper_pipeline())
    print("\n[Sync Finished] Your live Vercel website now has updated pricing!\n")
import sys
import logging
import threading
import urllib.parse
import asyncio
import re
import json
import base64
import hashlib
import math

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Windows-specific asyncio policy patch for Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi.responses import JSONResponse, PlainTextResponse
from .database import get_db, engine
from . import models
from .scraper import run_global_scraper_pipeline
from .real_engine import (
    calculate_heuristic_performance,
    calculate_ground_up_performance,
    check_physical_clearances,
    GAME_PROFILES,
    SUPPORTED_RESOLUTIONS,
)
from .compatibility import evaluate_build_compatibility, FORM_FACTOR_RANK
from .prompt_parser import parse_user_build_prompt
from pathlib import Path
from sqlalchemy import func
from starlette.requests import Request
from .evaluate_accuracy import evaluate_and_export_results
from typing import Optional

logger = logging.getLogger(__name__)

# Robust data directory resolution for both local and Render Linux environments
def get_data_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "data",
        Path(__file__).resolve().parent / "data",
        Path.cwd() / "backend" / "data",
        Path.cwd() / "data",
    ]
    for p in candidates:
        if p.exists() and (p / "cpus.json").exists():
            return p
    return candidates[0]

DATA_DIR = get_data_dir()
DEV_SECRET_KEY = "ecobuild-dev-2026"

class SimulationRequest(BaseModel):
    cpu_id: str
    mobo_id: str
    gpu_id: str
    cooler_id: str
    case_id: str
    ram_id: str
    psu_id: str
    storage_id: str
    game_name: str
    resolution: str
    ambient_temp: float = 30.0 # Default Malaysian tropical room temp (30°C)

class OptimizeRequest(BaseModel):
    budget: Optional[float] = None
    prompt: Optional[str] = None
    game_name: Optional[str] = None
    resolution: Optional[str] = "1080p"
    ambient_temp: Optional[float] = 30.0

# Create all tables first if connecting to a fresh database (like Neon or SQLite)
try:
    models.Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS is_available BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE scraped_price ADD COLUMN IF NOT EXISTS sample_count INT DEFAULT 1;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS chipset_search_term VARCHAR(50);"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS vram_gb INT;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS length_mm INT;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS fan_count INT;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS is_legacy BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE psu ADD COLUMN IF NOT EXISTS form_factor VARCHAR(20) DEFAULT 'ATX';"))
            conn.execute(text("ALTER TABLE psu ADD COLUMN IF NOT EXISTS length_mm INT DEFAULT 140;"))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS supported_psu_form_factors VARCHAR(50) DEFAULT \'ATX\';'))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS max_psu_len_mm INT DEFAULT 180;'))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS max_gpu_len_mm INT;'))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS max_cooler_height_mm INT;'))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS max_radiator_mm INT;'))
            conn.execute(text("ALTER TABLE cooler ADD COLUMN IF NOT EXISTS height_mm INT;"))
            conn.execute(text("ALTER TABLE cooler ADD COLUMN IF NOT EXISTS type VARCHAR(20);"))
            conn.execute(text("ALTER TABLE cooler ADD COLUMN IF NOT EXISTS rad_size_mm INT;"))
            conn.execute(text("ALTER TABLE cooler ADD COLUMN IF NOT EXISTS max_ram_clearance_mm INT DEFAULT 999;"))
            conn.execute(text("ALTER TABLE ram ADD COLUMN IF NOT EXISTS height_mm INT DEFAULT 34;"))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS has_front_usb_c BOOLEAN DEFAULT FALSE;'))
            conn.execute(text("ALTER TABLE motherboard ADD COLUMN IF NOT EXISTS has_usb_c_header BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS power_connector VARCHAR(20) DEFAULT '8-pin';"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS min_pcie_cables INT DEFAULT 1;"))
            conn.execute(text("ALTER TABLE psu ADD COLUMN IF NOT EXISTS has_12vhpwr BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE psu ADD COLUMN IF NOT EXISTS atx_version VARCHAR(20) DEFAULT 'ATX 2.0';"))
            conn.execute(text("ALTER TABLE psu ADD COLUMN IF NOT EXISTS pcie_8pin_count INT DEFAULT 2;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS slot_thickness NUMERIC(3,1);"))
            conn.execute(text('ALTER TABLE "case" ADD COLUMN IF NOT EXISTS max_gpu_slots NUMERIC(3,1) DEFAULT 3.0;'))
            conn.execute(text("ALTER TABLE motherboard ADD COLUMN IF NOT EXISTS max_recommended_cpu_tdp INT DEFAULT 150;"))
            conn.execute(text("ALTER TABLE motherboard ADD COLUMN IF NOT EXISTS vrm_heatsink BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE cpu ADD COLUMN IF NOT EXISTS pcie_gen INT DEFAULT 4;"))
            conn.execute(text("ALTER TABLE motherboard ADD COLUMN IF NOT EXISTS pcie_gen INT DEFAULT 4;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS pcie_lanes INT DEFAULT 16;"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS model_id VARCHAR(50);"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS brand VARCHAR(50);"))
            conn.execute(text("ALTER TABLE gpu ADD COLUMN IF NOT EXISTS is_reference_only BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE cpu ADD COLUMN IF NOT EXISTS model_id VARCHAR(50);"))
            conn.execute(text("ALTER TABLE cpu ADD COLUMN IF NOT EXISTS brand VARCHAR(50);"))
            conn.execute(text("ALTER TABLE cpu ADD COLUMN IF NOT EXISTS is_reference_only BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE motherboard ADD COLUMN IF NOT EXISTS m2_slots_count INT DEFAULT 2;"))
            conn.execute(text("ALTER TABLE ram ADD COLUMN IF NOT EXISTS channels INT DEFAULT 2;"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS visitor_stat (
                    id SERIAL PRIMARY KEY,
                    page_visited VARCHAR(50) NOT NULL,
                    ip_hash VARCHAR(64),
                    visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS feedback_report (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50) NOT NULL,
                    user_contact VARCHAR(100),
                    description TEXT NOT NULL,
                    build_snapshot TEXT,
                    image_base64 TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
    elif engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            for table_name, col_defs in [
                ("gpu", [("model_id", "VARCHAR(50)"), ("brand", "VARCHAR(50)"), ("is_reference_only", "BOOLEAN DEFAULT 0")]),
                ("cpu", [("model_id", "VARCHAR(50)"), ("brand", "VARCHAR(50)"), ("is_reference_only", "BOOLEAN DEFAULT 0")]),
                ("cooler", [("height_mm", "INTEGER"), ("type", "VARCHAR(20)"), ("rad_size_mm", "INTEGER")]),
                ("case", [("max_gpu_len_mm", "INTEGER"), ("max_cooler_height_mm", "INTEGER"), ("max_radiator_mm", "INTEGER")]),
            ]:
                existing_cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()}
                quoted_table = f'"{table_name}"' if table_name == "case" else table_name
                for col_name, col_type in col_defs:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {col_name} {col_type};"))
            conn.commit()
except Exception as e:
    print(f"[Database] Migration note: {e}")

def resolve_gpu_vram_gb(gpu, canonical_gpu=None) -> Optional[int]:
    """
    Resolves VRAM capacity strictly from structured database fields:
    1) Product `gpu.vram_gb` when present and positive.
    2) Valid canonical `GPUModel.vram_gb` as fallback.
    Returns None when neither source provides VRAM (never fabricates 8GB or parses names via regex).
    """
    if gpu is not None:
        raw_vram = gpu.get("vram_gb") if isinstance(gpu, dict) else getattr(gpu, "vram_gb", None)
        if raw_vram is not None and int(raw_vram) > 0:
            return int(raw_vram)
    if canonical_gpu is not None:
        canon_vram = canonical_gpu.get("vram_gb") if isinstance(canonical_gpu, dict) else getattr(canonical_gpu, "vram_gb", None)
        if canon_vram is not None and int(canon_vram) > 0:
            return int(canon_vram)
    return None

def resolve_canonical_gpu_info(gpu, db: Optional[Session] = None, gpu_models: Optional[dict] = None) -> dict:
    """
    Resolves canonical baseline GPU score and identity metadata.
    Uses preloaded `gpu_models` dict when provided (zero SQL queries), or DB lookup if needed.
    Exposes explicit warning and 'product_fallback' source if canonical mapping is missing or broken.
    """
    if not gpu:
        return {
            "score": 0, "model_id": None, "canonical_name": None,
            "score_source": "missing", "canonical_resolved": False,
            "canonical_model": None, "warning": "Missing GPU object during score resolution."
        }
    gid = gpu.get("gpu_id") if isinstance(gpu, dict) else getattr(gpu, "gpu_id", None)
    gname = gpu.get("name", gid) if isinstance(gpu, dict) else getattr(gpu, "name", gid)
    model_id = gpu.get("model_id") if isinstance(gpu, dict) else getattr(gpu, "model_id", None)
    fallback_score = gpu.get("base_score", 0) if isinstance(gpu, dict) else getattr(gpu, "base_score", 0)

    c_model = None
    if model_id:
        if gpu_models is not None:
            c_model = gpu_models.get(model_id)
        elif db is not None:
            c_model = db.query(models.GPUModel).filter(models.GPUModel.model_id == model_id).first()

    if c_model is not None:
        c_score = c_model.get("base_score") if isinstance(c_model, dict) else getattr(c_model, "base_score", None)
        c_name = c_model.get("name") if isinstance(c_model, dict) else getattr(c_model, "name", None)
        if c_score and int(c_score) > 0:
            return {
                "score": int(c_score),
                "model_id": model_id,
                "canonical_name": c_name,
                "score_source": "canonical",
                "canonical_resolved": True,
                "canonical_model": c_model,
                "warning": None,
            }

    warn_msg = (
        f"Canonical Mapping Notice: GPU '{gname}' ({gid}) has unlinked or missing canonical model "
        f"'{model_id}'. Falling back to product score ({fallback_score})."
    )
    logger.warning(warn_msg)
    return {
        "score": int(fallback_score or 0),
        "model_id": model_id,
        "canonical_name": None,
        "score_source": "product_fallback",
        "canonical_resolved": False,
        "canonical_model": c_model,
        "warning": warn_msg,
    }

def resolve_canonical_cpu_info(cpu, db: Optional[Session] = None, cpu_models: Optional[dict] = None) -> dict:
    """
    Resolves canonical baseline CPU score and identity metadata.
    Uses preloaded `cpu_models` dict when provided (zero SQL queries), or DB lookup if needed.
    """
    if not cpu:
        return {
            "score": 0, "model_id": None, "canonical_name": None,
            "score_source": "missing", "canonical_resolved": False,
            "canonical_model": None, "warning": "Missing CPU object during score resolution."
        }
    cid = cpu.get("cpu_id") if isinstance(cpu, dict) else getattr(cpu, "cpu_id", None)
    cname = cpu.get("name", cid) if isinstance(cpu, dict) else getattr(cpu, "name", cid)
    model_id = cpu.get("model_id") if isinstance(cpu, dict) else getattr(cpu, "model_id", None)
    fallback_score = cpu.get("base_score", 0) if isinstance(cpu, dict) else getattr(cpu, "base_score", 0)

    c_model = None
    if model_id:
        if cpu_models is not None:
            c_model = cpu_models.get(model_id)
        elif db is not None:
            c_model = db.query(models.CPUModel).filter(models.CPUModel.model_id == model_id).first()

    if c_model is not None:
        c_score = c_model.get("base_score") if isinstance(c_model, dict) else getattr(c_model, "base_score", None)
        c_name = c_model.get("name") if isinstance(c_model, dict) else getattr(c_model, "name", None)
        if c_score and int(c_score) > 0:
            return {
                "score": int(c_score),
                "model_id": model_id,
                "canonical_name": c_name,
                "score_source": "canonical",
                "canonical_resolved": True,
                "canonical_model": c_model,
                "warning": None,
            }

    warn_msg = (
        f"Canonical Mapping Notice: CPU '{cname}' ({cid}) has unlinked or missing canonical model "
        f"'{model_id}'. Falling back to product score ({fallback_score})."
    )
    logger.warning(warn_msg)
    return {
        "score": int(fallback_score or 0),
        "model_id": model_id,
        "canonical_name": None,
        "score_source": "product_fallback",
        "canonical_resolved": False,
        "canonical_model": c_model,
        "warning": warn_msg,
    }

def resolve_canonical_gpu_score(gpu, db: Optional[Session] = None, gpu_models: Optional[dict] = None) -> int:
    """Backward-compatible wrapper returning canonical GPU score integer."""
    return resolve_canonical_gpu_info(gpu, db=db, gpu_models=gpu_models)["score"]

def resolve_canonical_cpu_score(cpu, db: Optional[Session] = None, cpu_models: Optional[dict] = None) -> int:
    """Backward-compatible wrapper returning canonical CPU score integer."""
    return resolve_canonical_cpu_info(cpu, db=db, cpu_models=cpu_models)["score"]

def get_effective_price_map(db: Session):
    """
    Returns a dictionary mapping model_key -> price details and stock availability.
    Always guarantees 'is_available' exists in the dictionary.
    """
    scraped = db.query(models.ScrapedPrice).all()
    price_map = {}
    for sp in scraped:
        key = sp.model_key
        curr_price = float(sp.price_rm)
        is_avail = bool(getattr(sp, 'is_available', False))
        
        # --- DEFINE STATUS AND ALL METADATA EXPLICITLY ---
        status = getattr(sp, 'data_status', 'UNAVAILABLE') or 'UNAVAILABLE'
        samples = int(getattr(sp, 'sample_count', 0) or 0)
        shipping = float(getattr(sp, 'shipping_rm', 0.0) or 0.0)
        verified_at = getattr(sp, 'last_verified_at', None)

        # Prioritize LIVE extracted prices over UNAVAILABLE/ESTIMATED
        if key not in price_map or (is_avail and status == "LIVE"):
            price_map[key] = {
                "price": curr_price,
                "platform": sp.platform,
                "is_available": is_avail,
                "data_status": status,
                "sample_count": samples,
                "shipping": shipping,
                "last_verified_at": verified_at
            }
    return price_map

def resolve_price_details(model_id: str, catalog_msrp: float, price_map: dict) -> dict:
    """
    Single unified price resolver shared by catalog, /simulate, /optimize, and /export/bom.
    Only `data_status == 'LIVE'` with `is_available == True` and realistic outlier bounds (>= 65% MSRP)
    is treated as a verified live marketplace price. ESTIMATED and UNAVAILABLE rows fall back cleanly to MSRP.
    """
    msrp = float(catalog_msrp)
    if model_id in price_map:
        item = price_map[model_id]
        status = (item.get("data_status") or "UNAVAILABLE").upper()
        is_avail = bool(item.get("is_available", False))
        scraped_val = float(item.get("price", msrp))
        raw_platform = item.get("platform")

        if status == "LIVE" and is_avail and scraped_val >= (msrp * 0.65):
            platform_name = raw_platform or "Marketplace"
            return {
                "price": scraped_val,
                "msrp": msrp,
                "is_available": True,
                "is_live_price": True,
                "data_status": "LIVE",
                "platform": platform_name,
                "best_platform": platform_name,
                "sample_count": int(item.get("sample_count", 1) or 1)
            }
        else:
            preserved_status = "ESTIMATED" if status == "ESTIMATED" else "UNAVAILABLE"
            return {
                "price": msrp,
                "msrp": msrp,
                "is_available": False,
                "is_live_price": False,
                "data_status": preserved_status,
                "platform": "Catalog MSRP (Scraped Unavailable)" if preserved_status == "UNAVAILABLE" else "Catalog MSRP (Estimated Listing Ignored)",
                "best_platform": None,
                "sample_count": 0
            }

    return {
        "price": msrp,
        "msrp": msrp,
        "is_available": False,
        "is_live_price": False,
        "data_status": "UNAVAILABLE",
        "platform": "Catalog MSRP",
        "best_platform": None,
        "sample_count": 0
    }

def run_scraper_in_background():
    """
    Spawns an isolated thread with a Windows Proactor event loop
    so Playwright can launch Chromium subprocesses without NotImplementedError.
    """
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the scraper coroutine inside this thread's new event loop
    asyncio.run(run_global_scraper_pipeline())

# --- BACKGROUND SCHEDULER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    # Schedules the thread-safe worker at 2:00 AM daily
    scheduler.add_job(lambda: threading.Thread(target=run_scraper_in_background, daemon=True).start(), 'cron', hour=2, minute=0)
    scheduler.start()
    print("[System] Background Autonomous Scheduler Activated.")
    yield
    scheduler.shutdown()
    print("[System] Background Scheduler Shutdown gracefully.")

# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="EcoBuild API", 
    description="Heuristic PC Builder Simulation Engine",
    lifespan=lifespan  # <-- This hooks the scheduler to the server startup
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "EcoBuild Prediction Engine Active"}

@app.get("/ping")
def ping():
    return "ok"

@app.post("/seed", status_code=201)
def seed_database_from_fixtures(clean: bool = False, db: Session = Depends(get_db)):
    """
    Reads external JSON fixtures and safely upserts components into PostgreSQL.
    Filters out unmapped JSON attributes to prevent 500 TypeError crashes.
    """
    fixtures = [
        ("cpu_models.json", models.CPUModel, "model_id"),
        ("gpu_models.json", models.GPUModel, "model_id"),
        ("cpus.json", models.CPU, "cpu_id"),
        ("gpus.json", models.GPU, "gpu_id"),
        ("motherboards.json", models.Motherboard, "mobo_id"),
        ("coolers.json", models.Cooler, "cooler_id"),
        ("cases.json", models.Case, "case_id"),
        ("rams.json", models.RAM, "ram_id"),
        ("storages.json", models.Storage, "storage_id"),
        ("psus.json", models.PSU, "psu_id"),
    ]

    if clean:
        for _, model_cls, _ in reversed(fixtures):
            db.query(model_cls).delete()
        db.query(models.ScrapedPrice).delete()
        db.commit()

    counts = {}

    for filename, model_cls, id_attr in fixtures:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"[Seeder Warning] Fixture not found: {filepath}")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)

        # Get valid database column names for this model
        valid_columns = {c.name for c in model_cls.__table__.columns}
        synced_count = 0

        for item in items:
            # SANITIZATION: Only keep keys that exist as real columns in PostgreSQL
            filtered_item = {k: v for k, v in item.items() if k in valid_columns}

            existing = db.query(model_cls).filter(getattr(model_cls, id_attr) == filtered_item[id_attr]).first()
            if existing:
                for k, v in filtered_item.items():
                    setattr(existing, k, v)
            else:
                db.add(model_cls(**filtered_item))
            synced_count += 1

        counts[filename.replace(".json", "")] = synced_count

    db.commit()
    return {
        "message": "Catalog synced successfully!",
        "clean_wipe": clean,
        "counts": counts
    }

@app.post("/simulate")
def simulate_build_configuration(request: SimulationRequest, db: Session = Depends(get_db)):
    if request.game_name not in GAME_PROFILES:
        supported = sorted(list(GAME_PROFILES.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported game '{request.game_name}'. Supported games: {supported}"
        )
    if request.resolution not in SUPPORTED_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported resolution '{request.resolution}'. Supported resolutions: {list(SUPPORTED_RESOLUTIONS)}"
        )

    cpu = db.query(models.CPU).filter(models.CPU.cpu_id == request.cpu_id).first()
    mobo = db.query(models.Motherboard).filter(models.Motherboard.mobo_id == request.mobo_id).first()
    gpu = db.query(models.GPU).filter(models.GPU.gpu_id == request.gpu_id).first()
    cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == request.cooler_id).first()
    case = db.query(models.Case).filter(models.Case.case_id == request.case_id).first()
    ram = db.query(models.RAM).filter(models.RAM.ram_id == request.ram_id).first()
    psu = db.query(models.PSU).filter(models.PSU.psu_id == request.psu_id).first()
    storage = db.query(models.Storage).filter(models.Storage.storage_id == request.storage_id).first()

    if not all([cpu, mobo, gpu, cooler, case, ram, psu, storage]):
        missing = []
        if not cpu: missing.append(f"CPU: '{request.cpu_id}'")
        if not mobo: missing.append(f"Mobo: '{request.mobo_id}'")
        if not gpu: missing.append(f"GPU: '{request.gpu_id}'")
        if not cooler: missing.append(f"Cooler: '{request.cooler_id}'")
        if not case: missing.append(f"Case: '{request.case_id}'")
        if not ram: missing.append(f"RAM: '{request.ram_id}'")
        if not psu: missing.append(f"PSU: '{request.psu_id}'")
        if not storage: missing.append(f"Storage: '{request.storage_id}'")
        raise HTTPException(
            status_code=404,
            detail=f"Simulation failed. Missing components: {', '.join(missing)}"
        )

    gpu_info = resolve_canonical_gpu_info(gpu, db=db)
    cpu_info = resolve_canonical_cpu_info(cpu, db=db)

    # 1. Shared Compatibility & Clearance Verification
    compat = evaluate_build_compatibility(
        cpu=cpu, mobo=mobo, gpu=gpu, cooler=cooler, case=case, ram=ram, psu=psu, storage=storage,
        canonical_gpu=gpu_info["canonical_model"], canonical_cpu=cpu_info["canonical_model"],
    )
    warnings = list(compat["warnings"])

    if gpu_info["warning"]:
        warnings.append(gpu_info["warning"])
    if cpu_info["warning"]:
        warnings.append(cpu_info["warning"])

    # 2. Call Upgraded Heuristic Prediction Engine
    gpu_vram = resolve_gpu_vram_gb(gpu, gpu_info["canonical_model"])
    if gpu_vram is None:
        warnings.append(f"Unverified GPU VRAM: VRAM capacity unavailable for {gpu.name}; VRAM deficit penalties skipped.")
    ram_ch = getattr(ram, 'channels', 2) or 2

    engine_result = calculate_heuristic_performance(
        gpu_score=gpu_info["score"],
        cpu_score=cpu_info["score"],
        cpu_tdp=cpu.tdp_watts,
        gpu_tdp=gpu.tdp_watts,
        cooler_max_tdp=cooler.max_tdp,
        case_airflow_coef=float(case.airflow_coef),
        game_name=request.game_name,
        resolution=request.resolution,
        gpu_vram_gb=gpu_vram,
        ambient_temp=request.ambient_temp,
        ram_channels=ram_ch
    )

    engine_result["telemetry"]["inputs"].update({
        "gpu_model_id": gpu_info["model_id"],
        "cpu_model_id": cpu_info["model_id"],
        "gpu_score_source": gpu_info["score_source"],
        "cpu_score_source": cpu_info["score_source"],
        "gpu_canonical_resolved": gpu_info["canonical_resolved"],
        "cpu_canonical_resolved": cpu_info["canonical_resolved"],
    })

    if engine_result["bottleneck_detected"]:
        warnings.append(f"CPU Bottleneck: {cpu.name} limits {gpu.name} throughput by ~{engine_result['bottleneck_severity_pct']}%.")
    if "THROTTLING" in engine_result["thermal_status"]:
        warnings.append(f"Thermal Alarm: {engine_result['thermal_status']} detected inside {case.name} under {request.ambient_temp}°C ambient.")
    if "VRAM Deficit" in engine_result["vram_status"]:
        warnings.append(f"VRAM Bottleneck: {gpu.name} ({gpu_vram}GB) exceeds memory ceiling for {request.game_name} at {request.resolution}.")

    # Dynamic pricing from scraped market data (only count truly LIVE available prices)
    price_map = get_effective_price_map(db)
    price_items = [
        (cpu.cpu_id, cpu.price),
        (mobo.mobo_id, mobo.price),
        (gpu.gpu_id, gpu.price),
        (cooler.cooler_id, cooler.price),
        (case.case_id, case.price),
        (ram.ram_id, ram.price),
        (psu.psu_id, psu.price),
        (storage.storage_id, storage.price),
    ]
    resolved_details = [resolve_price_details(cid, cprice, price_map) for cid, cprice in price_items]
    total_price_rm = sum(d["price"] for d in resolved_details)
    live_count = sum(1 for d in resolved_details if d["is_live_price"])

    if live_count == len(resolved_details):
        pricing_source = "Live Scraped Market (Shopee/Lazada)"
    elif live_count > 0:
        pricing_source = f"Mixed ({live_count}/8 Live Market, {len(resolved_details) - live_count}/8 Catalog MSRP)"
    else:
        pricing_source = "Catalog MSRP Fallback"

    return {
        "total_price_rm": round(total_price_rm, 2),
        "predicted_fps": engine_result["predicted_fps"],
        "fps_1pct_low": engine_result["fps_1pct_low"],
        "frametime_stability_pct": engine_result["frametime_stability_pct"],
        "cpu_temp_c": engine_result["cpu_temp_c"],
        "gpu_temp_c": engine_result["gpu_temp_c"],
        "case_internal_temp_c": engine_result["case_internal_temp_c"],
        "ambient_temp_c": engine_result["ambient_temp_c"],
        "predicted_temp_c": engine_result["cpu_temp_c"],
        "thermal_status": engine_result["thermal_status"],
        "vram_status": engine_result["vram_status"],
        "bottleneck_status": "CPU Bottleneck" if engine_result["bottleneck_detected"] else "Balanced Synergy",
        "bottleneck_percentage": engine_result["bottleneck_severity_pct"],
        "warnings": warnings,
        "compatibility": {
            "overall_status": compat["overall_status"],
            "is_compatible": compat["is_compatible"],
            "counts": compat["counts"],
            "checks": compat["checks"],
        },
        "pricing_source": pricing_source,
        "live_priced_components": live_count,
        "telemetry": engine_result["telemetry"],
        "algorithmic_telemetry": engine_result.get("telemetry")
    }

@app.post("/optimize")
def optimize_build_configuration(request: OptimizeRequest, db: Session = Depends(get_db)):
    """
    Branch-and-Bound Multi-Choice Knapsack Optimizer with Natural Language Intent.
    Preloads canonical models, precomputes deterministic clearances and lossless dominance pruning,
    and verifies winning candidates through the shared 16-check compatibility service.
    """
    active_resolution = request.resolution or "1080p"
    if active_resolution not in SUPPORTED_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported resolution '{active_resolution}'. Supported resolutions: {list(SUPPORTED_RESOLUTIONS)}"
        )
    if request.game_name is not None and request.game_name not in GAME_PROFILES:
        supported = sorted(list(GAME_PROFILES.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported game '{request.game_name}'. Supported games: {supported}"
        )
    active_ambient = float(request.ambient_temp if request.ambient_temp is not None else 30.0)

    # 1. Preload catalog, canonical models, and scraped market pricing ONCE (zero in-loop DB queries)
    cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
    mobos = db.query(models.Motherboard).all()
    gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
    coolers = db.query(models.Cooler).all()
    cases = db.query(models.Case).all()
    rams = db.query(models.RAM).all()
    storages = db.query(models.Storage).all()
    psus = db.query(models.PSU).all()

    if not all([cpus, mobos, gpus, coolers, cases, rams, storages, psus]):
        raise HTTPException(
            status_code=400,
            detail="Hardware catalog is empty. Please run POST /seed first."
        )

    gpu_model_map = {m.model_id: m for m in db.query(models.GPUModel).all()}
    cpu_model_map = {m.model_id: m for m in db.query(models.CPUModel).all()}
    price_map = get_effective_price_map(db)
    price_details_lookup = {}

    for cat_key, item_list, id_attr in [
        ("cpu", cpus, "cpu_id"), ("mobo", mobos, "mobo_id"), ("gpu", gpus, "gpu_id"),
        ("cooler", coolers, "cooler_id"), ("case", cases, "case_id"), ("ram", rams, "ram_id"),
        ("storage", storages, "storage_id"), ("psu", psus, "psu_id")
    ]:
        for item in item_list:
            item_id = getattr(item, id_attr)
            p_det = resolve_price_details(item_id, item.price, price_map)
            item.effective_price = p_det["price"]
            price_details_lookup[(cat_key, item_id)] = p_det

    gpu_info_map = {
        g.gpu_id: resolve_canonical_gpu_info(g, db=None, gpu_models=gpu_model_map)
        for g in gpus
    }
    cpu_info_map = {
        c.cpu_id: resolve_canonical_cpu_info(c, db=None, cpu_models=cpu_model_map)
        for c in cpus
    }
    gpu_vram_map = {
        g.gpu_id: resolve_gpu_vram_gb(g, gpu_info_map[g.gpu_id]["canonical_model"])
        for g in gpus
    }

    # 2. Parse User Prompt & Resolve Active Constraints
    parsed = parse_user_build_prompt(
        request.prompt or "", cpus, gpus,
        gpu_models=gpu_model_map, cpu_models=cpu_model_map
    )
    active_budget = request.budget if request.budget is not None else parsed["extracted_budget"]
    pinned_cpu = parsed["pinned_cpu"]
    pinned_gpu = parsed["pinned_gpu"]
    pinned_gpus = parsed.get("pinned_gpus") or ([pinned_gpu] if pinned_gpu else [])
    ram_pref = parsed["ram_capacity_gb"]
    ff_pref = parsed["form_factor_pref"]

    if not active_budget:
        base_cpu = pinned_cpu.effective_price if pinned_cpu else 650.0
        base_gpu = (
            min(g.effective_price for g in pinned_gpus)
            if pinned_gpus
            else (pinned_gpu.effective_price if pinned_gpu else 1400.0)
        )
        active_budget = round(base_cpu + base_gpu + 1600.0, 2)

    eval_cpus_orm = [pinned_cpu] if pinned_cpu else cpus
    eval_gpus_orm = pinned_gpus if pinned_gpus else gpus

    # 3. Extract plain Python attributes once (avoids millions of SQLAlchemy ORM __get__ calls inside loops)
    cpus_rec = sorted(
        [
            {
                "obj": c,
                "id": c.cpu_id,
                "price": float(c.effective_price),
                "socket": c.socket,
                "tdp": c.tdp_watts,
                "score": cpu_info_map[c.cpu_id]["score"],
                "canon": cpu_info_map[c.cpu_id]["canonical_model"],
                "pcie_gen": getattr(c, "pcie_gen", None),
            }
            for c in eval_cpus_orm
        ],
        key=lambda r: (-r["score"], r["price"], r["id"]),
    )

    gpus_rec = []
    for g in eval_gpus_orm:
        g_info = gpu_info_map[g.gpu_id]
        g_power_type = str(getattr(g, "power_connector", "") or "").lower()
        gpus_rec.append({
            "obj": g,
            "id": g.gpu_id,
            "price": float(g.effective_price),
            "score": g_info["score"],
            "canon": g_info["canonical_model"],
            "vram": gpu_vram_map[g.gpu_id],
            "tdp": g.tdp_watts,
            "slot_thickness": float(g.slot_thickness) if getattr(g, "slot_thickness", None) is not None else None,
            "length_mm": getattr(g, "length_mm", None),
            "power_type": g_power_type,
            "is_16pin": any(tok in g_power_type for tok in ("12v-2x6", "12vhpwr", "16-pin")),
            "min_pcie_cables": getattr(g, "min_pcie_cables", None),
            "pcie_lanes": getattr(g, "pcie_lanes", None),
        })
    gpus_rec.sort(key=lambda r: (-r["score"], r["price"], r["id"]))

    sorted_storages = sorted(storages, key=lambda s: (float(s.effective_price), s.storage_id))
    cheapest_nvme_orm = next((s for s in sorted_storages if s.type == "NVMe_M2"), sorted_storages[0])
    cheapest_non_nvme_orm = next((s for s in sorted_storages if s.type != "NVMe_M2"), None)
    cheapest_nvme_rec = {"obj": cheapest_nvme_orm, "id": cheapest_nvme_orm.storage_id, "price": float(cheapest_nvme_orm.effective_price)}
    cheapest_non_nvme_rec = (
        {"obj": cheapest_non_nvme_orm, "id": cheapest_non_nvme_orm.storage_id, "price": float(cheapest_non_nvme_orm.effective_price)}
        if cheapest_non_nvme_orm else None
    )

    complete_rams = [
        r for r in rams
        if r.ram_type is not None
        and r.capacity_gb is not None and int(r.capacity_gb) > 0
        and r.speed_mhz is not None and int(r.speed_mhz) > 0
        and r.channels is not None and int(r.channels) >= 1
        and r.height_mm is not None and int(r.height_mm) > 0
    ]

    candidate_rams = [r for r in complete_rams if int(r.capacity_gb) == ram_pref] if ram_pref else complete_rams
    if not candidate_rams:
        candidate_rams = complete_rams

    ram_candidates_by_type = {}
    for rtype in ("DDR4", "DDR5"):
        type_rams = [r for r in candidate_rams if r.ram_type == rtype]
        dual_rams = [r for r in type_rams if int(r.channels) >= 2]
        lp_dual = min([r for r in dual_rams if int(r.height_mm) <= 35], key=lambda r: float(r.effective_price), default=None)
        cheapest_dual = min(dual_rams, key=lambda r: float(r.effective_price), default=None)
        cheapest_any = min(type_rams, key=lambda r: float(r.effective_price), default=None)
        deduped = []
        seen_rids = set()
        for r in (lp_dual, cheapest_dual, cheapest_any):
            if r is not None and r.ram_id not in seen_rids:
                r_ch = int(r.channels)
                deduped.append({
                    "obj": r,
                    "id": r.ram_id,
                    "ram_type": r.ram_type,
                    "ch": r_ch,
                    "is_dual": 1 if r_ch >= 2 else 0,
                    "height_mm": int(r.height_mm),
                    "price": float(r.effective_price),
                })
                seen_rids.add(r.ram_id)
        ram_candidates_by_type[rtype] = deduped

    psus_rec = sorted(
        [
            {
                "obj": p,
                "id": p.psu_id,
                "price": float(p.effective_price),
                "wattage": p.wattage,
                "form_factor": getattr(p, "form_factor", None),
                "length_mm": getattr(p, "length_mm", None),
                "has_12vhpwr": getattr(p, "has_12vhpwr", None),
                "pcie_8pin_count": getattr(p, "pcie_8pin_count", None),
            }
            for p in psus
        ],
        key=lambda p: (p["price"], p["id"]),
    )

    eval_cases_orm = [c for c in cases if c.form_factor == "ITX"] if ff_pref == "ITX" else cases
    eval_mobos_orm = [m for m in mobos if m.form_factor == "ITX"] if ff_pref == "ITX" else mobos

    cases_rec = [
        {
            "obj": cs,
            "id": cs.case_id,
            "name": cs.name,
            "form_factor": cs.form_factor,
            "ff_rank": FORM_FACTOR_RANK.get(cs.form_factor, 0),
            "psu_ffs": {s.strip() for s in str(getattr(cs, "supported_psu_form_factors", "") or "").split(",") if s.strip()},
            "max_psu_len": getattr(cs, "max_psu_len_mm", None),
            "max_gpu_slots": float(cs.max_gpu_slots) if getattr(cs, "max_gpu_slots", None) is not None else None,
            "max_gpu_len_mm": getattr(cs, "max_gpu_len_mm", None),
            "max_cooler_height_mm": getattr(cs, "max_cooler_height_mm", None),
            "max_radiator_mm": getattr(cs, "max_radiator_mm", None),
            "airflow_coef": float(cs.airflow_coef),
            "price": float(cs.effective_price),
        }
        for cs in eval_cases_orm
    ]

    mobos_rec = [
        {
            "obj": m,
            "id": m.mobo_id,
            "socket": m.socket,
            "form_factor": m.form_factor,
            "ff_rank": FORM_FACTOR_RANK.get(m.form_factor, 99),
            "ram_type": m.ram_type,
            "has_m2": (m.m2_slots_count or 0) > 0,
            "max_tdp": m.max_recommended_cpu_tdp,
            "pcie_gen": getattr(m, "pcie_gen", None),
            "has_usb_c": getattr(m, "has_usb_c_header", None),
            "price": float(m.effective_price),
            "compat_complete": (
                m.socket is not None
                and m.form_factor in FORM_FACTOR_RANK
                and m.ram_type is not None
                and m.m2_slots_count is not None
                and m.max_recommended_cpu_tdp is not None
                and getattr(m, "pcie_gen", None) is not None
                and getattr(m, "has_usb_c_header", None) is not None
            ),
        }
        for m in eval_mobos_orm
    ]

    coolers_rec = sorted(
        [
            {
                "obj": cl,
                "id": cl.cooler_id,
                "sockets": {s.strip() for s in str(getattr(cl, "socket_list", "") or "").split(",") if s.strip()},
                "max_tdp": cl.max_tdp,
                "ram_limit": getattr(cl, "max_ram_clearance_mm", None),
                "type": getattr(cl, "type", None),
                "height_mm": getattr(cl, "height_mm", None),
                "rad_size_mm": getattr(cl, "rad_size_mm", None),
                "price": float(cl.effective_price),
            }
            for cl in coolers
        ],
        key=lambda cl: (cl["price"], cl["id"]),
    )

    # 4. Precompute GPU x Case and Cooler x Case physical clearances once outside main loops
    gpu_case_ok = {}
    for g in gpus_rec:
        gid = g["id"]
        g_slots = g["slot_thickness"]
        for cs in cases_rec:
            csid = cs["id"]
            if g_slots is None or cs["max_gpu_slots"] is None or g_slots > cs["max_gpu_slots"]:
                gpu_case_ok[(gid, csid)] = False
                continue
            clr_g = check_physical_clearances(
                gpu_id=gid, cooler_id="", case_id=csid,
                gpu_length_mm=g["length_mm"],
                case_name=cs["name"],
                case_max_gpu_len_mm=cs["max_gpu_len_mm"],
            )
            gpu_case_ok[(gid, csid)] = (
                not any(m.startswith("GPU Collision") for m in clr_g["conflicts"])
                and not any("GPU Clearance" in m for m in clr_g["unverified"])
            )

    cooler_case_ok = {}
    for cl in coolers_rec:
        clid = cl["id"]
        for cs in cases_rec:
            csid = cs["id"]
            clr_c = check_physical_clearances(
                gpu_id="", cooler_id=clid, case_id=csid,
                cooler_type=cl["type"],
                cooler_height_mm=cl["height_mm"],
                cooler_rad_size_mm=cl["rad_size_mm"],
                case_name=cs["name"],
                case_max_cooler_height_mm=cs["max_cooler_height_mm"],
                case_max_radiator_mm=cs["max_radiator_mm"],
            )
            cooler_case_ok[(clid, csid)] = (
                not any(not m.startswith("GPU Collision") for m in clr_c["conflicts"])
                and not any("GPU Clearance" not in m for m in clr_c["unverified"])
            )

    # Search Space & Pruning Telemetry Counters
    total_pairs = len(cpus_rec) * len(gpus_rec)
    pruned_by_budget = 0
    pruned_by_compatibility = 0
    pruned_by_dominance_bound = 0
    feasible_evaluations = 0

    best_build = None
    best_compat = None
    best_winner_results = None
    best_rank = (-1.0, -1, float('-inf'))

    all_catalog_games = list(GAME_PROFILES.keys())
    objective_games = [request.game_name] if request.game_name else all_catalog_games
    perf_cache = {}
    composite_cache = {}

    def _eval_composite(gpu_score, cpu_score, cpu_tdp, gpu_tdp, cooler_max_tdp, case_airflow_coef, gpu_vram, ram_ch):
        ckey = (gpu_score, cpu_score, cpu_tdp, gpu_tdp, cooler_max_tdp, case_airflow_coef, gpu_vram, ram_ch)
        cached = composite_cache.get(ckey)
        if cached is not None:
            return cached

        game_fps_map = {}
        result_map = {}
        log_fps_sum = 0.0
        for g_name in objective_games:
            res = perf_cache.get((ckey, g_name))
            if res is None:
                res = calculate_heuristic_performance(
                    gpu_score=gpu_score,
                    cpu_score=cpu_score,
                    cpu_tdp=cpu_tdp,
                    gpu_tdp=gpu_tdp,
                    cooler_max_tdp=cooler_max_tdp,
                    case_airflow_coef=case_airflow_coef,
                    game_name=g_name,
                    resolution=active_resolution,
                    gpu_vram_gb=gpu_vram,
                    ambient_temp=active_ambient,
                    ram_channels=ram_ch
                )
                perf_cache[(ckey, g_name)] = res
            fps_val = res["predicted_fps"]
            game_fps_map[g_name] = fps_val
            result_map[g_name] = res
            anchor_fps = GAME_PROFILES[g_name]["gpu_anchor_fps"]
            log_fps_sum += math.log(max(1e-6, fps_val / anchor_fps))

        comp = round(math.exp(log_fps_sum / len(objective_games)) * 100.0, 2)
        out = (comp, game_fps_map, result_map)
        composite_cache[ckey] = out
        return out

    # Precompute socket-viable motherboards (with lossless Pareto dominance pruning) and coolers per CPU
    cpu_mobos_map = {}
    cpu_coolers_map = {}
    for c in cpus_rec:
        csock = c["socket"]
        ctdp = c["tdp"]
        viable_m = [
            m for m in mobos_rec
            if m["socket"] == csock and m["max_tdp"] is not None and ctdp <= m["max_tdp"]
        ]
        # Lossless motherboard dominance per (ram_type, has_m2):
        # keep incomplete entries conservatively, keep cheapest per ff_rank,
        # and prune strictly larger ff_rank if no cheaper than a smaller ff_rank.
        kept_incomplete = [m for m in viable_m if not m["compat_complete"]]
        by_group = {}
        for m in viable_m:
            if not m["compat_complete"]:
                continue
            grp_key = (m["ram_type"], m["has_m2"], m["ff_rank"])
            prev = by_group.get(grp_key)
            tie_key = (m["price"], 0 if m["has_usb_c"] else 1, -(m["pcie_gen"] or 0), m["id"])
            if prev is None or tie_key < prev[0]:
                by_group[grp_key] = (tie_key, m)

        dominant_complete = []
        bucket_pairs = {(rt, hm) for (rt, hm, _) in by_group.keys()}
        for rt, hm in bucket_pairs:
            best_smaller_price = float('inf')
            for ff_r in sorted(ff_r2 for (rt2, hm2, ff_r2) in by_group.keys() if rt2 == rt and hm2 == hm):
                cand = by_group[(rt, hm, ff_r)][1]
                if cand["price"] < best_smaller_price:
                    dominant_complete.append(cand)
                    best_smaller_price = cand["price"]

        dom_list = sorted(kept_incomplete + dominant_complete, key=lambda m: (m["price"], m["ff_rank"], m["id"]))
        cpu_mobos_map[c["id"]] = dom_list
        cpu_coolers_map[c["id"]] = [
            cl for cl in coolers_rec
            if csock in cl["sockets"] and cl["max_tdp"] is not None and ctdp <= cl["max_tdp"]
        ]

    # 5. Branch-and-Bound Execution Loop
    for cpu in cpus_rec:
        canonical_cpu_score = cpu["score"]
        viable_mobos = cpu_mobos_map[cpu["id"]]
        viable_coolers = cpu_coolers_map[cpu["id"]]
        if not viable_mobos or not viable_coolers:
            pruned_by_compatibility += len(gpus_rec)
            continue

        min_cooler_price = viable_coolers[0]["price"]
        max_cooler_tdp = max(cl["max_tdp"] for cl in viable_coolers)

        for gpu in gpus_rec:
            core_cost = cpu["price"] + gpu["price"]
            canonical_gpu_score = gpu["score"]
            gpu_vram = gpu["vram"]

            if gpu["slot_thickness"] is None or not gpu["power_type"] or gpu["min_pcie_cables"] is None:
                pruned_by_compatibility += 1
                continue

            total_system_tdp = cpu["tdp"] + gpu["tdp"] + 50
            req_psu_wattage = total_system_tdp / 0.80

            is_16pin_gpu = gpu["is_16pin"]
            gpu_cables_req = gpu["min_pcie_cables"]
            power_psus = []
            for p in psus_rec:
                if p["wattage"] < req_psu_wattage:
                    continue
                if p["has_12vhpwr"] is None or p["pcie_8pin_count"] is None:
                    continue
                if is_16pin_gpu:
                    if not (bool(p["has_12vhpwr"]) or int(p["pcie_8pin_count"]) >= int(gpu_cables_req)):
                        continue
                else:
                    if int(p["pcie_8pin_count"]) < int(gpu_cables_req):
                        continue
                power_psus.append(p)

            if not power_psus:
                pruned_by_compatibility += 1
                continue

            if is_16pin_gpu and len(power_psus) > 1:
                power_psus.sort(key=lambda p: (p["price"], 0 if p["has_12vhpwr"] else 1, p["id"]))

            # Precompute cheapest compatible PSU per GPU-compatible case once per (cpu, gpu) pair
            gpu_case_psu_list = []
            gid = gpu["id"]
            for cs in cases_rec:
                if not gpu_case_ok[(gid, cs["id"])] or cs["max_psu_len"] is None or not cs["psu_ffs"]:
                    continue
                valid_psu = next(
                    (p for p in power_psus
                     if p["form_factor"] in cs["psu_ffs"]
                     and p["length_mm"] is not None
                     and p["length_mm"] <= cs["max_psu_len"]),
                    None
                )
                if valid_psu is not None:
                    gpu_case_psu_list.append((cs, valid_psu, cs["price"] + valid_psu["price"]))

            if not gpu_case_psu_list:
                pruned_by_compatibility += 1
                continue

            gpu_case_psu_list.sort(key=lambda row: (row[2], -row[0]["airflow_coef"], row[0]["id"]))
            max_pair_airflow = max(row[0]["airflow_coef"] for row in gpu_case_psu_list)
            min_case_psu_cost = gpu_case_psu_list[0][2]

            # Exact pair-level budget + upper-bound dominance pruning
            mobo_ram_floors = []
            max_pair_dual = 0
            for mobo in viable_mobos:
                st_rec = cheapest_nvme_rec if mobo["has_m2"] else cheapest_non_nvme_rec
                r_cands = ram_candidates_by_type.get(mobo["ram_type"]) or []
                if st_rec and r_cands:
                    min_r_price = min(r["price"] for r in r_cands)
                    mobo_ram_floors.append(mobo["price"] + min_r_price + st_rec["price"])
                    if any(r["is_dual"] for r in r_cands):
                        max_pair_dual = 1

            if not mobo_ram_floors:
                pruned_by_compatibility += 1
                continue

            min_pair_cost = core_cost + min(mobo_ram_floors) + min_cooler_price + min_case_psu_cost
            if min_pair_cost > active_budget:
                pruned_by_budget += 1
                continue

            pair_max_ch = 2 if max_pair_dual else 1
            pair_upper_score, _, _ = _eval_composite(
                canonical_gpu_score, canonical_cpu_score,
                cpu["tdp"], gpu["tdp"], max_cooler_tdp, max_pair_airflow,
                gpu_vram, pair_max_ch
            )
            if (pair_upper_score, max_pair_dual) < (best_rank[0], best_rank[1]) or (
                (pair_upper_score, max_pair_dual) == (best_rank[0], best_rank[1]) and -min_pair_cost <= best_rank[2]
            ):
                pruned_by_dominance_bound += 1
                continue

            for mobo in viable_mobos:
                mobo_ff_rank = mobo["ff_rank"]
                storage_cand = cheapest_nvme_rec if mobo["has_m2"] else cheapest_non_nvme_rec
                if not storage_cand:
                    pruned_by_compatibility += 1
                    continue

                mobo_cases = [row for row in gpu_case_psu_list if mobo_ff_rank <= row[0]["ff_rank"]]
                if not mobo_cases:
                    pruned_by_compatibility += 1
                    continue

                min_mobo_case_psu_cost = mobo_cases[0][2]
                max_mobo_airflow = max(row[0]["airflow_coef"] for row in mobo_cases)

                ram_cands = ram_candidates_by_type.get(mobo["ram_type"]) or []
                for ram in ram_cands:
                    ram_ch = ram["ch"]
                    ram_dual = ram["is_dual"]
                    ram_height = ram["height_mm"]
                    subtotal = core_cost + mobo["price"] + ram["price"] + storage_cand["price"]
                    ram_min_total = subtotal + min_cooler_price + min_mobo_case_psu_cost

                    if ram_min_total > active_budget:
                        pruned_by_budget += 1
                        continue

                    ram_upper_score, _, _ = _eval_composite(
                        canonical_gpu_score, canonical_cpu_score,
                        cpu["tdp"], gpu["tdp"], max_cooler_tdp, max_mobo_airflow,
                        gpu_vram, ram_ch
                    )
                    if (ram_upper_score, ram_dual) < (best_rank[0], best_rank[1]) or (
                        (ram_upper_score, ram_dual) == (best_rank[0], best_rank[1]) and -ram_min_total <= best_rank[2]
                    ):
                        pruned_by_dominance_bound += 1
                        continue

                    for cooler in viable_coolers:
                        cl_ram_limit = cooler["ram_limit"]
                        if ram_height is None or cl_ram_limit is None or ram_height > cl_ram_limit:
                            pruned_by_compatibility += 1
                            continue

                        cl_subtotal = subtotal + cooler["price"]
                        if (cl_subtotal + min_mobo_case_psu_cost) > active_budget:
                            pruned_by_budget += 1
                            break

                        cl_id = cooler["id"]
                        cl_tdp = cooler["max_tdp"]
                        cl_upper_score, _, _ = _eval_composite(
                            canonical_gpu_score, canonical_cpu_score,
                            cpu["tdp"], gpu["tdp"], cl_tdp, max_mobo_airflow,
                            gpu_vram, ram_ch
                        )
                        if (cl_upper_score, ram_dual) < (best_rank[0], best_rank[1]) or (
                            (cl_upper_score, ram_dual) == (best_rank[0], best_rank[1]) and -(cl_subtotal + min_mobo_case_psu_cost) <= best_rank[2]
                        ):
                            pruned_by_dominance_bound += 1
                            continue

                        for cs, valid_psu, cs_psu_cost in mobo_cases:
                            total_cost = cl_subtotal + cs_psu_cost
                            if total_cost > active_budget:
                                pruned_by_budget += 1
                                break

                            if not cooler_case_ok[(cl_id, cs["id"])]:
                                pruned_by_compatibility += 1
                                continue

                            feasible_evaluations += 1
                            composite_score, game_fps_map, result_map = _eval_composite(
                                canonical_gpu_score, canonical_cpu_score,
                                cpu["tdp"], gpu["tdp"], cl_tdp, cs["airflow_coef"],
                                gpu_vram, ram_ch
                            )
                            candidate_rank = (composite_score, ram_dual, -total_cost)
                            if candidate_rank <= best_rank:
                                pruned_by_dominance_bound += 1
                                continue

                            # Authoritative shared 16-check compatibility gate for strictly improving candidates
                            compat = evaluate_build_compatibility(
                                cpu=cpu["obj"], mobo=mobo["obj"], gpu=gpu["obj"], cooler=cooler["obj"], case=cs["obj"],
                                ram=ram["obj"], psu=valid_psu["obj"], storage=storage_cand["obj"],
                                canonical_gpu=gpu["canon"],
                                canonical_cpu=cpu["canon"],
                            )
                            if not compat["is_compatible"]:
                                pruned_by_compatibility += 1
                                continue

                            best_rank = candidate_rank
                            best_compat = compat
                            best_winner_results = result_map
                            best_build = {
                                "cpu": cpu["obj"],
                                "mobo": mobo["obj"],
                                "gpu": gpu["obj"],
                                "cooler": cooler["obj"],
                                "case": cs["obj"],
                                "ram": ram["obj"],
                                "psu": valid_psu["obj"],
                                "storage": storage_cand["obj"],
                                "total_price_rm": round(total_cost, 2),
                                "composite_gaming_score": composite_score,
                                "catalog_game_fps": dict(game_fps_map),
                            }
                            if (composite_score, ram_dual) == (cl_upper_score, ram_dual):
                                break

    if not best_build:
        raise HTTPException(
            status_code=404,
            detail=f"No physically compatible configuration could be synthesized under RM {active_budget:,.2f}. Try increasing the budget ceiling."
        )

    # Populate full catalog game FPS & thermal telemetry for winner
    w_cpu = best_build["cpu"]
    w_gpu = best_build["gpu"]
    w_cooler = best_build["cooler"]
    w_case = best_build["case"]
    w_ram = best_build["ram"]
    w_cpu_score = cpu_info_map[w_cpu.cpu_id]["score"]
    w_gpu_score = gpu_info_map[w_gpu.gpu_id]["score"]
    w_gpu_vram = gpu_vram_map[w_gpu.gpu_id]
    w_ram_ch = getattr(w_ram, "channels", 2) or 2

    if any(g not in best_build["catalog_game_fps"] for g in all_catalog_games):
        for g_name in all_catalog_games:
            if g_name not in best_build["catalog_game_fps"]:
                res = calculate_heuristic_performance(
                    gpu_score=w_gpu_score,
                    cpu_score=w_cpu_score,
                    cpu_tdp=w_cpu.tdp_watts,
                    gpu_tdp=w_gpu.tdp_watts,
                    cooler_max_tdp=w_cooler.max_tdp,
                    case_airflow_coef=float(w_case.airflow_coef),
                    game_name=g_name,
                    resolution=active_resolution,
                    gpu_vram_gb=w_gpu_vram,
                    ambient_temp=active_ambient,
                    ram_channels=w_ram_ch
                )
                best_build["catalog_game_fps"][g_name] = res["predicted_fps"]
                best_winner_results[g_name] = res

    primary_game = request.game_name or "Cyberpunk 2077"
    primary_res = best_winner_results.get(primary_game) or next(iter(best_winner_results.values()))

    best_build["target_game"] = request.game_name
    best_build["resolution"] = active_resolution
    best_build["predicted_fps"] = best_build["catalog_game_fps"].get(primary_game, primary_res["predicted_fps"])
    best_build["cpu_temp_c"] = primary_res["cpu_temp_c"]
    best_build["gpu_temp_c"] = primary_res["gpu_temp_c"]
    best_build["case_internal_temp_c"] = primary_res["case_internal_temp_c"]
    best_build["thermal_status"] = primary_res["thermal_status"]

    # Honest per-component pricing metadata
    component_pricing = {}
    live_count = 0
    for cat_key, comp_obj, id_attr in [
        ("cpu", best_build["cpu"], "cpu_id"),
        ("mobo", best_build["mobo"], "mobo_id"),
        ("gpu", best_build["gpu"], "gpu_id"),
        ("cooler", best_build["cooler"], "cooler_id"),
        ("case", best_build["case"], "case_id"),
        ("ram", best_build["ram"], "ram_id"),
        ("psu", best_build["psu"], "psu_id"),
        ("storage", best_build["storage"], "storage_id"),
    ]:
        p_det = price_details_lookup[(cat_key, getattr(comp_obj, id_attr))]
        if p_det["is_live_price"]:
            live_count += 1
        component_pricing[cat_key] = {
            "price_rm": round(p_det["price"], 2),
            "msrp_rm": round(p_det["msrp"], 2),
            "data_status": p_det["data_status"],
            "is_live_price": p_det["is_live_price"],
            "best_platform": p_det["best_platform"],
            "price_source": p_det["platform"],
        }

    if live_count == 8:
        opt_pricing_source = "Live Scraped Market (Shopee/Lazada)"
    elif live_count > 0:
        opt_pricing_source = f"Mixed ({live_count}/8 Live Market, {8 - live_count}/8 Catalog MSRP)"
    else:
        opt_pricing_source = "Catalog MSRP Fallback"

    best_build["pricing_source"] = opt_pricing_source
    best_build["live_priced_components"] = live_count
    best_build["component_pricing"] = component_pricing
    best_build["compatibility"] = {
        "overall_status": best_compat["overall_status"],
        "is_compatible": best_compat["is_compatible"],
        "counts": best_compat["counts"],
        "warnings": best_compat["warnings"],
    }

    ram_channel_desc = "dual-channel" if w_ram_ch >= 2 else "single-channel (budget-constrained fallback)"

    # Telemetry and Selection Rationales
    best_build["optimizer_telemetry"] = {
        "execution_mode": "Hybrid (Prompt + Budget)" if (request.prompt and request.budget) else ("Prompt Intent" if request.prompt else "Budget-Driven Knapsack"),
        "active_budget_ceiling_rm": active_budget,
        "target_game": request.game_name,
        "resolution": active_resolution,
        "natural_language_audit": {
            "raw_prompt": request.prompt,
            "parsing_notes": parsed["parsing_notes"]
        },
        "search_space_pruning": {
            "primary_combinations": total_pairs,
            "pruned_by_budget_limit": pruned_by_budget,
            "pruned_by_physical_clearance": pruned_by_compatibility,
            "pruned_by_dominance_bound": pruned_by_dominance_bound,
            "feasible_candidates_simulated": feasible_evaluations
        },
        "optimization_criteria": {
            "objective": f"Maximize {request.game_name} FPS Index" if request.game_name else "Maximize Multi-Game Geometric Mean Performance Index",
            "evaluated_catalog_titles": objective_games,
            "composite_score_achieved": best_build["composite_gaming_score"]
        },
        "selection_rationales": {
            "processor": f"Selected {w_cpu.name} ({w_cpu.socket}) to satisfy compute requirements.",
            "motherboard": f"Paired {best_build['mobo'].name} ({best_build['mobo'].form_factor}) to match {w_cpu.socket} socket with VRM rated for {best_build['mobo'].max_recommended_cpu_tdp}W (CPU requires {w_cpu.tdp_watts}W).",
            "memory": f"Allocated {w_ram.name} ({w_ram.capacity_gb}GB {w_ram.ram_type}) with {ram_channel_desc} memory configuration.",
            "power_supply": f"Provisioned {best_build['psu'].wattage}W {best_build['psu'].form_factor} unit ({best_build['psu'].efficiency}) delivering stable power and connector headroom over estimated {w_cpu.tdp_watts + w_gpu.tdp_watts + 50}W peak demand.",
            "chassis_cooler_fit": f"Verified {w_cooler.name} ({w_cooler.max_tdp}W TDP rating) and GPU fitment inside {w_case.name} ({w_case.form_factor})."
        }
    }

    return best_build

@app.post("/compare-groundup")
def compare_groundup_vs_realworld(request: SimulationRequest, db: Session = Depends(get_db)):
    if request.game_name not in GAME_PROFILES:
        supported = sorted(list(GAME_PROFILES.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported game '{request.game_name}'. Supported games: {supported}"
        )
    if request.resolution not in SUPPORTED_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported resolution '{request.resolution}'. Supported resolutions: {list(SUPPORTED_RESOLUTIONS)}"
        )

    cpu = db.query(models.CPU).filter(models.CPU.cpu_id == request.cpu_id).first()
    gpu = db.query(models.GPU).filter(models.GPU.gpu_id == request.gpu_id).first()
    cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == request.cooler_id).first()
    case = db.query(models.Case).filter(models.Case.case_id == request.case_id).first()
    ram = db.query(models.RAM).filter(models.RAM.ram_id == request.ram_id).first()

    if not all([cpu, gpu, cooler, case, ram]):
        missing = []
        if not cpu: missing.append(f"CPU: '{request.cpu_id}'")
        if not gpu: missing.append(f"GPU: '{request.gpu_id}'")
        if not cooler: missing.append(f"Cooler: '{request.cooler_id}'")
        if not case: missing.append(f"Case: '{request.case_id}'")
        if not ram: missing.append(f"RAM: '{request.ram_id}'")
        raise HTTPException(
            status_code=404,
            detail=f"Ground-up comparison failed. Missing components: {', '.join(missing)}"
        )

    gpu_model_id = getattr(gpu, "model_id", None)
    cpu_model_id = getattr(cpu, "model_id", None)

    gpu_arch = {
        "amd_rx_6600":      {"cores": 1792,  "clock": 2491, "bus": 128, "speed": 14.0},
        "nv_rtx_3060_12gb": {"cores": 3584,  "clock": 1777, "bus": 192, "speed": 15.0},
        "nv_rtx_4060":      {"cores": 3072,  "clock": 2460, "bus": 128, "speed": 17.0},
        "nv_rtx_4070":      {"cores": 5888,  "clock": 2475, "bus": 192, "speed": 21.0},
        "nv_rtx_4090":      {"cores": 16384, "clock": 2520, "bus": 384, "speed": 21.0},
        # Legacy ID aliases preserved for backward compatibility
        "rx_6600":  {"cores": 1792,  "clock": 2491, "bus": 128, "speed": 14.0},
        "rtx_3060": {"cores": 3584,  "clock": 1777, "bus": 192, "speed": 15.0},
        "rtx_4060": {"cores": 3072,  "clock": 2460, "bus": 128, "speed": 17.0},
        "rtx_4070": {"cores": 5888,  "clock": 2475, "bus": 192, "speed": 21.0},
        "rtx_4090": {"cores": 16384, "clock": 2520, "bus": 384, "speed": 21.0},
    }

    cpu_arch = {
        "intel_i3_12100f":    {"ipc": 1.35, "boost": 4.3, "l3_mb": 12},
        "intel_i5_12400f":    {"ipc": 1.35, "boost": 4.4, "l3_mb": 18},
        "intel_i9_14900k":    {"ipc": 1.48, "boost": 6.0, "l3_mb": 36},
        "amd_ryzen_5_5600":   {"ipc": 1.30, "boost": 4.4, "l3_mb": 32},
        "amd_ryzen_7_7800x3d": {"ipc": 1.50, "boost": 5.0, "l3_mb": 96},
        # Legacy ID aliases preserved for backward compatibility
        "i3_12100F":     {"ipc": 1.35, "boost": 4.3, "l3_mb": 12},
        "i5_12400F":     {"ipc": 1.35, "boost": 4.4, "l3_mb": 18},
        "i9_14900K":     {"ipc": 1.48, "boost": 6.0, "l3_mb": 36},
        "ryzen_5600":    {"ipc": 1.30, "boost": 4.4, "l3_mb": 32},
        "ryzen_7800X3D": {"ipc": 1.50, "boost": 5.0, "l3_mb": 96},
    }

    g_arch = gpu_arch.get(gpu_model_id) or gpu_arch.get(gpu.gpu_id)
    c_arch = cpu_arch.get(cpu_model_id) or cpu_arch.get(cpu.cpu_id)

    if g_arch is None or c_arch is None:
        unmodeled = []
        if g_arch is None:
            unmodeled.append(f"GPU '{gpu.gpu_id}' (model_id='{gpu_model_id}')")
        if c_arch is None:
            unmodeled.append(f"CPU '{cpu.cpu_id}' (model_id='{cpu_model_id}')")
        return {
            "gpu_model_id": gpu_model_id,
            "cpu_model_id": cpu_model_id,
            "architecture_profile_matched": False,
            "ground_up_calculated_fps": None,
            "real_world_benchmark_fps": None,
            "prediction_error_percentage": None,
            "has_empirical_reference": False,
            "theoretical_tflops": None,
            "memory_bandwidth_gbs": None,
            "predicted_temp_c": None,
            "disclosure": (
                f"First-principles silicon architecture parameters (cores/clock/bus/IPC/cache) are not modeled for "
                f"{', '.join(unmodeled)}; no fallback placeholder profile substituted."
            ),
        }

    groundup = calculate_ground_up_performance(
        gpu_cores=g_arch["cores"], gpu_clock_mhz=g_arch["clock"],
        gpu_bus_bit=g_arch["bus"], gpu_speed_gbps=g_arch["speed"],
        cpu_ipc=c_arch["ipc"], cpu_boost_ghz=c_arch["boost"], cpu_l3_cache_mb=c_arch["l3_mb"], cpu_tdp=cpu.tdp_watts,
        cooler_max_tdp=cooler.max_tdp, case_airflow_coef=float(case.airflow_coef),
        ram_speed_mts=ram.speed_mhz, game_name=request.game_name, resolution=request.resolution
    )

    realworld_benchmarks = {
        ("intel_i5_12400f", "nv_rtx_4060", "Cyberpunk 2077", "1080p"): 72.0,
        ("intel_i3_12100f", "nv_rtx_3060_12gb", "Cyberpunk 2077", "1080p"): 60.0,
        ("intel_i5_12400f", "nv_rtx_4070", "Cyberpunk 2077", "1080p"): 96.0,
        ("intel_i9_14900k", "nv_rtx_4070", "Cyberpunk 2077", "1080p"): 121.0,
        ("amd_ryzen_7_7800x3d", "nv_rtx_4090", "Cyberpunk 2077", "4K"): 88.0,
        ("amd_ryzen_5_5600", "amd_rx_6600", "Cyberpunk 2077", "1080p"): 52.0,
        # Legacy ID aliases
        ("i5_12400F", "rtx_4060", "Cyberpunk 2077", "1080p"): 72.0,
        ("i3_12100F", "rtx_3060", "Cyberpunk 2077", "1080p"): 60.0,
        ("i5_12400F", "rtx_4070", "Cyberpunk 2077", "1080p"): 96.0,
        ("i9_14900K", "rtx_4070", "Cyberpunk 2077", "1080p"): 121.0,
        ("ryzen_7800X3D", "rtx_4090", "Cyberpunk 2077", "4K"): 88.0,
        ("ryzen_5600", "rx_6600", "Cyberpunk 2077", "1080p"): 52.0,
    }

    actual_benchmark_fps = (
        realworld_benchmarks.get((cpu_model_id, gpu_model_id, request.game_name, request.resolution))
        or realworld_benchmarks.get((cpu.cpu_id, gpu.gpu_id, request.game_name, request.resolution))
    )

    if actual_benchmark_fps is not None:
        error_percentage = round((abs(actual_benchmark_fps - groundup["ground_up_fps"]) / actual_benchmark_fps) * 100.0, 2)
        real_world_fps = round(actual_benchmark_fps)
        has_reference = True
        disclosure = "Matched canonical first-principles silicon profile and recorded reference benchmark."
    else:
        error_percentage = None
        real_world_fps = None
        has_reference = False
        disclosure = "Canonical silicon profile matched; no recorded real-world benchmark reference exists for this exact configuration and workload."

    return {
        "gpu_model_id": gpu_model_id,
        "cpu_model_id": cpu_model_id,
        "architecture_profile_matched": True,
        "ground_up_calculated_fps": groundup["ground_up_fps"],
        "real_world_benchmark_fps": real_world_fps,
        "prediction_error_percentage": error_percentage,
        "has_empirical_reference": has_reference,
        "theoretical_tflops": groundup["theoretical_tflops"],
        "memory_bandwidth_gbs": groundup["memory_bandwidth_gbs"],
        "predicted_temp_c": groundup["predicted_temp_c"],
        "disclosure": disclosure,
    }

# --- BILL OF MATERIALS (BOM) EXPORT ---
@app.post("/export/bom")
def export_bill_of_materials(request: SimulationRequest, db: Session = Depends(get_db)):
    if request.game_name not in GAME_PROFILES:
        supported = sorted(list(GAME_PROFILES.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported game '{request.game_name}'. Supported games: {supported}"
        )
    if request.resolution not in SUPPORTED_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported resolution '{request.resolution}'. Supported resolutions: {list(SUPPORTED_RESOLUTIONS)}"
        )

    # 1. Query all 8 components
    cpu = db.query(models.CPU).filter(models.CPU.cpu_id == request.cpu_id).first()
    mobo = db.query(models.Motherboard).filter(models.Motherboard.mobo_id == request.mobo_id).first()
    gpu = db.query(models.GPU).filter(models.GPU.gpu_id == request.gpu_id).first()
    cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == request.cooler_id).first()
    case = db.query(models.Case).filter(models.Case.case_id == request.case_id).first()
    ram = db.query(models.RAM).filter(models.RAM.ram_id == request.ram_id).first()
    psu = db.query(models.PSU).filter(models.PSU.psu_id == request.psu_id).first()
    storage = db.query(models.Storage).filter(models.Storage.storage_id == request.storage_id).first()

    # 2. Pinpoint any missing component clearly
    if not all([cpu, mobo, gpu, cooler, case, ram, psu, storage]):
        missing = []
        if not cpu: missing.append(f"CPU: '{request.cpu_id}'")
        if not mobo: missing.append(f"Mobo: '{request.mobo_id}'")
        if not gpu: missing.append(f"GPU: '{request.gpu_id}'")
        if not cooler: missing.append(f"Cooler: '{request.cooler_id}'")
        if not case: missing.append(f"Case: '{request.case_id}'")
        if not ram: missing.append(f"RAM: '{request.ram_id}'")
        if not psu: missing.append(f"PSU: '{request.psu_id}'")
        if not storage: missing.append(f"Storage: '{request.storage_id}'")
        raise HTTPException(
            status_code=400,
            detail=f"BOM generation failed. Missing component in DB: {', '.join(missing)}. Please run POST /seed."
        )

    gpu_info = resolve_canonical_gpu_info(gpu, db=db)
    cpu_info = resolve_canonical_cpu_info(cpu, db=db)

    # 3. Shared Compatibility & Clearance Verification
    compat = evaluate_build_compatibility(
        cpu=cpu, mobo=mobo, gpu=gpu, cooler=cooler, case=case, ram=ram, psu=psu, storage=storage,
        canonical_gpu=gpu_info["canonical_model"], canonical_cpu=cpu_info["canonical_model"],
    )
    warnings = list(compat["warnings"])
    if gpu_info["warning"]:
        warnings.append(gpu_info["warning"])
    if cpu_info["warning"]:
        warnings.append(cpu_info["warning"])

    # 4. Calculate physics and telemetry
    gpu_vram = resolve_gpu_vram_gb(gpu, gpu_info["canonical_model"])
    if gpu_vram is None:
        warnings.append(f"Unverified GPU VRAM: VRAM capacity unavailable for {gpu.name}; VRAM deficit penalties skipped.")
    ambient_c = float(getattr(request, 'ambient_temp', 30.0) or 30.0)
    ram_ch = getattr(ram, 'channels', 2) or 2

    engine_result = calculate_heuristic_performance(
        gpu_score=gpu_info["score"],
        cpu_score=cpu_info["score"],
        cpu_tdp=cpu.tdp_watts,
        gpu_tdp=gpu.tdp_watts,
        cooler_max_tdp=cooler.max_tdp,
        case_airflow_coef=float(case.airflow_coef),
        game_name=request.game_name,
        resolution=request.resolution,
        gpu_vram_gb=gpu_vram,
        ram_channels=ram_ch,
        ambient_temp=ambient_c
    )

    if engine_result.get("bottleneck_detected"):
        warnings.append(f"CPU Bottleneck: {cpu.name} limits {gpu.name} throughput by ~{engine_result['bottleneck_severity_pct']}%.")
    if "THROTTLING" in engine_result.get("thermal_status", ""):
        warnings.append(f"Thermal Alarm: {engine_result['thermal_status']} detected inside {case.name} under {ambient_c}°C ambient.")
    if "VRAM Deficit" in engine_result.get("vram_status", ""):
        warnings.append(f"VRAM Bottleneck: {gpu.name} ({gpu_vram}GB) exceeds memory ceiling for {request.game_name} at {request.resolution}.")

    # 5. Resolve honest effective market prices and build itemized list
    price_map = get_effective_price_map(db)
    raw_components = [
        ("Processor", cpu.cpu_id, cpu.name, cpu.price, cpu),
        ("Motherboard", mobo.mobo_id, mobo.name, mobo.price, mobo),
        ("Graphics Card", gpu.gpu_id, gpu.name, gpu.price, gpu),
        ("CPU Cooler", cooler.cooler_id, cooler.name, cooler.price, cooler),
        ("Chassis", case.case_id, case.name, case.price, case),
        ("Memory (RAM)", ram.ram_id, ram.name, ram.price, ram),
        ("Power Supply", psu.psu_id, psu.name, psu.price, psu),
        ("Storage", storage.storage_id, storage.name, storage.price, storage),
    ]

    components_list = []
    purchasable_total_rm = 0.0
    reference_only_value_rm = 0.0
    purchasable_count = 0
    live_count = 0
    has_reference_only = False

    for category, model_id, name, catalog_price, comp_obj in raw_components:
        is_ref = bool(getattr(comp_obj, 'is_reference_only', False))
        msrp_val = round(float(catalog_price), 2)

        if is_ref:
            has_reference_only = True
            reference_only_value_rm += float(catalog_price)
            components_list.append({
                "category": category,
                "name": name,
                "price_rm": msrp_val,
                "msrp_rm": msrp_val,
                "data_status": "REFERENCE_ONLY",
                "is_available": False,
                "best_platform": None,
                "price_source": "Reference Identity (Non-Purchasable)",
                "shopee_link": None,
                "lazada_link": None,
                "is_purchasable": False,
                "is_reference_only": True,
                "note": "Canonical benchmark reference identity only; excluded from purchasable total."
            })
        else:
            purchasable_count += 1
            p_details = resolve_price_details(model_id, catalog_price, price_map)
            if p_details["is_live_price"]:
                live_count += 1
            purchasable_total_rm += p_details["price"]
            encoded = urllib.parse.quote(name)

            components_list.append({
                "category": category,
                "name": name,
                "price_rm": round(float(p_details["price"]), 2),
                "msrp_rm": msrp_val,
                "data_status": p_details["data_status"],
                "is_available": p_details["is_available"],
                "best_platform": p_details["best_platform"],
                "price_source": p_details["platform"],
                "shopee_link": f"https://shopee.com.my/search?keyword={encoded}",
                "lazada_link": f"https://www.lazada.com.my/catalog/?q={encoded}",
                "is_purchasable": True,
                "is_reference_only": False,
            })

    msrp_fallback_count = purchasable_count - live_count
    if purchasable_count == 0:
        bom_pricing_source = "No Purchasable Components"
    elif live_count == purchasable_count:
        bom_pricing_source = "Live Scraped Market (Shopee/Lazada)"
    elif live_count > 0:
        bom_pricing_source = f"Mixed ({live_count}/{purchasable_count} Live Market, {msrp_fallback_count}/{purchasable_count} Catalog MSRP)"
    else:
        bom_pricing_source = "Catalog MSRP Fallback"

    # 6. Assemble receipt payload
    return JSONResponse(content={
        "report_title": "EcoBuild System Configuration Bill of Materials",
        "workload_target": f"{request.game_name} ({request.resolution})",
        "has_reference_only_components": has_reference_only,
        "system_telemetry": {
            "predicted_fps": engine_result.get("predicted_fps", 0),
            "fps_1pct_low": engine_result.get("fps_1pct_low", 0),
            "frametime_stability_pct": engine_result.get("frametime_stability_pct", 100),
            "operating_temp_c": engine_result.get("cpu_temp_c", 45.0),
            "cpu_temp_c": engine_result.get("cpu_temp_c", 45.0),
            "gpu_temp_c": engine_result.get("gpu_temp_c", 50.0),
            "thermal_status": engine_result.get("thermal_status", "Stable"),
            "vram_status": engine_result.get("vram_status", "Optimal Capacity"),
            "bottleneck_status": "CPU Bottleneck" if engine_result.get("bottleneck_detected") else "Balanced Synergy",
            "bottleneck_loss_pct": engine_result.get("bottleneck_severity_pct", 0.0)
        },
        "compatibility": {
            "overall_status": compat["overall_status"],
            "is_compatible": compat["is_compatible"],
            "counts": compat["counts"],
            "checks": compat["checks"],
        },
        "warnings": warnings,
        "financials": {
            "total_cost_rm": round(float(purchasable_total_rm), 2),
            "purchasable_total_rm": round(float(purchasable_total_rm), 2),
            "reference_only_value_rm": round(float(reference_only_value_rm), 2),
            "overall_displayed_value_rm": round(float(purchasable_total_rm + reference_only_value_rm), 2),
            "live_priced_components": live_count,
            "msrp_fallback_components": msrp_fallback_count,
            "pricing_source": bom_pricing_source,
            "currency": "MYR"
        },
        "components": components_list
    })

@app.post("/analytics/visit")
async def record_silent_visit(request: Request, db: Session = Depends(get_db)):
    """Silently tracks incoming visits for developer telemetry."""
    try:
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
        path = request.headers.get("referer", "/")
        new_visit = models.VisitorStat(page_visited=path[:50], ip_hash=ip_hash)
        db.add(new_visit)
        db.commit()
    except Exception as e:
        print(f"[Analytics Note] {e}")
    return {"status": "ok"}

@app.get("/admin/dashboard")
def get_developer_dashboard(secret_key: str, db: Session = Depends(get_db)):
    """
    Private Developer-Only Insights Dashboard.
    Access via: http://localhost:8000/admin/dashboard?secret_key=ecobuild-dev-2026
    """
    if secret_key != DEV_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized developer access.")

    total_pageviews = db.query(models.VisitorStat).count()
    unique_visitors = db.query(func.count(func.distinct(models.VisitorStat.ip_hash))).scalar() or 0
    
    reports = db.query(models.FeedbackReport).order_by(models.FeedbackReport.created_at.desc()).limit(25).all()
    feedback_list = []
    for r in reports:
        feedback_list.append({
            "id": r.id,
            "category": r.category,
            "contact": r.user_contact or "Anonymous",
            "description": r.description,
            "build": r.build_snapshot,
            "has_screenshot": bool(r.image_base64),
            "image_data": r.image_base64,
            "submitted_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return {
        "developer_telemetry": {
            "total_pageviews": total_pageviews,
            "unique_visitors": unique_visitors,
            "total_feedback_count": len(feedback_list)
        },
        "feedback_reports": feedback_list
    }

@app.post("/feedback")
async def submit_user_feedback(
    category: str = Form("Bug"),
    description: str = Form(...),
    contact: str = Form(""),
    build_snapshot: str = Form("{}"),
    screenshot: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """
    Receives feedback, auto-attached build snapshot, and optional screenshot.
    """
    image_b64 = None
    if screenshot:
        content = await screenshot.read()
        # Cap image upload size at 4MB to protect DB storage
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image exceeds 4MB limit.")
        mime = screenshot.content_type or "image/png"
        image_b64 = f"data:{mime};base64,{base64.b64encode(content).decode('utf-8')}"

    report = models.FeedbackReport(
        category=category,
        user_contact=contact,
        description=description,
        build_snapshot=build_snapshot,
        image_base64=image_b64
    )
    db.add(report)
    db.commit()

    return {"status": "success", "message": "Report logged successfully for the developer."}

def resolve_price(model_id: str, fallback_price: float, price_map: dict) -> float:
    """Uses verified LIVE scraped price when valid; otherwise falls back cleanly to MSRP."""
    return resolve_price_details(model_id, fallback_price, price_map)["price"]

def enrich_catalog_items(items, id_attr, db: Session, canonical_model_map: Optional[dict] = None):
    """
    Safely enriches catalog items with MSRP, live market scraped pricing,
    and (when canonical_model_map is supplied) canonical benchmark metadata.
    """
    price_map = get_effective_price_map(db)
    result = []
    for item in items:
        item_id = getattr(item, id_attr)
        details = resolve_price_details(item_id, item.price, price_map)
        item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns}
        item_dict["price"] = float(item.price)
        item_dict["msrp"] = float(item.price)
        item_dict["market_price"] = details["price"]
        item_dict["is_available"] = details["is_available"]
        item_dict["is_live_price"] = details["is_live_price"]
        item_dict["data_status"] = details.get("data_status", "UNAVAILABLE")
        item_dict["platform"] = details["platform"]
        item_dict["best_platform"] = details["best_platform"]
        item_dict["sample_count"] = details.get("sample_count", 0)
        if canonical_model_map is not None:
            mid = getattr(item, "model_id", None)
            c_model = canonical_model_map.get(mid) if mid else None
            if c_model is not None and getattr(c_model, "base_score", None):
                item_dict["canonical_base_score"] = int(c_model.base_score)
                item_dict["canonical_model_name"] = getattr(c_model, "name", None)
                item_dict["score_source"] = "canonical"
            else:
                item_dict["canonical_base_score"] = int(getattr(item, "base_score", 0) or 0)
                item_dict["canonical_model_name"] = None
                item_dict["score_source"] = "product_fallback"
        result.append(item_dict)
    return result

@app.get("/cpus")
def get_cpus(db: Session = Depends(get_db)):
    items = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
    cpu_model_map = {m.model_id: m for m in db.query(models.CPUModel).all()}
    return enrich_catalog_items(items, "cpu_id", db, canonical_model_map=cpu_model_map)

@app.get("/gpus")
def get_gpus(db: Session = Depends(get_db)):
    items = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
    gpu_model_map = {m.model_id: m for m in db.query(models.GPUModel).all()}
    return enrich_catalog_items(items, "gpu_id", db, canonical_model_map=gpu_model_map)

@app.get("/gpu-models")
def get_gpu_models(db: Session = Depends(get_db)):
    return db.query(models.GPUModel).all()

@app.get("/gpu-models/{model_id}")
def get_gpu_model_by_id(model_id: str, db: Session = Depends(get_db)):
    model = db.query(models.GPUModel).filter(models.GPUModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"GPU model '{model_id}' not found")
    return model

@app.get("/gpu-models/{model_id}/products")
def get_gpu_products_by_model(model_id: str, db: Session = Depends(get_db)):
    model = db.query(models.GPUModel).filter(models.GPUModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"GPU model '{model_id}' not found")
    items = db.query(models.GPU).filter(
        models.GPU.model_id == model_id,
        models.GPU.is_reference_only == False
    ).all()
    return enrich_catalog_items(items, "gpu_id", db, canonical_model_map={model_id: model})

@app.get("/cpu-models")
def get_cpu_models(db: Session = Depends(get_db)):
    return db.query(models.CPUModel).all()

@app.get("/cpu-models/{model_id}")
def get_cpu_model_by_id(model_id: str, db: Session = Depends(get_db)):
    model = db.query(models.CPUModel).filter(models.CPUModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"CPU model '{model_id}' not found")
    return model

@app.get("/cpu-models/{model_id}/products")
def get_cpu_products_by_model(model_id: str, db: Session = Depends(get_db)):
    model = db.query(models.CPUModel).filter(models.CPUModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"CPU model '{model_id}' not found")
    items = db.query(models.CPU).filter(
        models.CPU.model_id == model_id,
        models.CPU.is_reference_only == False
    ).all()
    return enrich_catalog_items(items, "cpu_id", db, canonical_model_map={model_id: model})

@app.get("/motherboards")
def get_motherboards(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.Motherboard).all(), "mobo_id", db)

@app.get("/coolers")
def get_coolers(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.Cooler).all(), "cooler_id", db)

@app.get("/cases")
def get_cases(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.Case).all(), "case_id", db)

@app.get("/rams")
def get_rams(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.RAM).all(), "ram_id", db)

@app.get("/storages")
def get_storages(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.Storage).all(), "storage_id", db)

@app.get("/psus")
def get_psus(db: Session = Depends(get_db)): 
    return enrich_catalog_items(db.query(models.PSU).all(), "psu_id", db)

@app.get("/evaluation/metrics")
def get_evaluation_metrics(db: Session = Depends(get_db)):
    """
    Returns the dynamic empirical evaluation results.
    Reads from evaluation_results.json or runs a live evaluation if missing.
    """
    json_path = DATA_DIR / "evaluation_results.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # If file doesn't exist on Render, compute directly from DB — ZERO hardcoded dummy data
    live_results = evaluate_and_export_results(db)
    if live_results:
        return live_results
    
    raise HTTPException(status_code=503, detail="Evaluation dataset is not seeded. Please run POST /seed first.")

@app.post("/scrape")
def trigger_live_market_scraper():
    """
    Triggers the multi-listing Playwright scraper in an isolated thread.
    """
    worker_thread = threading.Thread(target=run_scraper_in_background, daemon=True)
    worker_thread.start()
    return {
        "status": "processing", 
        "message": "Scraper pipeline initiated in background thread. Monitoring console for progress."
    }

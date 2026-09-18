import asyncio
import sys
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional

from .database import get_db
from . import models
from .scraper import run_global_scraper_pipeline

# Windows-specific asyncio policy patch for Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


app = FastAPI(title="EcoBuild API", description="Heuristic PC Builder Simulation Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PYDANTIC INPUT SCHEMAS ---
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

class OptimizeRequest(BaseModel):
    budget: float
    game_name: str
    resolution: str

# --- GAME CONSTANTS MATRIX ---
GAME_CONSTANTS = {
    "Cyberpunk 2077": 0.0046,  # High-intensity title
    "Valorant": 0.025          # Light, CPU-bound title
}

@app.get("/")
def read_root():
    return {"status": "online", "message": "EcoBuild Prediction Engine Active"}

# --- SEEDING ENDPOINT (Packs your database with parts instantly) ---
@app.post("/seed", status_code=201)
def seed_database(db: Session = Depends(get_db)):
    db.query(models.CPU).delete()
    db.query(models.Motherboard).delete()
    db.query(models.GPU).delete()
    db.query(models.Cooler).delete()
    db.query(models.Case).delete()
    db.query(models.RAM).delete()
    db.query(models.Storage).delete()
    db.query(models.PSU).delete()

    cpus = [
        models.CPU(cpu_id="i3_12100F", name="Intel Core i3-12100F", socket="LGA1700", tdp_watts=65, base_score=14000, price=380.00),
        models.CPU(cpu_id="i5_12400F", name="Intel Core i5-12400F", socket="LGA1700", tdp_watts=65, base_score=19500, price=520.00),
        models.CPU(cpu_id="i9_14900K", name="Intel Core i9-14900K", socket="LGA1700", tdp_watts=253, base_score=60000, price=2550.00),
        models.CPU(cpu_id="ryzen_5600", name="AMD Ryzen 5 5600", socket="AM4", tdp_watts=65, base_score=21000, price=510.00),
        models.CPU(cpu_id="ryzen_7800X3D", name="AMD Ryzen 7 7800X3D", socket="AM5", tdp_watts=120, base_score=34000, price=1850.00)
    ]
    
    mobos = [
        models.Motherboard(mobo_id="b660m", name="Gigabyte B660M DS3H DDR4", socket="LGA1700", form_factor="MATX", ram_type="DDR4", price=420.00),
        models.Motherboard(mobo_id="z790", name="MSI PRO Z790-A Wi-Fi DDR5", socket="LGA1700", form_factor="ATX", ram_type="DDR5", price=1100.00),
        models.Motherboard(mobo_id="b550m", name="ASRock B550M Steel Legend", socket="AM4", form_factor="MATX", ram_type="DDR4", price=380.00),
        models.Motherboard(mobo_id="b650m", name="Gigabyte B650M Gaming Wi-Fi", socket="AM5", form_factor="MATX", ram_type="DDR5", price=650.00)
    ]

    gpus = [
        models.GPU(gpu_id="rtx_3060", name="NVIDIA GeForce RTX 3060 12GB", pcie_slot="PCIe_x16", tdp_watts=170, base_score=13000, price=1250.00),
        models.GPU(gpu_id="rtx_4060", name="MSI Ventus RTX 4060 8GB", pcie_slot="PCIe_x16", tdp_watts=115, base_score=15500, price=1399.00),
        models.GPU(gpu_id="rtx_4070", name="ASUS Dual RTX 4070 12GB", pcie_slot="PCIe_x16", tdp_watts=200, base_score=26000, price=2899.00),
        models.GPU(gpu_id="rx_6600", name="Sapphire Pulse RX 6600 8GB", pcie_slot="PCIe_x16", tdp_watts=132, base_score=11000, price=990.00)
    ]

    coolers = [
        models.Cooler(cooler_id="stock", name="Intel/AMD Stock Cooler", socket_list="LGA1700,AM4", max_tdp=65, price=30.00),
        models.Cooler(cooler_id="air_cooler", name="Deepcool AG400 Air Cooler", socket_list="LGA1700,AM4,AM5", max_tdp=220, price=95.00),
        models.Cooler(cooler_id="liquid_aio", name="Cooler Master 240mm Liquid AIO", socket_list="LGA1700,AM4,AM5", max_tdp=250, price=280.00)
    ]

    cases = [
        models.Case(case_id="mesh_atx", name="Tecware Forge M Omni Mesh ATX", form_factor="ATX", airflow_coef=1.00, price=180.00),
        models.Case(case_id="glass_matx", name="InWin 301 Tempered Glass MATX", form_factor="MATX", airflow_coef=0.80, price=150.00),
        models.Case(case_id="itx_case", name="Lian Li Q58 Compact ITX", form_factor="ITX", airflow_coef=0.60, price=250.00)
    ]

    rams = [
        models.RAM(ram_id="ddr4_16gb", name="Kingston Fury Beast 16GB DDR4 3200MHz", ram_type="DDR4", capacity_gb=16, speed_mhz=3200, price=180.00),
        models.RAM(ram_id="ddr5_32gb", name="G.Skill Flare X5 32GB DDR5 5600MHz", ram_type="DDR5", capacity_gb=32, speed_mhz=5600, price=450.00)
    ]

    storages = [
        models.Storage(storage_id="ssd_500gb", name="Kingston NV2 500GB NVMe M.2", type="NVMe_M2", capacity_gb=500, price=150.00),
        models.Storage(storage_id="ssd_1tb", name="Samsung 980 Pro 1TB NVMe M.2", type="NVMe_M2", capacity_gb=1000, price=350.00)
    ]

    psus = [
        models.PSU(psu_id="psu_550w", name="Corsair CV550 550W 80+ Bronze", wattage=550, efficiency="Bronze", price=220.00),
        models.PSU(psu_id="psu_750w", name="Deepcool PM750D 750W 80+ Gold", wattage=750, efficiency="Gold", price=360.00)
    ]

    db.add_all(cpus + mobos + gpus + coolers + cases + rams + storages + psus)
    db.commit()
    return {"message": "Database populated successfully with baseline hardware specifications"}

# --- THE PREDICITIVE SIMULATION API (EcoBuild's Logical Brain) ---
@app.post("/simulate")
def simulate_build_configuration(request: SimulationRequest, db: Session = Depends(get_db)):
    cpu = db.query(models.CPU).filter(models.CPU.cpu_id == request.cpu_id).first()
    mobo = db.query(models.Motherboard).filter(models.Motherboard.mobo_id == request.mobo_id).first()
    gpu = db.query(models.GPU).filter(models.GPU.gpu_id == request.gpu_id).first()
    cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == request.cooler_id).first()
    case = db.query(models.Case).filter(models.Case.case_id == request.case_id).first()
    ram = db.query(models.RAM).filter(models.RAM.ram_id == request.ram_id).first()
    psu = db.query(models.PSU).filter(models.PSU.psu_id == request.psu_id).first()
    storage = db.query(models.Storage).filter(models.Storage.storage_id == request.storage_id).first()

    if not all([cpu, mobo, gpu, cooler, case, ram, psu, storage]):
        raise HTTPException(status_code=400, detail="One or more selected components do not exist in the database.")

    warnings = []
    
    # Socket Check (Physical Constraint)
    if cpu.socket != mobo.socket:
        warnings.append(f"Physical Mismatch: Chosen CPU requires an {cpu.socket} socket, but Motherboard is designed for {mobo.socket}.")
    
    # Motherboard vs Case Sizing Check (Physical Constraint)
    form_factors = {"ATX": 3, "MATX": 2, "ITX": 1}
    if form_factors[mobo.form_factor] > form_factors[case.form_factor]:
         warnings.append(f"Sizing Conflict: Motherboard form factor ({mobo.form_factor}) exceeds PC Case size limitations ({case.form_factor}).")

    # RAM Type Check (Physical Constraint)
    if ram.ram_type != mobo.ram_type:
         warnings.append(f"Memory Mismatch: Selected Motherboard supports only {mobo.ram_type} RAM, but chosen RAM is {ram.ram_type}.")

    # HEURISTIC THERMAL DYNAMICS MODEL
    ambient_temp = 30.0
    thermal_load = (cpu.tdp_watts / cooler.max_tdp) / float(case.airflow_coef)
    predicted_temp = ambient_temp + (thermal_load * 35.0)

    thermal_status = "Stable"
    thermal_penalty = 1.0
    if predicted_temp > 90.0:
        thermal_status = "THROTTLING"
        thermal_penalty = 0.82
        warnings.append(f"Thermal Overload Warning: Selected Cooler cannot dissipate {cpu.tdp_watts}W TDP inside a restricted Case environment. Expect CPU throttling.")
    elif predicted_temp > 78.0:
        thermal_status = "High Load"

    # HEURISTIC FPS ENGINE (CPU/GPU Synergy)
    res_modifiers = {"1080p": 1.0, "1440p": 0.72, "4K": 0.45}
    game_constant = GAME_CONSTANTS.get(request.game_name, 0.01)
    raw_fps = gpu.base_score * game_constant * res_modifiers[request.resolution]

    bottleneck_ratio = cpu.base_score / gpu.base_score
    bottleneck_penalty = 1.0
    bottleneck_status = "Balanced Synergy"
    
    if bottleneck_ratio < 0.8:
        bottleneck_penalty = 0.78
        bottleneck_status = "CPU Bottleneck"
        warnings.append(f"CPU Bottleneck: Your CPU ({cpu.name}) limits the graphics output of your GPU ({gpu.name}) by approximately {round((1 - bottleneck_ratio)*100)}%.")

    final_fps = raw_fps * bottleneck_penalty * thermal_penalty

    # PSU Wattage Headroom Check
    total_system_tdp = cpu.tdp_watts + gpu.tdp_watts + 50
    minimum_required_psu = total_system_tdp / 0.80
    if psu.wattage < minimum_required_psu:
        warnings.append(f"Power Supply Risk: Your system draws a maximum of {total_system_tdp}W. We recommend a minimum of {round(minimum_required_psu)}W PSU for safe operation, but your chosen PSU is only {psu.wattage}W.")

    total_price_rm = float(cpu.price + mobo.price + gpu.price + cooler.price + case.price + ram.price + psu.price + storage.price)

    return {
        "total_price_rm": round(total_price_rm, 2),
        "predicted_fps": round(final_fps),
        "predicted_temp_c": round(predicted_temp, 1),
        "thermal_status": thermal_status,
        "bottleneck_status": bottleneck_status,
        "bottleneck_percentage": round((1 - bottleneck_ratio) * 100) if bottleneck_ratio < 0.8 else 0,
        "warnings": warnings
    }

# --- THE 0-1 KNAPSACK BUDGET OPTIMIZATION ENGINE ---
@app.post("/optimize")
def optimize_build_configuration(request: OptimizeRequest, db: Session = Depends(get_db)):
    # 1. Fetch all elements from DB
    cpus = db.query(models.CPU).all()
    mobos = db.query(models.Motherboard).all()
    gpus = db.query(models.GPU).all()
    coolers = db.query(models.Cooler).all()
    cases = db.query(models.Case).all()
    rams = db.query(models.RAM).all()
    storages = db.query(models.Storage).all()
    psus = db.query(models.PSU).all()

    best_build = None
    max_fps = -1.0
    min_cost = float('inf')

    form_factors = {"ATX": 3, "MATX": 2, "ITX": 1}

    # 2. Bounded Knapsack search loop
    for cpu in cpus:
        for mobo in mobos:
            # Physical Socket Check
            if cpu.socket != mobo.socket:
                continue
            
            for ram in rams:
                # RAM Type Check
                if ram.ram_type != mobo.ram_type:
                    continue
                
                for gpu in gpus:
                    for cooler in coolers:
                        # Cooler Socket Compatibility
                        if cpu.socket not in cooler.socket_list:
                            continue
                        
                        for case in cases:
                            # Sizing Check (Form Factor)
                            if form_factors[mobo.form_factor] > form_factors[case.form_factor]:
                                continue
                            
                            for psu in psus:
                                # Power Supply Wattage Safety Check
                                total_system_tdp = cpu.tdp_watts + gpu.tdp_watts + 50
                                min_required_psu_wattage = total_system_tdp / 0.8
                                if psu.wattage < min_required_psu_wattage:
                                    continue
                                
                                for storage in storages:
                                    # Calculate total cost
                                    total_price = float(cpu.price + mobo.price + gpu.price + cooler.price + case.price + ram.price + psu.price + storage.price)
                                    if total_price > request.budget:
                                        continue
                                    
                                    # 3. HEURISTIC MATH ENGINE (Runs on potential builds)
                                    res_modifiers = {"1080p": 1.0, "1440p": 0.72, "4K": 0.45}
                                    game_constant = GAME_CONSTANTS.get(request.game_name, 0.01)
                                    
                                    # Base FPS
                                    raw_fps = gpu.base_score * game_constant * res_modifiers[request.resolution]
                                    
                                    # CPU Bottleneck Check
                                    bottleneck_ratio = cpu.base_score / gpu.base_score
                                    bottleneck_penalty = 0.78 if bottleneck_ratio < 0.8 else 1.0
                                    
                                    # Thermal Throttling Check
                                    thermal_load = (cpu.tdp_watts / cooler.max_tdp) / float(case.airflow_coef)
                                    predicted_temp = 30.0 + (thermal_load * 35.0)
                                    thermal_penalty = 0.82 if predicted_temp > 90.0 else 1.0
                                    
                                    # Final FPS
                                    final_fps = raw_fps * bottleneck_penalty * thermal_penalty
                                    
                                    # Knapsack decision: Maximize performance. If performance is equal, choose cheaper.
                                    if final_fps > max_fps or (final_fps == max_fps and total_price < min_cost):
                                        max_fps = final_fps
                                        min_cost = total_price
                                        best_build = {
                                            "cpu": cpu,
                                            "mobo": mobo,
                                            "gpu": gpu,
                                            "cooler": cooler,
                                            "case": case,
                                            "ram": ram,
                                            "psu": psu,
                                            "storage": storage,
                                            "predicted_fps": round(final_fps),
                                            "predicted_temp_c": round(predicted_temp, 1),
                                            "total_price_rm": round(total_price, 2)
                                        }

    if not best_build:
        raise HTTPException(status_code=404, detail="No valid, compatible component combinations could be found within this budget limit.")

    return best_build

# --- TRIGGER SCRAPER ENGINE ---
@app.post("/scrape")
async def trigger_live_market_scraper():
    # Runs the async scraping pipeline in the background
    asyncio.create_task(run_global_scraper_pipeline())
    return {"status": "processing", "message": "Playwright background scraper initiated. PostgreSQL registry updates will occur asynchronously."}

# --- Standard Database Get Routes ---
@app.get("/cpus")
def get_cpus(db: Session = Depends(get_db)):
    return db.query(models.CPU).all()

@app.get("/gpus")
def get_gpus(db: Session = Depends(get_db)):
    return db.query(models.GPU).all()

@app.get("/motherboards")
def get_motherboards(db: Session = Depends(get_db)):
    return db.query(models.Motherboard).all()

@app.get("/coolers")
def get_coolers(db: Session = Depends(get_db)):
    return db.query(models.Cooler).all()

@app.get("/cases")
def get_cases(db: Session = Depends(get_db)):
    return db.query(models.Case).all()

@app.get("/rams")
def get_rams(db: Session = Depends(get_db)):
    return db.query(models.RAM).all()

@app.get("/storages")
def get_storages(db: Session = Depends(get_db)):
    return db.query(models.Storage).all()

@app.get("/psus")
def get_psus(db: Session = Depends(get_db)):
    return db.query(models.PSU).all()

@app.get("/prices")
def get_scraped_prices(db: Session = Depends(get_db)):
    return db.query(models.ScrapedPrice).all()
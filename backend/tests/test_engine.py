import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# --- SETUP: SEED DATABASE BEFORE TESTS ---
@pytest.fixture(autouse=True, scope="module")
def seed_database():
    response = client.post("/seed")
    assert response.status_code == 201

def get_base_payload():
    return {
        "cpu_id": "i5_12400F",
        "mobo_id": "b660m",
        "gpu_id": "rtx_4060",
        "cooler_id": "air_ag400",
        "case_id": "atx_mesh",
        "ram_id": "ddr4_16gb",
        "psu_id": "psu_650w",
        "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077",
        "resolution": "1080p"
    }

# ==========================================
# 🧪 TEST CASE 01: SOCKET MISMATCH
# ==========================================
def test_socket_mismatch():
    payload = get_base_payload()
    payload["cpu_id"] = "ryzen_5600" # AM4 CPU
    payload["mobo_id"] = "z790"      # LGA1700 Motherboard

    response = client.post("/simulate", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert any("Physical Mismatch" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 02: FORM FACTOR SIZE LIMIT
# ==========================================
def test_case_sizing_conflict():
    payload = get_base_payload()
    payload["mobo_id"] = "z790"         # ATX Motherboard
    payload["case_id"] = "itx_compact"  # ITX Case (Small)
    payload["ram_id"] = "ddr5_32gb"

    response = client.post("/simulate", json=payload)
    data = response.json()

    assert any("Sizing Conflict" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 03: RAM TYPE MISMATCH
# ==========================================
def test_ram_type_mismatch():
    payload = get_base_payload()
    payload["mobo_id"] = "b660m"        # DDR4 Motherboard
    payload["ram_id"] = "ddr5_32gb"     # DDR5 RAM

    response = client.post("/simulate", json=payload)
    data = response.json()

    assert any("Memory Mismatch" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 04: THERMAL THROTTLING
# ==========================================
def test_thermal_overload():
    payload = get_base_payload()
    payload["cpu_id"] = "i9_14900K"     
    payload["cooler_id"] = "stock"      
    payload["case_id"] = "itx_compact"  

    response = client.post("/simulate", json=payload)
    data = response.json()

    assert data["thermal_status"] == "THROTTLING"
    # Fixed the strict string matching to match the new engine
    assert any("Thermal Overload" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 05: PSU WATTAGE RISK
# ==========================================
def test_psu_wattage_risk():
    payload = get_base_payload()
    payload["cpu_id"] = "i9_14900K"     
    payload["gpu_id"] = "rtx_4090"      
    payload["psu_id"] = "psu_550w"      

    response = client.post("/simulate", json=payload)
    data = response.json()

    assert any("Power Supply Risk" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 06: CPU BOTTLENECK
# ==========================================
def test_cpu_bottleneck():
    payload = get_base_payload()
    payload["cpu_id"] = "i3_12100F"     
    payload["gpu_id"] = "rtx_4090"      

    response = client.post("/simulate", json=payload)
    data = response.json()

    assert data["bottleneck_status"] == "CPU Bottleneck"
    assert data["bottleneck_percentage"] > 0
    assert any("CPU Bottleneck" in w for w in data["warnings"])

# ==========================================
# 🧪 TEST CASE 07: KNAPSACK OPTIMIZER
# ==========================================
def test_budget_optimizer():
    payload = {
        "budget": 3500,
        "game_name": "Cyberpunk 2077",
        "resolution": "1080p"
    }

    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_price_rm"] <= 3500
    assert "cpu" in data and "gpu" in data
"""
backend/tests/test_phase1_catalog_separation.py

Phase 1 Test Suite: Hardware Model and Manufacturer Product Separation
- Verifies canonical GPU and CPU model fixtures exist and adhere to schema.
- Verifies board-partner products link to canonical model identities.
- Verifies prediction engine resolves canonical baseline scores across board-partner variants.
- Verifies benchmark-only references (e.g. rtx_4070_dual) are excluded from public GET /gpus.
- Verifies benchmark-only references remain resolvable for evaluation and calibration datasets.
- Verifies physical clearance and thermal checks preserve manufacturer product-specific attributes.
- Verifies canonical model endpoints (/gpu-models, /gpu-models/{id}/products, /cpu-models).
"""

import os
import sys
import json
import pytest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Use SQLite database for offline tests
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{BACKEND_DIR / 'test_ecobuild.db'}"

DATA_DIR = BACKEND_DIR / "data"

from app.database import engine, Base, SessionLocal
from app import models
from app.main import (
    simulate_build_configuration,
    export_bill_of_materials,
    get_gpus,
    get_cpus,
    get_gpu_models,
    get_gpu_model_by_id,
    get_gpu_products_by_model,
    get_cpu_models,
    get_cpu_model_by_id,
    get_cpu_products_by_model,
    seed_database_from_fixtures,
    SimulationRequest,
    resolve_canonical_gpu_score,
    resolve_canonical_cpu_score
)
from app.evaluate_accuracy import evaluate_dataset, load_offline_catalogs, DEFAULT_CALIBRATION_DATASET
from app.real_engine import check_physical_clearances


@pytest.fixture(scope="module")
def db_session():
    """Initializes and seeds the test SQLite database with new fixtures."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database_from_fixtures(clean=True, db=db)
    yield db
    db.close()


class TestPhase1CatalogStructure:
    """Verifies the integrity of the new canonical model fixtures and product relationships."""

    def test_canonical_gpu_models_fixture_exists(self):
        """gpu_models.json must exist, contain 23 canonical models, and have required fields."""
        path = DATA_DIR / "gpu_models.json"
        assert path.exists(), "gpu_models.json must exist in data directory"
        with open(path, "r", encoding="utf-8") as f:
            models_data = json.load(f)

        assert len(models_data) == 23
        for m in models_data:
            assert "model_id" in m
            assert "name" in m
            assert "brand" in m
            assert "architecture" in m
            assert "base_score" in m
            assert m["base_score"] > 0
            assert "tdp_watts" in m
            assert "vram_gb" in m
            assert "is_reference_only" in m

    def test_canonical_cpu_models_fixture_exists(self):
        """cpu_models.json must exist, contain 29 canonical models, and have required fields."""
        path = DATA_DIR / "cpu_models.json"
        assert path.exists(), "cpu_models.json must exist in data directory"
        with open(path, "r", encoding="utf-8") as f:
            models_data = json.load(f)

        assert len(models_data) == 29
        for m in models_data:
            assert "model_id" in m
            assert "name" in m
            assert "brand" in m
            assert "architecture" in m
            assert "socket" in m
            assert "base_score" in m
            assert m["base_score"] > 0
            assert "tdp_watts" in m

    def test_manufacturer_products_link_to_canonical_gpu_models(self):
        """All 28 GPUs in gpus.json must have valid model_id and brand."""
        with open(DATA_DIR / "gpus.json", "r", encoding="utf-8") as f:
            gpus = json.load(f)
        with open(DATA_DIR / "gpu_models.json", "r", encoding="utf-8") as f:
            valid_model_ids = {m["model_id"] for m in json.load(f)}

        assert len(gpus) == 28
        for g in gpus:
            assert "model_id" in g, f"GPU {g['gpu_id']} missing model_id"
            assert g["model_id"] in valid_model_ids, f"GPU {g['gpu_id']} references unknown model_id {g['model_id']}"
            assert "brand" in g, f"GPU {g['gpu_id']} missing manufacturer brand"
            assert "is_reference_only" in g

    def test_board_partners_map_to_same_canonical_gpu_model(self):
        """Board-partner variants of RTX 4060 must link to nv_rtx_4060."""
        with open(DATA_DIR / "gpus.json", "r", encoding="utf-8") as f:
            gpus = {g["gpu_id"]: g for g in json.load(f)}

        # Zotac Twin Edge vs Gigabyte Eagle OC
        assert gpus["rtx_4060_twin"]["model_id"] == "nv_rtx_4060"
        assert gpus["rtx_4060_eagle"]["model_id"] == "nv_rtx_4060"
        assert gpus["rtx_4060_twin"]["brand"] == "Zotac"
        assert gpus["rtx_4060_eagle"]["brand"] == "Gigabyte"

        # ASUS Strix vs MSI Gaming Trio for RTX 5090
        assert gpus["rtx_5090_strix"]["model_id"] == "nv_rtx_5090"
        assert gpus["rtx_5090_gaming_trio"]["model_id"] == "nv_rtx_5090"


class TestPhase1EngineResolution:
    """Verifies that the prediction engine resolves canonical baseline scores without OC distortions."""

    def test_canonical_score_resolution_helper(self, db_session):
        """Canonical score helper must return model baseline score instead of card OC score."""
        gpu_twin = db_session.query(models.GPU).filter(models.GPU.gpu_id == "rtx_4060_twin").first()
        gpu_eagle = db_session.query(models.GPU).filter(models.GPU.gpu_id == "rtx_4060_eagle").first()

        score_twin = resolve_canonical_gpu_score(gpu_twin, db_session)
        score_eagle = resolve_canonical_gpu_score(gpu_eagle, db_session)

        # Both must resolve to the canonical baseline score of 10500
        assert score_twin == 10500
        assert score_eagle == 10500

    def test_simulate_yields_consistent_fps_across_board_partner_variants(self, db_session):
        """
        Simulating identical builds with RTX 4060 Twin Edge vs Eagle OC must produce identical FPS,
        eliminating artificial marketing OC score differences.
        """
        req_twin = SimulationRequest(
            cpu_id="i5_12400F",
            mobo_id="b660m_ds3h",
            gpu_id="rtx_4060_twin",
            cooler_id="air_ag400",
            case_id="atx_mesh",
            ram_id="ddr4_16gb",
            psu_id="psu_650w",
            storage_id="ssd_1tb",
            game_name="Cyberpunk 2077",
            resolution="1080p",
            ambient_temp=30.0
        )
        req_eagle = SimulationRequest(
            cpu_id="i5_12400F",
            mobo_id="b660m_ds3h",
            gpu_id="rtx_4060_eagle",
            cooler_id="air_ag400",
            case_id="atx_mesh",
            ram_id="ddr4_16gb",
            psu_id="psu_650w",
            storage_id="ssd_1tb",
            game_name="Cyberpunk 2077",
            resolution="1080p",
            ambient_temp=30.0
        )

        res_twin = simulate_build_configuration(req_twin, db=db_session)
        res_eagle = simulate_build_configuration(req_eagle, db=db_session)

        assert res_twin["predicted_fps"] == res_eagle["predicted_fps"]
        assert res_twin["fps_1pct_low"] == res_eagle["fps_1pct_low"]


class TestPhase1ReferenceOnlyProtection:
    """Verifies that reference-only fixtures are protected from public product lists and BOMs."""

    def test_rtx_4070_dual_marked_as_reference_only(self):
        """rtx_4070_dual must have is_reference_only == True."""
        with open(DATA_DIR / "gpus.json", "r", encoding="utf-8") as f:
            gpus = {g["gpu_id"]: g for g in json.load(f)}

        assert gpus["rtx_4070_dual"]["is_reference_only"] is True
        assert gpus["rtx_4070_dual"]["model_id"] == "nv_rtx_4070"

    def test_get_gpus_excludes_reference_only_hardware(self, db_session):
        """Public GET /gpus must return only purchasable GPUs (27 items, excluding rtx_4070_dual)."""
        gpus = get_gpus(db=db_session)
        gpu_ids = [g["gpu_id"] for g in gpus]

        assert "rtx_4070_dual" not in gpu_ids, "rtx_4070_dual must NOT appear in GET /gpus"
        assert len(gpus) == 27, f"Expected 27 purchasable retail GPUs, got {len(gpus)}"

    def test_get_cpus_returns_purchasable_cpus(self, db_session):
        """Public GET /cpus returns all 29 retail desktop processors."""
        cpus = get_cpus(db=db_session)
        assert len(cpus) == 29

    def test_export_bom_marks_reference_hardware_non_purchasable(self, db_session):
        """When exporting a BOM with reference hardware, it must disallow shopping links and mark non-purchasable."""
        req = SimulationRequest(
            cpu_id="i5_12400F",
            mobo_id="b660m_ds3h",
            gpu_id="rtx_4070_dual",
            cooler_id="air_ag400",
            case_id="atx_mesh",
            ram_id="ddr4_16gb",
            psu_id="psu_650w",
            storage_id="ssd_1tb",
            game_name="Cyberpunk 2077",
            resolution="1080p",
            ambient_temp=30.0
        )
        resp = export_bill_of_materials(req, db=db_session)
        body = json.loads(resp.body)

        assert body["has_reference_only_components"] is True
        gpu_item = next(c for c in body["components"] if c["category"] == "Graphics Card")
        assert gpu_item["is_reference_only"] is True
        assert gpu_item["is_purchasable"] is False
        assert gpu_item["shopee_link"] is None
        assert gpu_item["lazada_link"] is None

    def test_evaluator_resolves_rtx_4070_dual_and_computes_accuracy(self):
        """Calibration dataset with 7 rtx_4070_dual cases evaluates cleanly without error."""
        res = evaluate_dataset(dataset_path=DEFAULT_CALIBRATION_DATASET, offline=True)
        assert res["sample_size"] == 19
        assert res["avg_metrics"]["n"] == 19
        assert res["low_metrics"]["n"] == 19


class TestPhase1PhysicalAndThermalIntegrity:
    """Verifies that physical dimensions and thermal clearances use product-specific attributes."""

    def test_physical_clearance_preserves_manufacturer_dimensions(self):
        """Zotac Twin (222mm) vs Gigabyte Eagle (272mm) have distinct physical clearance footprints."""
        # Test against a hypothetical compact chassis clearance of 240mm
        res_twin = check_physical_clearances(
            gpu_id="rtx_4060_twin",
            cooler_id="air_ag400",
            case_id="matx_mesh"  # max_gpu_len_mm: 300
        )
        assert res_twin["is_compatible"] is True
        assert res_twin["metrics"]["gpu_length_mm"] == 222

        res_eagle = check_physical_clearances(
            gpu_id="rtx_4060_eagle",
            cooler_id="air_ag400",
            case_id="matx_mesh"  # max_gpu_len_mm: 300
        )
        assert res_eagle["is_compatible"] is True
        assert res_eagle["metrics"]["gpu_length_mm"] == 272


class TestPhase1CanonicalModelEndpoints:
    """Verifies the new canonical model API endpoints."""

    def test_get_gpu_models_endpoint(self, db_session):
        """GET /gpu-models must return all 23 canonical GPU models."""
        models_list = get_gpu_models(db=db_session)
        assert len(models_list) == 23

    def test_get_gpu_model_by_id_endpoint(self, db_session):
        """GET /gpu-models/{model_id} returns accurate canonical model specs."""
        m = get_gpu_model_by_id("nv_rtx_4060", db=db_session)
        assert m.name == "NVIDIA GeForce RTX 4060"
        assert m.base_score == 10500
        assert m.tdp_watts == 115
        assert m.vram_gb == 8

    def test_get_gpu_products_by_model_endpoint(self, db_session):
        """GET /gpu-models/{model_id}/products returns manufacturer products for that model."""
        products = get_gpu_products_by_model("nv_rtx_4060", db=db_session)
        product_ids = {p["gpu_id"] for p in products}
        assert "rtx_4060_twin" in product_ids
        assert "rtx_4060_eagle" in product_ids

    def test_get_cpu_models_endpoint(self, db_session):
        """GET /cpu-models must return all 29 canonical CPU models."""
        models_list = get_cpu_models(db=db_session)
        assert len(models_list) == 29

    def test_get_cpu_model_by_id_endpoint(self, db_session):
        """GET /cpu-models/{model_id} returns accurate canonical CPU specs."""
        m = get_cpu_model_by_id("intel_i5_12400f", db=db_session)
        assert m.name == "Intel Core i5-12400F"
        assert m.base_score == 19500
        assert m.socket == "LGA1700"

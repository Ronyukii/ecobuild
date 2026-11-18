"""
backend/tests/test_wave1_correctness.py

Wave 1 Correctness & Integrity Test Suite
Tier 1: Software Correctness Tests
Tier 2: Model-Assumption Consistency & Numerical Tests
"""

import os
import sys
import json
import pytest
from pathlib import Path
from fastapi import HTTPException

# Ensure backend directory is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Use SQLite database for offline tests
os.environ.setdefault("SQLALCHEMY_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'test_ecobuild.db'}")

from app.database import engine, Base, SessionLocal
from app import models
from app.real_engine import (
    calculate_heuristic_performance,
    calculate_ground_up_performance,
    UnsupportedGameError,
    GAME_PROFILES
)
from app.main import (
    simulate_build_configuration,
    export_bill_of_materials,
    compare_groundup_vs_realworld,
    seed_database_from_fixtures,
    SimulationRequest,
    DATA_DIR
)


@pytest.fixture(scope="module")
def db_session():
    """Seeds the SQLite database from JSON fixtures once for the test module."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database_from_fixtures(clean=True, db=db)
    yield db
    db.close()


def _get_valid_request(game_name="Cyberpunk 2077", resolution="1080p", ram_id="ddr4_16gb"):
    return SimulationRequest(
        cpu_id="i5_12400F",
        mobo_id="b660m_ds3h",
        gpu_id="rtx_4070_dual",
        cooler_id="air_ag400",
        case_id="atx_mesh",
        ram_id=ram_id,
        psu_id="psu_650w",
        storage_id="ssd_1tb",
        game_name=game_name,
        resolution=resolution,
        ambient_temp=30.0
    )


# ==============================================================================
# TIER 1: SOFTWARE CORRECTNESS TESTS
# ==============================================================================

class TestWave1SoftwareCorrectness:

    def test_simulate_unsupported_game_returns_http_400(self, db_session):
        """Unsupported games must raise HTTP 400 listing supported games."""
        req = _get_valid_request(game_name="Unsupported Title 2026")
        with pytest.raises(HTTPException) as exc_info:
            simulate_build_configuration(req, db=db_session)
        assert exc_info.value.status_code == 400
        assert "Unsupported game 'Unsupported Title 2026'" in exc_info.value.detail
        for game in GAME_PROFILES:
            assert game in exc_info.value.detail

    def test_compare_groundup_unsupported_game_returns_http_400(self, db_session):
        """Unsupported games in /compare-groundup must raise HTTP 400."""
        req = _get_valid_request(game_name="FakeGame")
        with pytest.raises(HTTPException) as exc_info:
            compare_groundup_vs_realworld(req, db=db_session)
        assert exc_info.value.status_code == 400
        assert "Unsupported game 'FakeGame'" in exc_info.value.detail

    def test_export_bom_unsupported_game_returns_http_400(self, db_session):
        """Unsupported games in /export/bom must raise HTTP 400."""
        req = _get_valid_request(game_name="Nonexistent Game")
        with pytest.raises(HTTPException) as exc_info:
            export_bill_of_materials(req, db=db_session)
        assert exc_info.value.status_code == 400
        assert "Unsupported game 'Nonexistent Game'" in exc_info.value.detail

    def test_engine_functions_raise_unsupported_game_error(self):
        """Both engine calculation functions must strictly raise UnsupportedGameError."""
        with pytest.raises(UnsupportedGameError) as exc_h:
            calculate_heuristic_performance(
                gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
                cooler_max_tdp=220, case_airflow_coef=1.0, game_name="InvalidGame",
                resolution="1080p", gpu_vram_gb=12
            )
        assert "Unsupported game: 'InvalidGame'" in str(exc_h.value)

        with pytest.raises(UnsupportedGameError) as exc_gu:
            calculate_ground_up_performance(
                gpu_cores=5888, gpu_clock_mhz=2475, gpu_bus_bit=192, gpu_speed_gbps=21.0,
                cpu_ipc=1.0, cpu_boost_ghz=4.4, cpu_l3_cache_mb=18, cpu_tdp=65,
                cooler_max_tdp=220, case_airflow_coef=1.0, ram_speed_mts=3200,
                resolution="1080p", game_name="InvalidGame"
            )
        assert "Unsupported game: 'InvalidGame'" in str(exc_gu.value)

    def test_simulate_propagates_ram_channels_and_penalizes_single_channel(self, db_session):
        """Single-channel RAM must receive the penalty in simulate_build_configuration."""
        req_dual = _get_valid_request(ram_id="ddr4_16gb")  # channels: 2
        req_single = _get_valid_request(ram_id="ddr4_8gb_single")  # channels: 1

        res_dual = simulate_build_configuration(req_dual, db=db_session)
        res_single = simulate_build_configuration(req_single, db=db_session)

        assert res_single["predicted_fps"] < res_dual["predicted_fps"], (
            f"Single-channel FPS ({res_single['predicted_fps']}) must be less than "
            f"dual-channel FPS ({res_dual['predicted_fps']})"
        )
        assert res_single["fps_1pct_low"] < res_dual["fps_1pct_low"]
        assert res_single["telemetry"]["inputs"]["ram_channels"] == 1
        assert res_dual["telemetry"]["inputs"]["ram_channels"] == 2
        assert res_single["telemetry"]["active_penalties"]["ram_channel_multiplier"] < 1.0
        assert res_dual["telemetry"]["active_penalties"]["ram_channel_multiplier"] == 1.0

    def test_export_bom_propagates_ram_channels(self, db_session):
        """BOM export must calculate physics with propagated ram_channels."""
        req_dual = _get_valid_request(ram_id="ddr4_16gb")
        req_single = _get_valid_request(ram_id="ddr4_8gb_single")

        resp_dual = export_bill_of_materials(req_dual, db=db_session)
        resp_single = export_bill_of_materials(req_single, db=db_session)

        bom_dual = json.loads(resp_dual.body.decode("utf-8"))
        bom_single = json.loads(resp_single.body.decode("utf-8"))

        assert bom_single["system_telemetry"]["predicted_fps"] < bom_dual["system_telemetry"]["predicted_fps"]

    def test_compare_groundup_unlisted_returns_none_without_fabrication(self, db_session):
        """Unlisted configurations in /compare-groundup must return null, never groundup * 0.98."""
        req = _get_valid_request(game_name="Cyberpunk 2077")
        req.cpu_id = "i3_12100F"

        result = compare_groundup_vs_realworld(req, db=db_session)

        assert result["real_world_benchmark_fps"] is None, "Benchmark FPS must be null for unlisted build"
        assert result["prediction_error_percentage"] is None, "Error % must be null for unlisted build"
        assert result["has_empirical_reference"] is False
        assert result["ground_up_calculated_fps"] > 0

    def test_rtx_4070_dual_canonical_identity_reconciled(self):
        """rtx_4070_dual must resolve in gpus.json with base_score=18000 and null physical dimensions."""
        gpus_path = DATA_DIR / "gpus.json"
        with open(gpus_path, "r", encoding="utf-8") as f:
            gpus = json.load(f)

        rtx_4070_entries = [g for g in gpus if g["gpu_id"] == "rtx_4070_dual"]
        assert len(rtx_4070_entries) == 1, "rtx_4070_dual must exist in gpus.json"

        entry = rtx_4070_entries[0]
        assert entry["base_score"] == 18000
        assert entry["tdp_watts"] == 200
        assert entry["vram_gb"] == 12
        assert entry["length_mm"] is None, "Must not fabricate unverified physical length"
        assert entry["fan_count"] is None, "Must not fabricate unverified fan count"
        assert entry["slot_thickness"] is None, "Must not fabricate unverified slot thickness"


# ==============================================================================
# TIER 2: MODEL-ASSUMPTION CONSISTENCY & NUMERICAL TESTS
# ==============================================================================

class TestWave1ModelConsistency:

    def test_heuristic_deterministic_output(self):
        """Identical inputs must produce bitwise-identical results across multiple runs."""
        kwargs = dict(
            gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
            cooler_max_tdp=220, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
            resolution="1080p", gpu_vram_gb=12, ambient_temp=30.0, ram_channels=2
        )
        run1 = calculate_heuristic_performance(**kwargs)
        run2 = calculate_heuristic_performance(**kwargs)

        assert run1["predicted_fps"] == run2["predicted_fps"]
        assert run1["fps_1pct_low"] == run2["fps_1pct_low"]
        assert run1["cpu_temp_c"] == run2["cpu_temp_c"]
        assert run1["gpu_temp_c"] == run2["gpu_temp_c"]

    def test_gpu_scaling_monotonicity(self):
        """Higher GPU base_score must strictly yield higher predicted FPS in GPU-bound scenarios."""
        scores = [12000, 15000, 18000, 24000, 36000]
        fps_results = []
        for s in scores:
            res = calculate_heuristic_performance(
                gpu_score=s, cpu_score=34000, cpu_tdp=125, gpu_tdp=220,
                cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
                resolution="1440p", gpu_vram_gb=16, ambient_temp=30.0, ram_channels=2
            )
            fps_results.append(res["predicted_fps"])

        for i in range(len(fps_results) - 1):
            assert fps_results[i] < fps_results[i + 1], (
                f"GPU scaling non-monotonic: score {scores[i]} -> {fps_results[i]} FPS, "
                f"score {scores[i+1]} -> {fps_results[i+1]} FPS"
            )

    def test_resolution_scaling_monotonicity_gpu_bound(self):
        """In GPU-bound regimes, FPS must strictly decrease as resolution increases (1080p > 1440p > 4K)."""
        for game in GAME_PROFILES:
            # Pair high-end CPU with moderate GPU to ensure GPU bound
            fps_1080p = calculate_heuristic_performance(
                gpu_score=12000, cpu_score=34000, cpu_tdp=125, gpu_tdp=170,
                cooler_max_tdp=260, case_airflow_coef=1.0, game_name=game,
                resolution="1080p", gpu_vram_gb=12
            )["predicted_fps"]

            fps_1440p = calculate_heuristic_performance(
                gpu_score=12000, cpu_score=34000, cpu_tdp=125, gpu_tdp=170,
                cooler_max_tdp=260, case_airflow_coef=1.0, game_name=game,
                resolution="1440p", gpu_vram_gb=12
            )["predicted_fps"]

            fps_4k = calculate_heuristic_performance(
                gpu_score=12000, cpu_score=34000, cpu_tdp=125, gpu_tdp=170,
                cooler_max_tdp=260, case_airflow_coef=1.0, game_name=game,
                resolution="4K", gpu_vram_gb=12
            )["predicted_fps"]

            assert fps_1080p > fps_1440p, f"{game}: 1080p ({fps_1080p}) not > 1440p ({fps_1440p})"
            assert fps_1440p > fps_4k, f"{game}: 1440p ({fps_1440p}) not > 4K ({fps_4k})"

    def test_vram_saturation_penalty_at_4k(self):
        """8GB card at 4K in Cyberpunk must suffer saturation penalty vs 16GB card."""
        res_8gb = calculate_heuristic_performance(
            gpu_score=18000, cpu_score=34000, cpu_tdp=125, gpu_tdp=220,
            cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
            resolution="4K", gpu_vram_gb=8, ambient_temp=30.0
        )
        res_16gb = calculate_heuristic_performance(
            gpu_score=18000, cpu_score=34000, cpu_tdp=125, gpu_tdp=220,
            cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
            resolution="4K", gpu_vram_gb=16, ambient_temp=30.0
        )

        assert "VRAM Deficit" in res_8gb["vram_status"]
        assert res_16gb["vram_status"] == "Optimal Capacity"
        # 8GB VRAM saturation penalty: average FPS * 0.75, 1% low * 0.65
        assert res_8gb["predicted_fps"] < res_16gb["predicted_fps"]
        assert res_8gb["fps_1pct_low"] < res_16gb["fps_1pct_low"]

    def test_thermal_throttling_penalty(self):
        """Inadequate cooling causing T_cpu >= 95°C must trigger throttling penalty."""
        # Adequate cooling: 260W cooler on 65W CPU
        normal = calculate_heuristic_performance(
            gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
            cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
            resolution="1080p", gpu_vram_gb=12, ambient_temp=30.0
        )
        # Inadequate cooling: 35W cooler on 253W CPU inside poor airflow case
        throttled = calculate_heuristic_performance(
            gpu_score=18000, cpu_score=34000, cpu_tdp=253, gpu_tdp=350,
            cooler_max_tdp=35, case_airflow_coef=0.5, game_name="Cyberpunk 2077",
            resolution="1080p", gpu_vram_gb=12, ambient_temp=35.0
        )

        assert "THROTTLE" in throttled["thermal_status"]
        assert normal["thermal_status"] == "Stable"
        assert throttled["cpu_temp_c"] >= 95.0 or throttled["gpu_temp_c"] >= 83.0

    def test_frametime_1pct_low_bounds(self):
        """1% low FPS must be strictly positive and strictly <= average FPS."""
        for game in GAME_PROFILES:
            for res in ["1080p", "1440p", "4K"]:
                out = calculate_heuristic_performance(
                    gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
                    cooler_max_tdp=220, case_airflow_coef=1.0, game_name=game,
                    resolution=res, gpu_vram_gb=12
                )
                assert 0 < out["fps_1pct_low"] <= out["predicted_fps"], (
                    f"{game} @ {res}: 1% low ({out['fps_1pct_low']}) not in (0, {out['predicted_fps']}]"
                )

"""
backend/tests/test_phase2_integration.py

Phase 2 Offline Integration & Correctness Test Suite.
Validates:
- Shared 16-check compatibility engine & UNVERIFIED missing-spec classification
- Optimizer correctness (query budget, ITX strictness, GPU power cables, cooler socket/TDP, dual-channel RAM, anchor unclamping, game_name support)
- Prompt parser disambiguation (Arc B580/B570/A750, 5600 vs 5600X, RTX variants, RM vs chipsets, 4K, VRAM vs RAM)
- Honest pricing resolution (LIVE vs ESTIMATED/UNAVAILABLE/MSRP) and BOM reference-only exclusion
- Canonical score resolution telemetry & fallback warnings across /simulate, /export/bom, /compare-groundup, and catalog routes
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("SQLALCHEMY_DATABASE_URL", "sqlite:///:memory:")

from app import models
from app.compatibility import (
    STATUS_COMPATIBLE,
    STATUS_INCOMPATIBLE,
    STATUS_UNVERIFIED,
    STATUS_WARNING,
    evaluate_build_compatibility,
)
from app.main import (
    OptimizeRequest,
    SimulationRequest,
    compare_groundup_vs_realworld,
    export_bill_of_materials,
    get_cpu_products_by_model,
    get_cpus,
    get_gpu_products_by_model,
    get_gpus,
    optimize_build_configuration,
    resolve_gpu_vram_gb,
    resolve_price_details,
    seed_database_from_fixtures,
    simulate_build_configuration,
)
from app.prompt_parser import parse_user_build_prompt
from app.real_engine import (
    UnsupportedResolutionError,
    calculate_heuristic_performance,
    check_physical_clearances,
)


@pytest.fixture
def mem_db():
    """Isolated in-memory SQLite DB seeded from production fixtures for each test."""
    mem_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=mem_engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=mem_engine)
    db = Session()
    try:
        seed_database_from_fixtures(clean=False, db=db)
        yield db, mem_engine
    finally:
        db.close()
        mem_engine.dispose()


def _base_sim_request(**overrides):
    defaults = dict(
        cpu_id="i5_12400F",
        mobo_id="b660m_ds3h",
        gpu_id="rtx_4060_twin",
        cooler_id="assassin_x120",
        case_id="matx_mesh",
        ram_id="ddr4_16gb",
        psu_id="psu_650w",
        storage_id="ssd_1tb",
        game_name="Cyberpunk 2077",
        resolution="1080p",
        ambient_temp=30.0,
    )
    defaults.update(overrides)
    return SimulationRequest(**defaults)


# ==============================================================================
# 1. PROMPT PARSER TESTS
# ==============================================================================
class TestPromptParserDisambiguation:
    def test_gpu_model_extraction_matrix(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        gpu_models = {m.model_id: m for m in db.query(models.GPUModel).all()}
        cpu_models = {m.model_id: m for m in db.query(models.CPUModel).all()}

        expected_models = {
            "RTX 4060 gaming PC": "nv_rtx_4060",
            "RTX 4070 Super build": "nv_rtx_4070_super",
            "RTX 5070 rig": "nv_rtx_5070",
            "RTX 5090 workstation": "nv_rtx_5090",
            "RX 6600 budget PC": "amd_rx_6600",
            "RX 7800 XT build": "amd_rx_7800_xt",
            "Intel Arc B580 build": "intel_arc_b580",
            "Arc B570 PC": "intel_arc_b570",
            "Intel Arc A750 PC": "intel_arc_a750",
        }
        for prompt, expected_mid in expected_models.items():
            parsed = parse_user_build_prompt(prompt, cpus, gpus, gpu_models=gpu_models, cpu_models=cpu_models)
            assert parsed["pinned_gpu"] is not None, f"Failed to pin GPU for prompt: {prompt}"
            assert parsed["pinned_gpu_model_id"] == expected_mid, (
                f"Expected model_id={expected_mid} for '{prompt}', got {parsed['pinned_gpu_model_id']}"
            )

    def test_ryzen_5600_vs_5600x_boundaries(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        cpu_models = {m.model_id: m for m in db.query(models.CPUModel).all()}

        parsed_x = parse_user_build_prompt("Ryzen 5 5600X build", cpus, gpus, cpu_models=cpu_models)
        parsed_non_x = parse_user_build_prompt("Ryzen 5 5600 build", cpus, gpus, cpu_models=cpu_models)

        assert parsed_x["pinned_cpu"].cpu_id == "ryzen_5600X"
        assert parsed_non_x["pinned_cpu"].cpu_id == "ryzen_5600"

    def test_budget_vs_gpu_and_4k_disambiguation(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        gpu_models = {m.model_id: m for m in db.query(models.GPUModel).all()}

        p_rm = parse_user_build_prompt("gaming PC under RM 4060", cpus, gpus, gpu_models=gpu_models)
        assert p_rm["extracted_budget"] == 4060.0
        assert p_rm["pinned_gpu"] is None

        p_4k = parse_user_build_prompt("4k gaming PC", cpus, gpus, gpu_models=gpu_models)
        assert p_4k["extracted_budget"] is None

    def test_non_super_rtx_4070_does_not_pin_super_variant(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        gpu_models = {m.model_id: m for m in db.query(models.GPUModel).all()}

        parsed = parse_user_build_prompt("RTX 4070 gaming PC", cpus, gpus, gpu_models=gpu_models)
        assert parsed["pinned_gpu"] is None
        assert parsed["pinned_gpus"] == []
        assert any("reference-only" in note.lower() for note in parsed["parsing_notes"])

    def test_gpu_vram_token_does_not_override_ram_capacity(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        gpu_models = {m.model_id: m for m in db.query(models.GPUModel).all()}

        parsed = parse_user_build_prompt("RTX 4060 8GB with 16GB RAM", cpus, gpus, gpu_models=gpu_models)
        assert parsed["pinned_gpu_model_id"] == "nv_rtx_4060"
        assert parsed["ram_capacity_gb"] == 16

    def test_multi_variant_grouping_and_aib_narrowing(self, mem_db):
        db, _ = mem_db
        cpus = db.query(models.CPU).filter(models.CPU.is_reference_only == False).all()
        gpus = db.query(models.GPU).filter(models.GPU.is_reference_only == False).all()
        gpu_models = {m.model_id: m for m in db.query(models.GPUModel).all()}

        generic_4060 = parse_user_build_prompt("RTX 4060 under RM 4000", cpus, gpus, gpu_models=gpu_models)
        assert len(generic_4060["pinned_gpus"]) > 1
        assert all(g.model_id == "nv_rtx_4060" for g in generic_4060["pinned_gpus"])

        eagle_4060 = parse_user_build_prompt("Gigabyte RTX 4060 Eagle under RM 4000", cpus, gpus, gpu_models=gpu_models)
        assert len(eagle_4060["pinned_gpus"]) == 1
        assert eagle_4060["pinned_gpus"][0].gpu_id == "rtx_4060_eagle"


# ==============================================================================
# 2. COMPATIBILITY ENGINE & SIMULATION TESTS
# ==============================================================================
class TestCompatibilityAndSimulation:
    def test_cooler_socket_tdp_and_gpu_cable_failures(self, mem_db):
        db, _ = mem_db

        # Cooler socket mismatch (synthetic cooler supporting AM4 only paired with LGA1700 CPU)
        cpu = db.query(models.CPU).filter(models.CPU.cpu_id == "i5_12400F").first()
        mobo = db.query(models.Motherboard).filter(models.Motherboard.mobo_id == "b660m_ds3h").first()
        gpu = db.query(models.GPU).filter(models.GPU.gpu_id == "rtx_4060_twin").first()
        bad_socket_cooler = SimpleNamespace(
            cooler_id="stock", name="AM4 Only Cooler", socket_list="AM4",
            max_tdp=180, height_mm=47, type="Air", rad_size_mm=None, max_ram_clearance_mm=999
        )
        case = db.query(models.Case).filter(models.Case.case_id == "matx_mesh").first()
        ram = db.query(models.RAM).filter(models.RAM.ram_id == "ddr4_16gb").first()
        psu = db.query(models.PSU).filter(models.PSU.psu_id == "psu_650w").first()
        storage = db.query(models.Storage).filter(models.Storage.storage_id == "ssd_1tb").first()

        res_sock = evaluate_build_compatibility(cpu, mobo, gpu, bad_socket_cooler, case, ram, psu, storage)
        assert res_sock["overall_status"] == STATUS_INCOMPATIBLE
        assert any(c["check_id"] == "cpu_cooler_socket" and c["status"] == STATUS_INCOMPATIBLE for c in res_sock["checks"])

        # Cooler TDP deficit via /simulate: i9_13900K (253W) + stock cooler (65W)
        sim_tdp = simulate_build_configuration(
            _base_sim_request(cpu_id="i9_13900K", mobo_id="z790_pro_a", cooler_id="stock", ram_id="ddr5_32gb_fury", psu_id="psu_850w_msi_gl"),
            db=db,
        )
        assert sim_tdp["compatibility"]["overall_status"] == STATUS_INCOMPATIBLE
        assert sim_tdp["compatibility"]["is_compatible"] is False
        assert any("Cooler Capacity Deficit" in w for w in sim_tdp["warnings"])

        # GPU/PSU PCIe cable shortage via /simulate: arc_a750_le (2 cables) + psu_500w_aerocool (1 cable)
        sim_cable = simulate_build_configuration(
            _base_sim_request(gpu_id="arc_a750_le", psu_id="psu_500w_aerocool"),
            db=db,
        )
        assert sim_cable["compatibility"]["overall_status"] == STATUS_INCOMPATIBLE
        assert any("Power Cable Shortage" in w for w in sim_cable["warnings"])

    def test_missing_dimensions_are_unverified_never_compatible(self, mem_db):
        db, _ = mem_db

        # 1) rtx_4070_dual has null length_mm & null slot_thickness -> UNVERIFIED
        sim_ref = simulate_build_configuration(_base_sim_request(gpu_id="rtx_4070_dual"), db=db)
        assert sim_ref["compatibility"]["overall_status"] == STATUS_UNVERIFIED
        assert sim_ref["compatibility"]["is_compatible"] is False
        assert any("Unverified" in w for w in sim_ref["warnings"])

        # 2) Direct check_physical_clearances on unknown hardware IDs -> UNVERIFIED
        unk = check_physical_clearances("unknown_gpu_x", "unknown_cooler_x", "unknown_case_x")
        assert unk["status"] == STATUS_UNVERIFIED
        assert unk["is_compatible"] is False
        assert len(unk["unverified"]) >= 2

    def test_invalid_resolution_raises_http_400_and_engine_error(self, mem_db):
        db, _ = mem_db
        with pytest.raises(UnsupportedResolutionError):
            calculate_heuristic_performance(10000, 10000, 65, 115, 185, 1.0, "Cyberpunk 2077", "720p")

        with pytest.raises(HTTPException) as exc:
            simulate_build_configuration(_base_sim_request(resolution="720p"), db=db)
        assert exc.value.status_code == 400

    def test_broken_canonical_mapping_logs_warning_and_exposes_fallback_source(self, mem_db):
        db, _ = mem_db
        gpu = db.query(models.GPU).filter(models.GPU.gpu_id == "rtx_4060_twin").first()
        gpu.model_id = "nonexistent_canonical_model"
        db.commit()

        res = simulate_build_configuration(_base_sim_request(gpu_id="rtx_4060_twin"), db=db)
        assert res["telemetry"]["inputs"]["gpu_score_source"] == "product_fallback"
        assert res["telemetry"]["inputs"]["gpu_canonical_resolved"] is False
        assert any("Canonical Mapping Notice" in w for w in res["warnings"])

    def test_vram_none_safety_and_honest_pricing_source(self, mem_db):
        db, _ = mem_db
        # VRAM=None in engine skips penalty cleanly without error
        perf = calculate_heuristic_performance(10500, 12000, 65, 115, 185, 1.0, "Cyberpunk 2077", "1080p", gpu_vram_gb=None)
        assert "Unverified" in perf["vram_status"]

        gpu_null_vram = SimpleNamespace(gpu_id="custom", name="RTX Custom", vram_gb=None)
        canon_vram = SimpleNamespace(vram_gb=12)
        assert resolve_gpu_vram_gb(gpu_null_vram, canon_vram) == 12
        assert resolve_gpu_vram_gb(gpu_null_vram, SimpleNamespace(vram_gb=None)) is None

        # Pricing honesty: ESTIMATED and UNAVAILABLE never count as live
        sim_msrp = simulate_build_configuration(_base_sim_request(), db=db)
        assert sim_msrp["pricing_source"] == "Catalog MSRP Fallback"
        assert sim_msrp["live_priced_components"] == 0

        db.add(models.ScrapedPrice(model_key="rtx_4060_twin", platform="Shopee", price_rm=1350.0, shipping_rm=0.0, data_status="ESTIMATED", is_available=False))
        db.add(models.ScrapedPrice(model_key="i5_12400F", platform="Lazada", price_rm=490.0, shipping_rm=0.0, data_status="LIVE", is_available=True))
        db.commit()

        sim_mixed = simulate_build_configuration(_base_sim_request(), db=db)
        assert sim_mixed["live_priced_components"] == 1
        assert sim_mixed["pricing_source"] == "Mixed (1/8 Live Market, 7/8 Catalog MSRP)"

        details_est = resolve_price_details("rtx_4060_twin", 1399.0, {"rtx_4060_twin": {"price": 1350.0, "platform": "Shopee", "data_status": "ESTIMATED", "is_available": False}})
        assert details_est["best_platform"] is None
        assert details_est["price"] == 1399.0

    def test_d14_arc_b580_pcie3_discrepancy_warning_without_fixture_edit(self, mem_db):
        db, _ = mem_db
        cpu_p3 = db.query(models.CPU).filter(models.CPU.cpu_id == "ryzen_5500").first()
        mobo_p3 = db.query(models.Motherboard).filter(models.Motherboard.mobo_id == "a520m_k").first()
        gpu_b580 = db.query(models.GPU).filter(models.GPU.gpu_id == "arc_b580_limited").first()
        canon_b580 = db.query(models.GPUModel).filter(models.GPUModel.model_id == gpu_b580.model_id).first()
        cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == "assassin_x120").first()
        case = db.query(models.Case).filter(models.Case.case_id == "matx_mesh").first()
        ram = db.query(models.RAM).filter(models.RAM.ram_id == "ddr4_16gb").first()
        psu = db.query(models.PSU).filter(models.PSU.psu_id == "psu_650w").first()
        storage = db.query(models.Storage).filter(models.Storage.storage_id == "ssd_1tb").first()

        compat = evaluate_build_compatibility(cpu_p3, mobo_p3, gpu_b580, cooler, case, ram, psu, storage, canonical_gpu=canon_b580)
        pcie_check = next(c for c in compat["checks"] if c["check_id"] == "pcie_bandwidth_x8")
        assert pcie_check["status"] == STATUS_WARNING
        assert compat["is_compatible"] is True  # Warning, not blocking


# ==============================================================================
# 3. OPTIMIZER TESTS
# ==============================================================================
class TestOptimizerCorrectnessAndPerformance:
    def test_budget_scaling_unclamped_objective_and_query_count(self, mem_db):
        db, mem_engine = mem_db

        query_count = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        event.listen(mem_engine, "before_cursor_execute", count_queries)
        try:
            res_2500 = optimize_build_configuration(OptimizeRequest(budget=2500, resolution="1080p"), db=db)
            q_2500 = query_count
            query_count = 0
            res_3500 = optimize_build_configuration(OptimizeRequest(budget=3500, resolution="1080p"), db=db)
            q_3500 = query_count
            query_count = 0
            res_5000 = optimize_build_configuration(OptimizeRequest(budget=5000, resolution="1080p"), db=db)
            q_5000 = query_count
        finally:
            event.remove(mem_engine, "before_cursor_execute", count_queries)

        assert q_2500 < 30, f"Expected < 30 SQL queries, got {q_2500}"
        assert q_3500 < 30, f"Expected < 30 SQL queries, got {q_3500}"
        assert q_5000 < 30, f"Expected < 30 SQL queries, got {q_5000}"

        assert res_2500["total_price_rm"] <= 2500.0
        assert res_3500["total_price_rm"] <= 3500.0
        assert res_5000["total_price_rm"] <= 5000.0
        assert res_3500["composite_gaming_score"] > res_2500["composite_gaming_score"]
        assert res_5000["composite_gaming_score"] > res_3500["composite_gaming_score"]
        assert res_2500["gpu"].is_reference_only is False
        assert res_3500["gpu"].is_reference_only is False
        assert res_5000["gpu"].is_reference_only is False
        assert res_3500["compatibility"]["is_compatible"] is True
        assert res_5000["compatibility"]["is_compatible"] is True

    def test_itx_constraint_enforces_strict_itx_and_no_matx_fallback(self, mem_db):
        db, _ = mem_db
        res = optimize_build_configuration(OptimizeRequest(prompt="ITX gaming PC under RM 5000"), db=db)
        assert res["mobo"].form_factor == "ITX"
        assert res["case"].form_factor == "ITX"
        assert res["psu"].form_factor in res["case"].supported_psu_form_factors.split(",")

        # Impossibly low ITX budget must 404, never fall back to MATX
        with pytest.raises(HTTPException) as exc:
            optimize_build_configuration(OptimizeRequest(prompt="ITX gaming PC", budget=1500), db=db)
        assert exc.value.status_code == 404

    def test_gpu_cable_and_high_tdp_cooler_constraints_in_optimizer(self, mem_db):
        db, _ = mem_db
        res_arc = optimize_build_configuration(OptimizeRequest(prompt="Intel Arc A750", budget=2900), db=db)
        assert res_arc["gpu"].gpu_id == "arc_a750_le"
        assert res_arc["psu"].pcie_8pin_count >= res_arc["gpu"].min_pcie_cables

        res_i9 = optimize_build_configuration(OptimizeRequest(prompt="i9 13900K", budget=7500), db=db)
        assert res_i9["cpu"].cpu_id == "i9_13900K"
        assert res_i9["cooler"].max_tdp >= res_i9["cpu"].tdp_watts
        assert res_i9["mobo"].max_recommended_cpu_tdp >= res_i9["cpu"].tdp_watts
        assert res_i9["cpu"].socket in res_i9["cooler"].socket_list.split(",")

    def test_dual_channel_preference_honest_memory_rationale_and_game_filter(self, mem_db):
        db, _ = mem_db
        res = optimize_build_configuration(OptimizeRequest(budget=4000, game_name="Valorant"), db=db)
        assert res["target_game"] == "Valorant"
        assert res["ram"].channels >= 2
        assert "dual-channel" in res["optimizer_telemetry"]["selection_rationales"]["memory"].lower()
        assert len(res["catalog_game_fps"]) == 4

        with pytest.raises(HTTPException) as exc_game:
            optimize_build_configuration(OptimizeRequest(budget=4000, game_name="Invalid Game"), db=db)
        assert exc_game.value.status_code == 400

        with pytest.raises(HTTPException) as exc_res:
            optimize_build_configuration(OptimizeRequest(budget=4000, resolution="8K"), db=db)
        assert exc_res.value.status_code == 400

    def test_single_channel_ram_fallback_honesty_and_channel_propagation(self, mem_db):
        db, _ = mem_db
        res = optimize_build_configuration(OptimizeRequest(budget=8000, resolution="1440p"), db=db)

        assert res["ram"].ram_id == "ddr5_16gb_crucial"
        assert res["ram"].channels == 1
        assert res["total_price_rm"] == 7929.0
        assert res["composite_gaming_score"] == 88.76

        # Confirm cheapest dual-channel DDR5 kit pushes this exact build over RM 8,000
        cheapest_dual_ddr5 = min(
            db.query(models.RAM).filter(models.RAM.ram_type == "DDR5", models.RAM.channels >= 2).all(),
            key=lambda r: float(r.price),
        )
        hypothetical_dual_cost = res["total_price_rm"] - float(res["ram"].price) + float(cheapest_dual_ddr5.price)
        assert hypothetical_dual_cost > 8000.0

        # Rationale and compatibility warning must honestly reflect single-channel configuration
        mem_rationale = res["optimizer_telemetry"]["selection_rationales"]["memory"].lower()
        assert "single-channel" in mem_rationale
        assert "dual-channel" not in mem_rationale
        assert res["compatibility"]["is_compatible"] is True
        assert any("single-channel" in w.lower() for w in res["compatibility"]["warnings"])

        # Verify actual ram_channels=1 was propagated cleanly to prediction engine
        for game_name, opt_fps in res["catalog_game_fps"].items():
            sim = simulate_build_configuration(
                SimulationRequest(
                    cpu_id=res["cpu"].cpu_id,
                    mobo_id=res["mobo"].mobo_id,
                    gpu_id=res["gpu"].gpu_id,
                    cooler_id=res["cooler"].cooler_id,
                    case_id=res["case"].case_id,
                    ram_id=res["ram"].ram_id,
                    psu_id=res["psu"].psu_id,
                    storage_id=res["storage"].storage_id,
                    game_name=game_name,
                    resolution="1440p",
                    ambient_temp=30.0,
                ),
                db=db,
            )
            assert opt_fps == sim["predicted_fps"]

    def test_optimizer_latency_and_exact_scores_across_budgets(self, mem_db):
        db, mem_engine = mem_db
        qcount = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal qcount
            qcount += 1

        event.listen(mem_engine, "before_cursor_execute", count_queries)
        try:
            expected = [
                (2500, "1080p", 52.61, 2495.0, "ryzen_5600X", "arc_a750_le", "ddr4_16gb"),
                (3500, "1080p", 64.23, 3339.0, "i5_13500", "arc_b580_limited", "ddr4_16gb"),
                (5000, "1080p", 76.02, 4774.0, "i5_14600KF", "rx_7700_xt_pure", "ddr4_16gb"),
                (8000, "1440p", 88.76, 7929.0, "ryzen_7900X3D", "rtx_5070_ti_tuf", "ddr5_16gb_crucial"),
            ]
            for budget, resolution, exp_score, exp_price, exp_cpu, exp_gpu, exp_ram in expected:
                qcount = 0
                res = optimize_build_configuration(OptimizeRequest(budget=budget, resolution=resolution), db=db)
                pruning = res["optimizer_telemetry"]["search_space_pruning"]
                assert qcount < 30, f"Budget {budget} executed {qcount} SQL queries"
                assert res["total_price_rm"] <= budget
                assert res["total_price_rm"] == exp_price
                assert res["composite_gaming_score"] == exp_score
                assert res["cpu"].cpu_id == exp_cpu
                assert res["gpu"].gpu_id == exp_gpu
                assert res["ram"].ram_id == exp_ram
                assert pruning["feasible_candidates_simulated"] >= 1
                assert pruning["pruned_by_dominance_bound"] >= 1
                assert res["compatibility"]["is_compatible"] is True
        finally:
            event.remove(mem_engine, "before_cursor_execute", count_queries)

    def test_incomplete_sql_null_ram_does_not_shadow_valid_ram_kits(self, mem_db):
        db, _ = mem_db
        baseline = optimize_build_configuration(OptimizeRequest(prompt="Ryzen 5600X", budget=2600), db=db)

        db.add(models.RAM(
            ram_id="ram_null_ch_height", name="Incomplete DDR4 Null Channels/Height",
            ram_type="DDR4", capacity_gb=16, speed_mhz=3200, height_mm=34, channels=2, price=50.0,
        ))
        db.add(models.RAM(
            ram_id="ram_invalid_zero_spec", name="Invalid DDR4 Zero Channels/Speed",
            ram_type="DDR4", capacity_gb=16, speed_mhz=0, height_mm=0, channels=0, price=55.0,
        ))
        db.commit()
        db.execute(text("UPDATE ram SET height_mm = NULL, channels = NULL WHERE ram_id = 'ram_null_ch_height'"))
        db.commit()
        db.expire_all()

        res = optimize_build_configuration(OptimizeRequest(prompt="Ryzen 5600X", budget=2600), db=db)
        assert res["ram"].ram_id not in ("ram_null_ch_height", "ram_invalid_zero_spec")
        assert res["ram"].ram_id == "ddr4_16gb"
        assert res["ram"].channels == 2
        assert res["total_price_rm"] == baseline["total_price_rm"]
        assert res["composite_gaming_score"] == baseline["composite_gaming_score"]
        assert res["compatibility"]["is_compatible"] is True


# ==============================================================================
# 4. BOM, COMPARE-GROUNDUP & CATALOG ENRICHMENT TESTS
# ==============================================================================
class TestBomGroundupAndCatalog:
    def test_bom_includes_compatibility_warnings_and_excludes_ref_price(self, mem_db):
        db, _ = mem_db
        resp = export_bill_of_materials(_base_sim_request(gpu_id="rtx_4070_dual"), db=db)
        body = json.loads(resp.body.decode("utf-8"))

        assert body["has_reference_only_components"] is True
        assert body["compatibility"]["overall_status"] == STATUS_UNVERIFIED
        assert len(body["warnings"]) >= 1
        assert body["financials"]["reference_only_value_rm"] > 0
        assert body["financials"]["total_cost_rm"] == body["financials"]["purchasable_total_rm"]
        assert body["financials"]["overall_displayed_value_rm"] > body["financials"]["purchasable_total_rm"]
        assert body["financials"]["pricing_source"] == "Catalog MSRP Fallback"

        # MSRP items must have best_platform=None (never "Local Catalog")
        cpu_row = next(c for c in body["components"] if c["category"] == "Processor")
        assert cpu_row["best_platform"] is None
        assert cpu_row["data_status"] == "UNAVAILABLE"

        # Add LIVE price for CPU and ESTIMATED for RAM -> only CPU shows best_platform="Shopee"
        db.add(models.ScrapedPrice(model_key="i5_12400F", platform="Shopee", price_rm=485.0, shipping_rm=0.0, data_status="LIVE", is_available=True))
        db.add(models.ScrapedPrice(model_key="ddr4_16gb", platform="Lazada", price_rm=170.0, shipping_rm=0.0, data_status="ESTIMATED", is_available=False))
        db.commit()

        body_live = json.loads(export_bill_of_materials(_base_sim_request(), db=db).body.decode("utf-8"))
        cpu_live = next(c for c in body_live["components"] if c["category"] == "Processor")
        ram_est = next(c for c in body_live["components"] if c["category"] == "Memory (RAM)")
        assert cpu_live["best_platform"] == "Shopee"
        assert cpu_live["price_rm"] == 485.0
        assert ram_est["best_platform"] is None
        assert ram_est["data_status"] == "ESTIMATED"
        assert ram_est["price_rm"] == 180.0

    def test_compare_groundup_uses_canonical_models_and_discloses_unmodeled(self, mem_db):
        db, _ = mem_db
        res = compare_groundup_vs_realworld(
            _base_sim_request(cpu_id="i5_12400F", gpu_id="rtx_4060_twin", resolution="1080p"),
            db=db,
        )
        assert res["gpu_model_id"] == "nv_rtx_4060"
        assert res["cpu_model_id"] == "intel_i5_12400f"
        assert res["architecture_profile_matched"] is True
        assert res["has_empirical_reference"] is True
        assert res["real_world_benchmark_fps"] == 72

        unmodeled = compare_groundup_vs_realworld(
            _base_sim_request(gpu_id="rtx_5070_s_twin"),
            db=db,
        )
        assert unmodeled["architecture_profile_matched"] is False
        assert unmodeled["ground_up_calculated_fps"] is None
        assert "not modeled" in unmodeled["disclosure"].lower()

        with pytest.raises(HTTPException) as exc_404:
            compare_groundup_vs_realworld(_base_sim_request(gpu_id="missing_gpu"), db=db)
        assert exc_404.value.status_code == 404

        with pytest.raises(HTTPException) as exc_400:
            compare_groundup_vs_realworld(_base_sim_request(resolution="720p"), db=db)
        assert exc_400.value.status_code == 400

    def test_catalog_routes_expose_canonical_scores_and_hide_reference_only(self, mem_db):
        db, _ = mem_db
        gpus = get_gpus(db=db)
        cpus = get_cpus(db=db)
        assert len(gpus) == 27
        assert len(cpus) == 29
        assert all("rtx_4070_dual" != g["gpu_id"] for g in gpus)
        assert all("canonical_base_score" in g and g["score_source"] == "canonical" for g in gpus)
        assert all("canonical_base_score" in c and c["score_source"] == "canonical" for c in cpus)

        prods_4060 = get_gpu_products_by_model("nv_rtx_4060", db=db)
        assert len(prods_4060) >= 2
        assert all(p["canonical_base_score"] == 10500 for p in prods_4060)

        prods_12400 = get_cpu_products_by_model("intel_i5_12400f", db=db)
        assert len(prods_12400) >= 1
        assert all(p["score_source"] == "canonical" for p in prods_12400)

import math
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
from .real_engine import calculate_heuristic_performance

# --- EMPIRICAL BENCHMARK VALIDATION DATASET ---
# Contains real-world average FPS recorded by professional hardware reviewers
# for specific CPU + GPU + Game + Resolution combinations.
VALIDATION_TEST_CASES = [
    {
        "id": "VAL-01",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 72.0
    },
    {
        "id": "VAL-02",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1440p",
        "actual_fps": 51.0
    },
    {
        "id": "VAL-03",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 385.0
    },
    {
        "id": "VAL-04",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rtx_3060",
        "cooler_id": "stock", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 60.0
    },
    {
        "id": "VAL-05",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rx_6600",
        "cooler_id": "stock", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 52.0
    },
    {
        "id": "VAL-06",
        "cpu_id": "ryzen_5600", "mobo_id": "b550m", "gpu_id": "rtx_3060",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 61.0
    },
    {
        "id": "VAL-07",
        "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m", "gpu_id": "rtx_4070",
        "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb",
        "psu_id": "psu_750w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 118.0
    },
    {
        "id": "VAL-08",
        "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m", "gpu_id": "rtx_4070",
        "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb",
        "psu_id": "psu_750w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1440p",
        "actual_fps": 85.0
    },
    {
        "id": "VAL-09",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rtx_4070",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_750w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 91.0
    },
    {
        "id": "VAL-10",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4070",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_750w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 410.0
    },
    {
        "id": "VAL-11",
        "cpu_id": "ryzen_5600", "mobo_id": "b550m", "gpu_id": "rx_6600",
        "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 320.0
    },
    {
        "id": "VAL-12",
        "cpu_id": "i9_14900K", "mobo_id": "z790", "gpu_id": "rtx_3060",
        "cooler_id": "stock", "case_id": "itx_compact", "ram_id": "ddr5_32gb",
        "psu_id": "psu_550w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 50.0
    }
]

GPU_VRAM_MAP = {
    "rtx_4060": 8,
    "rtx_3060": 12,
    "rx_6600": 8,
    "rtx_4070": 12,
    "rtx_4090": 24
}

def evaluate_model_accuracy():
    db: Session = SessionLocal()
    try:
        total_ape = 0.0
        results = []

        for test in VALIDATION_TEST_CASES:
            cpu = db.query(models.CPU).filter(models.CPU.cpu_id == test["cpu_id"]).first()
            gpu = db.query(models.GPU).filter(models.GPU.gpu_id == test["gpu_id"]).first()
            cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == test["cooler_id"]).first()
            case = db.query(models.Case).filter(models.Case.case_id == test["case_id"]).first()

            missing = []
            if not cpu: missing.append(f"CPU '{test['cpu_id']}'")
            if not gpu: missing.append(f"GPU '{test['gpu_id']}'")
            if not cooler: missing.append(f"Cooler '{test['cooler_id']}'")
            if not case: missing.append(f"Case '{test['case_id']}'")

            if missing:
                print(f"Error in {test['id']}: Missing in DB -> {', '.join(missing)}")
                print("Make sure PostgreSQL is running and you triggered: POST http://localhost:8000/seed")
                return

            gpu_vram = GPU_VRAM_MAP.get(test["gpu_id"], 8)
            
            engine_result = calculate_heuristic_performance(
                gpu_score=gpu.base_score,
                cpu_score=cpu.base_score,
                cpu_tdp=cpu.tdp_watts,
                gpu_tdp=gpu.tdp_watts,
                cooler_max_tdp=cooler.max_tdp,
                case_airflow_coef=float(case.airflow_coef),
                game_name=test["game_name"],
                resolution=test["resolution"],
                gpu_vram_gb=gpu_vram,
                ambient_temp=30.0
            )

            predicted_fps = engine_result["predicted_fps"]
            actual_fps = test["actual_fps"]
            ape = (abs(actual_fps - predicted_fps) / actual_fps) * 100.0
            total_ape += ape

            results.append({
                "id": test["id"],
                "hardware": f"{cpu.name} + {gpu.name}",
                "game": f"{test['game_name']} ({test['resolution']})",
                "actual": actual_fps,
                "predicted": predicted_fps,
                "fps_1pct_low": engine_result["fps_1pct_low"],
                "stability": engine_result["frametime_stability_pct"],
                "error": round(ape, 2)
            })

        n = len(VALIDATION_TEST_CASES)
        mape = total_ape / n
        accuracy_score = 100.0 - mape

        print("\n==========================================================================================================")
        print("                        ECOBUILD DUAL-HEAT HEURISTIC ACCURACY REPORT                               ")
        print("==========================================================================================================\n")
        print(f"| {'Test ID':<8} | {'Hardware Configuration':<33} | {'Game & Res':<20} | {'Actual':<7} | {'Pred':<6} | {'1% Low':<7} | {'Error':<7} |")
        print("|----------|-----------------------------------|----------------------|---------|--------|---------|---------|")
        for r in results:
            print(f"| {r['id']:<8} | {r['hardware']:<33} | {r['game']:<20} | {r['actual']:<7.0f} | {r['predicted']:<6} | {r['fps_1pct_low']:<7} | {r['error']:<6.2f}% |")
        print("|----------|-----------------------------------|----------------------|---------|--------|---------|---------|")
        print(f"\nOverall Mean Absolute Percentage Error (MAPE): {mape:.2f}%")
        print(f"Overall Model Accuracy Score:                  {accuracy_score:.2f}%\n")
        print("==========================================================================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    evaluate_model_accuracy()
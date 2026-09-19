import math
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models

# --- EMPIRICAL BENCHMARK VALIDATION DATASET ---
# Contains real-world average FPS recorded by professional hardware reviewers
# for specific CPU + GPU + Game + Resolution combinations.
VALIDATION_TEST_CASES = [
    {
        "id": "VAL-01",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 72.0
    },
    {
        "id": "VAL-02",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1440p",
        "actual_fps": 51.0
    },
    {
        "id": "VAL-03",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4060",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 385.0
    },
    {
        "id": "VAL-04",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rtx_3060",
        "cooler_id": "stock", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 60.0
    },
    {
        "id": "VAL-05",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rx_6600",
        "cooler_id": "stock", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 52.0
    },
    {
        "id": "VAL-06",
        "cpu_id": "ryzen_5600", "mobo_id": "b550m", "gpu_id": "rtx_3060",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 61.0
    },
    {
        "id": "VAL-07",
        "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m", "gpu_id": "rtx_4070",
        "cooler_id": "liquid_aio", "case_id": "mesh_atx", "ram_id": "ddr5_32gb",
        "psu_id": "psu_750w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 118.0
    },
    {
        "id": "VAL-08",
        "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m", "gpu_id": "rtx_4070",
        "cooler_id": "liquid_aio", "case_id": "mesh_atx", "ram_id": "ddr5_32gb",
        "psu_id": "psu_750w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1440p",
        "actual_fps": 85.0
    },
    {
        "id": "VAL-09",
        "cpu_id": "i3_12100F", "mobo_id": "b660m", "gpu_id": "rtx_4070",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_750w", "storage_id": "ssd_500gb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 91.0
    },
    {
        "id": "VAL-10",
        "cpu_id": "i5_12400F", "mobo_id": "b660m", "gpu_id": "rtx_4070",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_750w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 410.0
    },
    {
        "id": "VAL-11",
        "cpu_id": "ryzen_5600", "mobo_id": "b550m", "gpu_id": "rx_6600",
        "cooler_id": "air_cooler", "case_id": "mesh_atx", "ram_id": "ddr4_16gb",
        "psu_id": "psu_550w", "storage_id": "ssd_500gb",
        "game_name": "Valorant", "resolution": "1080p",
        "actual_fps": 320.0
    },
    {
        "id": "VAL-12",
        "cpu_id": "i9_14900K", "mobo_id": "z790", "gpu_id": "rtx_3060",
        "cooler_id": "stock", "case_id": "itx_case", "ram_id": "ddr5_32gb",
        "psu_id": "psu_550w", "storage_id": "ssd_1tb",
        "game_name": "Cyberpunk 2077", "resolution": "1080p",
        "actual_fps": 50.0
    }
]

GAME_CONSTANTS = {
    "Cyberpunk 2077": 0.0046,
    "Valorant": 0.025
}

def evaluate_model_accuracy():
    db: Session = SessionLocal()
    try:
        total_ape = 0.0
        results = []

        for test in VALIDATION_TEST_CASES:
            # Query components
            cpu = db.query(models.CPU).filter(models.CPU.cpu_id == test["cpu_id"]).first()
            gpu = db.query(models.GPU).filter(models.GPU.gpu_id == test["gpu_id"]).first()
            cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == test["cooler_id"]).first()
            case = db.query(models.Case).filter(models.Case.case_id == test["case_id"]).first()

            if not all([cpu, gpu, cooler, case]):
                print(f"Error: Components for {test['id']} not found in DB. Did you run /seed?")
                return

            # Execute Heuristic Engines
            res_modifiers = {"1080p": 1.0, "1440p": 0.72, "4K": 0.45}
            game_constant = GAME_CONSTANTS.get(test["game_name"], 0.01)
            raw_fps = gpu.base_score * game_constant * res_modifiers[test["resolution"]]

            # Bottleneck calculation
            bottleneck_ratio = cpu.base_score / gpu.base_score
            bottleneck_penalty = 0.78 if bottleneck_ratio < 0.8 else 1.0

            # Thermal calculation
            thermal_load = (cpu.tdp_watts / cooler.max_tdp) / float(case.airflow_coef)
            predicted_temp = 30.0 + (thermal_load * 35.0)
            thermal_penalty = 0.82 if predicted_temp > 90.0 else 1.0

            # Final predicted FPS
            predicted_fps = round(raw_fps * bottleneck_penalty * thermal_penalty)

            # Absolute Percentage Error (APE)
            actual_fps = test["actual_fps"]
            ape = (abs(actual_fps - predicted_fps) / actual_fps) * 100.0
            total_ape += ape

            results.append({
                "id": test["id"],
                "hardware": f"{cpu.name} + {gpu.name}",
                "game": f"{test['game_name']} ({test['resolution']})",
                "actual": actual_fps,
                "predicted": predicted_fps,
                "error": round(ape, 2)
            })

        # Calculate Mean Absolute Percentage Error (MAPE)
        n = len(VALIDATION_TEST_CASES)
        mape = total_ape / n
        accuracy_score = 100.0 - mape

        # Print Markdown Formatted Output for Chapter 4
        print("\n==========================================================================================")
        print("               ECOBUILD HEURISTIC ENGINE ACCURACY EVALUATION REPORT                       ")
        print("==========================================================================================\n")
        print(f"| {'Test ID':<8} | {'Hardware Configuration':<35} | {'Game & Resolution':<22} | {'Actual':<7} | {'Pred':<7} | {'Error (%)':<8} |")
        print("|----------|-------------------------------------|------------------------|---------|---------|-----------|")
        for r in results:
            print(f"| {r['id']:<8} | {r['hardware']:<35} | {r['game']:<22} | {r['actual']:<7.0f} | {r['predicted']:<7} | {r['error']:<7.2f}% |")
        print("|----------|-------------------------------------|------------------------|---------|---------|-----------|")
        print(f"\nOverall Mean Absolute Percentage Error (MAPE): {mape:.2f}%")
        print(f"Overall Model Accuracy Score:                  {accuracy_score:.2f}%\n")
        print("==========================================================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    evaluate_model_accuracy()
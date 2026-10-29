"""
backend/app/evaluate_accuracy.py — Academic Performance Validation Suite.

Computes:
- MAE  (Mean Absolute Error in FPS)
- RMSE (Root Mean Square Error in FPS)
- MAPE (Mean Absolute Percentage Error in %)
- R²   (Coefficient of Determination)
- Residual bias analysis grouped by Game and Resolution
- Automated export to Markdown and LaTeX tables for thesis Chapter 4.
"""

import math
import os
import statistics
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
from .real_engine import calculate_heuristic_performance

# --- EMPIRICAL REFERENCE BENCHMARK DATASET ---
# Conditions: Desktop platform, High/Ultra presets, Native resolution (No DLSS/FSR upscaling),
# RT Off, tested on modern Windows 11 with updated display drivers.
# Sourced from reputable hardware reviewers (TechPowerUp, Hardware Unboxed, Gamers Nexus).
BENCHMARK_DATASET = [
    # --- Cyberpunk 2077 (GPU-Heavy AAA Engine) ---
    {"id": "VAL-01", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Cyberpunk 2077", "res": "1080p", "ref_avg_fps": 72.0, "ref_1pct_low": 58.0},
    {"id": "VAL-02", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Cyberpunk 2077", "res": "1440p", "ref_avg_fps": 48.0, "ref_1pct_low": 37.0},
    {"id": "VAL-03", "cpu_id": "ryzen_5600", "mobo_id": "b550m_steel", "gpu_id": "rx_6600_sapphire", "cooler_id": "stock", "case_id": "matx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Cyberpunk 2077", "res": "1080p", "ref_avg_fps": 54.0, "ref_1pct_low": 42.0},
    {"id": "VAL-04", "cpu_id": "i3_12100F", "mobo_id": "h610m_asus", "gpu_id": "rtx_3060_dual", "cooler_id": "stock", "case_id": "matx_glass", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Cyberpunk 2077", "res": "1080p", "ref_avg_fps": 58.0, "ref_1pct_low": 45.0},
    {"id": "VAL-05", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Cyberpunk 2077", "res": "1080p", "ref_avg_fps": 118.0, "ref_1pct_low": 94.0},
    {"id": "VAL-06", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Cyberpunk 2077", "res": "1440p", "ref_avg_fps": 84.0, "ref_1pct_low": 68.0},
    {"id": "VAL-07", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Cyberpunk 2077", "res": "4K", "ref_avg_fps": 41.0, "ref_1pct_low": 32.0},
    {"id": "VAL-08", "cpu_id": "i7_13700KF", "mobo_id": "z790_pro_a", "gpu_id": "rtx_4080_s_gaming_oc", "cooler_id": "aio_360", "case_id": "montech_air_903", "ram_id": "ddr5_32gb", "psu_id": "psu_850w_msi_gl", "storage_id": "ssd_1tb", "game": "Cyberpunk 2077", "res": "1440p", "ref_avg_fps": 132.0, "ref_1pct_low": 105.0},
    {"id": "VAL-09", "cpu_id": "i7_13700KF", "mobo_id": "z790_pro_a", "gpu_id": "rtx_4080_s_gaming_oc", "cooler_id": "aio_360", "case_id": "montech_air_903", "ram_id": "ddr5_32gb", "psu_id": "psu_850w_msi_gl", "storage_id": "ssd_1tb", "game": "Cyberpunk 2077", "res": "4K", "ref_avg_fps": 68.0, "ref_1pct_low": 54.0},

    # --- Valorant (CPU-Bound Esports Engine) ---
    {"id": "VAL-10", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Valorant", "res": "1080p", "ref_avg_fps": 380.0, "ref_1pct_low": 240.0},
    {"id": "VAL-11", "cpu_id": "i3_12100F", "mobo_id": "h610m_asus", "gpu_id": "rtx_4060_twin", "cooler_id": "stock", "case_id": "matx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Valorant", "res": "1080p", "ref_avg_fps": 290.0, "ref_1pct_low": 175.0},
    {"id": "VAL-12", "cpu_id": "ryzen_5600", "mobo_id": "b550m_steel", "gpu_id": "rx_6600_sapphire", "cooler_id": "stock", "case_id": "matx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Valorant", "res": "1080p", "ref_avg_fps": 340.0, "ref_1pct_low": 210.0},
    {"id": "VAL-13", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Valorant", "res": "1080p", "ref_avg_fps": 580.0, "ref_1pct_low": 390.0},
    {"id": "VAL-14", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Valorant", "res": "1440p", "ref_avg_fps": 540.0, "ref_1pct_low": 360.0},

    # --- Counter-Strike 2 (Balanced Source 2 Engine) ---
    {"id": "VAL-15", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "CS2", "res": "1080p", "ref_avg_fps": 240.0, "ref_1pct_low": 155.0},
    {"id": "VAL-16", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "CS2", "res": "1440p", "ref_avg_fps": 275.0, "ref_1pct_low": 180.0},

    # --- Elden Ring (GPU-Heavy Cap/Load Profile) ---
    {"id": "VAL-17", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Elden Ring", "res": "1080p", "ref_avg_fps": 95.0, "ref_1pct_low": 76.0},
    {"id": "VAL-18", "cpu_id": "i5_12400F", "mobo_id": "b660m_ds3h", "gpu_id": "rtx_4060_twin", "cooler_id": "air_ag400", "case_id": "atx_mesh", "ram_id": "ddr4_16gb", "psu_id": "psu_550w", "storage_id": "ssd_500gb", "game": "Elden Ring", "res": "1440p", "ref_avg_fps": 68.0, "ref_1pct_low": 52.0},
    {"id": "VAL-19", "cpu_id": "ryzen_7800X3D", "mobo_id": "b650m_gaming_wifi", "gpu_id": "rtx_4070_dual", "cooler_id": "aio_240", "case_id": "atx_mesh", "ram_id": "ddr5_32gb", "psu_id": "psu_750w_msi_gl", "storage_id": "ssd_1tb", "game": "Elden Ring", "res": "1440p", "ref_avg_fps": 112.0, "ref_1pct_low": 88.0},
]


def run_comprehensive_evaluation():
    db: Session = SessionLocal()
    try:
        results = []
        actual_fps_list = []
        pred_fps_list = []

        abs_errors = []
        sq_errors = []
        pct_errors = []

        print("\n==========================================================================================")
        print("               ECOBUILD ACADEMIC BENCHMARK VALIDATION & RESIDUAL AUDIT                     ")
        print("==========================================================================================\n")

        for test in BENCHMARK_DATASET:
            cpu = db.query(models.CPU).filter(models.CPU.cpu_id == test["cpu_id"]).first()
            gpu = db.query(models.GPU).filter(models.GPU.gpu_id == test["gpu_id"]).first()
            cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == test["cooler_id"]).first()
            case = db.query(models.Case).filter(models.Case.case_id == test["case_id"]).first()
            ram = db.query(models.RAM).filter(models.RAM.ram_id == test["ram_id"]).first()

            if not all([cpu, gpu, cooler, case, ram]):
                missing = []
                if not cpu: missing.append(test["cpu_id"])
                if not gpu: missing.append(test["gpu_id"])
                if not cooler: missing.append(test["cooler_id"])
                if not case: missing.append(test["case_id"])
                if not ram: missing.append(test["ram_id"])
                print(f"[!] Skip {test['id']}: Missing in DB -> {', '.join(missing)}")
                continue

            vram = getattr(gpu, 'vram_gb', 8) or 8
            channels = getattr(ram, 'channels', 2) or 2

            sim = calculate_heuristic_performance(
                gpu_score=gpu.base_score,
                cpu_score=cpu.base_score,
                cpu_tdp=cpu.tdp_watts,
                gpu_tdp=gpu.tdp_watts,
                cooler_max_tdp=cooler.max_tdp,
                case_airflow_coef=float(case.airflow_coef),
                game_name=test["game"],
                resolution=test["res"],
                gpu_vram_gb=vram,
                ambient_temp=30.0,
                ram_channels=channels
            )

            actual_fps = test["ref_avg_fps"]
            pred_fps = float(sim["predicted_fps"])

            # Statistical residuals
            err = pred_fps - actual_fps
            abs_err = abs(err)
            sq_err = err ** 2
            ape = (abs_err / actual_fps) * 100.0

            actual_fps_list.append(actual_fps)
            pred_fps_list.append(pred_fps)
            abs_errors.append(abs_err)
            sq_errors.append(sq_err)
            pct_errors.append(ape)

            results.append({
                "id": test["id"],
                "hardware": f"{cpu.name[:16]} + {gpu.name[:18]}",
                "workload": f"{test['game']} ({test['res']})",
                "game": test["game"],
                "res": test["res"],
                "actual": actual_fps,
                "pred": pred_fps,
                "actual_1pct": test["ref_1pct_low"],
                "pred_1pct": sim["fps_1pct_low"],
                "error_fps": round(err, 1),
                "ape_pct": round(ape, 2)
            })

        n = len(actual_fps_list)
        if n == 0:
            print("[!] No benchmark cases could be evaluated. Did you run /seed?")
            return

        # --- COMPUTE PRIMARY STATISTICAL VALIDATION METRICS ---
        mae = statistics.mean(abs_errors)
        rmse = math.sqrt(statistics.mean(sq_errors))
        mape = statistics.mean(pct_errors)

        # R² (Coefficient of Determination) Calculation
        mean_actual = statistics.mean(actual_fps_list)
        ss_tot = sum((y - mean_actual) ** 2 for y in actual_fps_list)
        ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(actual_fps_list, pred_fps_list))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # --- TERMINAL REPORT ---
        print(f"| {'Test ID':<7} | {'Hardware Config':<36} | {'Game & Resolution':<22} | {'Ref':<6} | {'Pred':<6} | {'Diff':<6} | {'APE (%)':<8} |")
        print("|---------|--------------------------------------|------------------------|--------|--------|--------|----------|")
        for r in results:
            diff_str = f"{r['error_fps']:+0.1f}"
            print(f"| {r['id']:<7} | {r['hardware']:<36} | {r['workload']:<22} | {r['actual']:<6.0f} | {r['pred']:<6.0f} | {diff_str:<6} | {r['ape_pct']:<7.2f}% |")
        print("|---------|--------------------------------------|------------------------|--------|--------|--------|----------|\n")

        print("------------------------------------------------------------------------------------------")
        print("                      PRIMARY STATISTICAL VALIDATION METRICS                               ")
        print("------------------------------------------------------------------------------------------")
        print(f"  • Sample Size (N):                     {n} Configurations")
        print(f"  • Mean Absolute Error (MAE):           {mae:.2f} FPS")
        print(f"  • Root Mean Square Error (RMSE):       {rmse:.2f} FPS")
        print(f"  • Mean Absolute Percentage Error (MAPE): {mape:.2f}%")
        print(f"  • Coefficient of Determination (R²):   {r2:.4f}")
        print("------------------------------------------------------------------------------------------\n")

        # --- RESIDUAL ERROR ANALYSIS BY RESOLUTION ---
        print("--- RESIDUAL ANALYSIS GROUPED BY RESOLUTION ---")
        for res_name in ["1080p", "1440p", "4K"]:
            res_group = [r for r in results if r["res"] == res_name]
            if res_group:
                group_mape = statistics.mean(r["ape_pct"] for r in res_group)
                group_mae = statistics.mean(abs(r["error_fps"]) for r in res_group)
                mean_bias = statistics.mean(r["error_fps"] for r in res_group)
                bias_dir = "Over-predicting" if mean_bias > 0 else "Under-predicting"
                print(f"  [{res_name:<5}] N={len(res_group):<2} | MAE: {group_mae:<5.1f} FPS | MAPE: {group_mape:<5.2f}% | Bias: {mean_bias:+0.1f} FPS ({bias_dir})")

        # --- RESIDUAL ERROR ANALYSIS BY GAME TITLE ---
        print("\n--- RESIDUAL ANALYSIS GROUPED BY GAME ENGINE ---")
        for g_name in ["Cyberpunk 2077", "Valorant", "CS2", "Elden Ring"]:
            g_group = [r for r in results if r["game"] == g_name]
            if g_group:
                group_mape = statistics.mean(r["ape_pct"] for r in g_group)
                group_mae = statistics.mean(abs(r["error_fps"]) for r in g_group)
                mean_bias = statistics.mean(r["error_fps"] for r in g_group)
                print(f"  [{g_name:<14}] N={len(g_group):<2} | MAE: {group_mae:<5.1f} FPS | MAPE: {group_mape:<5.2f}% | Net Bias: {mean_bias:+0.1f} FPS")

        # --- AUTOMATED MARKDOWN & LATEX EXPORTERS FOR THESIS CHAPTER 4 ---
        _export_markdown_table(results, mae, rmse, mape, r2, n)
        _export_latex_table(results, mae, rmse, mape, r2, n)

    finally:
        db.close()


def _export_markdown_table(results, mae, rmse, mape, r2, n):
    output_path = os.path.join(os.path.dirname(__file__), "evaluation_report.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# EcoBuild Performance Prediction Model — Empirical Evaluation Report\n\n")
        f.write(f"**Date:** October 2026  \n")
        f.write(f"**Target System:** EcoBuild Heuristic Performance Engine (`real_engine.py`)  \n")
        f.write(f"**Primary Target Variable:** Average FPS (Frames Per Second)  \n\n")
        f.write("## 1. Summary of Statistical Accuracy Metrics\n\n")
        f.write(f"| Metric | Formula | Value | Academic Interpretation |\n")
        f.write(f"| :--- | :--- | :--- | :--- |\n")
        f.write(f"| **Mean Absolute Error (MAE)** | `(1/N) * Σ |y - ŷ|` | **{mae:.2f} FPS** | Average absolute distance from ground truth |\n")
        f.write(f"| **Root Mean Square Error (RMSE)** | `sqrt((1/N) * Σ (y - ŷ)²)` | **{rmse:.2f} FPS** | Penalizes large variance and outlier errors |\n")
        f.write(f"| **Mean Absolute Percentage Error (MAPE)** | `(1/N) * Σ |(y - ŷ)/y| * 100` | **{mape:.2f}%** | Percentage accuracy relative to benchmark |\n")
        f.write(f"| **Coefficient of Determination (R²)** | `1 - (SS_res / SS_tot)` | **{r2:.4f}** | Proportion of variance explained by model |\n\n")
        f.write("## 2. Experimental Validation Dataset & Prediction Matrix\n\n")
        f.write("| Test ID | Hardware Configuration | Workload Target | Reference FPS | Predicted FPS | Error (FPS) | APE (%) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            diff_str = f"{r['error_fps']:+0.1f}"
            f.write(f"| {r['id']} | {r['hardware']} | {r['workload']} | {r['actual']:.0f} | {r['pred']:.0f} | {diff_str} | {r['ape_pct']:.2f}% |\n")
    print(f"\n[Artifact] Saved Chapter 4 Markdown Report -> {output_path}")


def _export_latex_table(results, mae, rmse, mape, r2, n):
    output_path = os.path.join(os.path.dirname(__file__), "evaluation_table.tex")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("% ==========================================================================\n")
        f.write("% LATEX TABLE FOR CHAPTER 4 (PERFORMANCE EVALUATION RESULTS)\n")
        f.write("% ==========================================================================\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\small\n")
        f.write("\\caption{Empirical Validation of EcoBuild Heuristic FPS Prediction Engine against Published Reviewer Benchmarks}\n")
        f.write("\\label{tab:ecobuild_fps_evaluation}\n")
        f.write("\\begin{tabular}{llccccc}\n")
        f.write("\\hline\n")
        f.write("\\textbf{ID} & \\textbf{Game \\& Resolution} & \\textbf{Actual (FPS)} & \\textbf{Predicted (FPS)} & \\textbf{Diff} & \\textbf{APE (\\%)} \\\\\n")
        f.write("\\hline\n")
        for r in results:
            diff_str = f"{r['error_fps']:+0.1f}"
            clean_game = r['workload'].replace("&", "\\&")
            f.write(f"{r['id']} & {clean_game} & {r['actual']:.0f} & {r['pred']:.0f} & {diff_str} & {r['ape_pct']:.2f}\\% \\\\\n")
        f.write("\\hline\n")
        f.write(f"\\multicolumn{{6}}{{l}}{{\\textbf{{Overall Metrics:}} MAE = {mae:.2f} FPS, RMSE = {rmse:.2f} FPS, MAPE = {mape:.2f}\\%, $R^2$ = {r2:.4f}}} \\\\\n")
        f.write("\\hline\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")
    print(f"[Artifact] Saved Chapter 4 LaTeX Table     -> {output_path}\n")


if __name__ == "__main__":
    run_comprehensive_evaluation()
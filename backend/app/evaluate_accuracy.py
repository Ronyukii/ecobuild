"""
backend/app/evaluate_accuracy.py — Academic Performance Validation & Calibration Audit Suite.

Features:
- Dual-Mode Operation: Live PostgreSQL evaluation OR completely offline fixture evaluation (--offline).
- Distinct Dataset Roles: In-Sample Calibration Audit vs Independent Holdout Validation.
- Dual Metric Computation: Evaluates Average FPS and 1% Low FPS separately.
  - MAE  (Mean Absolute Error in FPS)
  - RMSE (Root Mean Square Error in FPS)
  - MAPE (Mean Absolute Percentage Error in %)
  - R²   (Coefficient of Determination)
- Residual Bias Analysis grouped by Game Engine and Resolution.
- Strict Integrity: Missing component IDs raise explicit errors rather than silent omission.
- Automated Export: Markdown report and LaTeX table for thesis documentation.
"""

import math
import os
import sys
import argparse
import statistics
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.real_engine import calculate_heuristic_performance, GAME_PROFILES

DATA_DIR = BACKEND_DIR / "data"
DEFAULT_CALIBRATION_DATASET = DATA_DIR / "calibration_dataset.json"
DEFAULT_HOLDOUT_DATASET = DATA_DIR / "validation_holdout_dataset.json"


def load_offline_catalogs(data_dir: Path = DATA_DIR) -> Dict[str, Dict[str, Any]]:
    """Loads catalog fixtures directly from JSON files without requiring a database."""
    catalogs = {}
    fixtures = {
        "cpus": ("cpus.json", "cpu_id"),
        "gpus": ("gpus.json", "gpu_id"),
        "cpu_models": ("cpu_models.json", "model_id"),
        "gpu_models": ("gpu_models.json", "model_id"),
        "coolers": ("coolers.json", "cooler_id"),
        "cases": ("cases.json", "case_id"),
        "rams": ("rams.json", "ram_id"),
    }
    for cat_name, (fname, id_key) in fixtures.items():
        fpath = data_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Required catalog fixture missing: {fpath}")
        with open(fpath, "r", encoding="utf-8") as f:
            items = json.load(f)
            catalogs[cat_name] = {item[id_key]: item for item in items}
    return catalogs


def _compute_regression_metrics(actual_list: List[float], pred_list: List[float]) -> Dict[str, float]:
    """Computes MAE, RMSE, MAPE, and R² for a paired set of actual and predicted values."""
    if not actual_list:
        return {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0, "n": 0}

    n = len(actual_list)
    abs_errors = [abs(p - a) for a, p in zip(actual_list, pred_list)]
    sq_errors = [(p - a) ** 2 for a, p in zip(actual_list, pred_list)]
    pct_errors = [(abs(p - a) / a) * 100.0 for a, p in zip(actual_list, pred_list)]

    mae = statistics.mean(abs_errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    mape = statistics.mean(pct_errors)

    mean_actual = statistics.mean(actual_list)
    ss_tot = sum((y - mean_actual) ** 2 for y in actual_list)
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(actual_list, pred_list))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "r2": round(r2, 4),
        "n": n
    }


def evaluate_dataset(
    dataset_path: Path = DEFAULT_CALIBRATION_DATASET,
    offline: bool = True,
    db: Any = None,
    data_dir: Path = DATA_DIR
) -> Dict[str, Any]:
    """
    Evaluates a benchmark dataset (calibration or holdout) against the prediction engine.
    Computes separate metrics for Average FPS and 1% Low FPS.
    Raises ValueError if any referenced hardware ID is missing from the catalog.
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Benchmark dataset file not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)

    if not benchmarks:
        return {
            "dataset_path": str(dataset_path),
            "sample_size": 0,
            "status": "EMPTY",
            "message": "Dataset is empty (0 records).",
            "avg_metrics": _compute_regression_metrics([], []),
            "low_metrics": _compute_regression_metrics([], []),
            "cases": []
        }

    # Load hardware catalog either offline or from SQLAlchemy DB
    catalogs = None
    if offline or db is None:
        catalogs = load_offline_catalogs(data_dir)

    results = []
    actual_avg_list = []
    pred_avg_list = []
    actual_low_list = []
    pred_low_list = []

    for test in benchmarks:
        cid = test["id"]
        cpu_id = test["cpu_id"]
        gpu_id = test["gpu_id"]
        env = test.get("test_environment", {}) or {}
        cooler_id = env.get("cooler_id")
        case_id = env.get("case_id")
        ram_id = env.get("ram_id")

        if catalogs is not None:
            # Offline catalog resolution
            missing = []
            cpu = catalogs["cpus"].get(cpu_id) or catalogs["cpu_models"].get(cpu_id)
            gpu = catalogs["gpus"].get(gpu_id) or catalogs["gpu_models"].get(gpu_id)

            if not cpu: missing.append(f"CPU '{cpu_id}'")
            if not gpu: missing.append(f"GPU '{gpu_id}'")
            if cooler_id and cooler_id not in catalogs["coolers"]: missing.append(f"Cooler '{cooler_id}'")
            if case_id and case_id not in catalogs["cases"]: missing.append(f"Case '{case_id}'")
            if ram_id and ram_id not in catalogs["rams"]: missing.append(f"RAM '{ram_id}'")

            if missing:
                raise ValueError(
                    f"Integrity check failed: Benchmark record {cid} references missing hardware in catalog fixtures: {', '.join(missing)}"
                )

            cooler = catalogs["coolers"].get(cooler_id, {"max_tdp": 220})
            case = catalogs["cases"].get(case_id, {"airflow_coef": 1.0})
            ram = catalogs["rams"].get(ram_id, {"channels": 2})

            cpu_name = cpu["name"]
            gpu_name = gpu["name"]

            # Resolve canonical baseline performance score to eliminate factory OC distortions
            gpu_model_id = gpu.get("model_id")
            if gpu_model_id and "gpu_models" in catalogs and gpu_model_id in catalogs["gpu_models"]:
                gpu_score = catalogs["gpu_models"][gpu_model_id]["base_score"]
            else:
                gpu_score = gpu["base_score"]

            cpu_model_id = cpu.get("model_id")
            if cpu_model_id and "cpu_models" in catalogs and cpu_model_id in catalogs["cpu_models"]:
                cpu_score = catalogs["cpu_models"][cpu_model_id]["base_score"]
            else:
                cpu_score = cpu["base_score"]

            cpu_tdp = cpu["tdp_watts"]
            gpu_tdp = gpu["tdp_watts"]
            cooler_max_tdp = cooler.get("max_tdp", 220)
            case_airflow_coef = float(case.get("airflow_coef", 1.0))
            gpu_vram = gpu.get("vram_gb", 8) or 8
            ram_channels = env.get("ram_channels") or ram.get("channels", 2) or 2
        else:
            # Live database query resolution
            from . import models
            cpu = db.query(models.CPU).filter(models.CPU.cpu_id == cpu_id).first()
            if not cpu:
                cpu = db.query(models.CPUModel).filter(models.CPUModel.model_id == cpu_id).first()
            gpu = db.query(models.GPU).filter(models.GPU.gpu_id == gpu_id).first()
            if not gpu:
                gpu = db.query(models.GPUModel).filter(models.GPUModel.model_id == gpu_id).first()
            cooler = db.query(models.Cooler).filter(models.Cooler.cooler_id == cooler_id).first() if cooler_id else None
            case = db.query(models.Case).filter(models.Case.case_id == case_id).first() if case_id else None
            ram = db.query(models.RAM).filter(models.RAM.ram_id == ram_id).first() if ram_id else None

            missing = []
            if not cpu: missing.append(f"CPU '{cpu_id}'")
            if not gpu: missing.append(f"GPU '{gpu_id}'")
            if cooler_id and not cooler: missing.append(f"Cooler '{cooler_id}'")
            if case_id and not case: missing.append(f"Case '{case_id}'")
            if ram_id and not ram: missing.append(f"RAM '{ram_id}'")

            if missing:
                raise ValueError(
                    f"Integrity check failed: Benchmark record {cid} references missing hardware in database: {', '.join(missing)}"
                )

            cpu_name = cpu.name
            gpu_name = gpu.name

            # Resolve canonical baseline performance score
            gpu_model_id = getattr(gpu, "model_id", None)
            if gpu_model_id:
                c_model = db.query(models.GPUModel).filter(models.GPUModel.model_id == gpu_model_id).first()
                gpu_score = c_model.base_score if c_model and c_model.base_score else gpu.base_score
            else:
                gpu_score = gpu.base_score

            cpu_model_id = getattr(cpu, "model_id", None)
            if cpu_model_id:
                c_model = db.query(models.CPUModel).filter(models.CPUModel.model_id == cpu_model_id).first()
                cpu_score = c_model.base_score if c_model and c_model.base_score else cpu.base_score
            else:
                cpu_score = cpu.base_score

            cpu_tdp = cpu.tdp_watts
            gpu_tdp = gpu.tdp_watts
            cooler_max_tdp = cooler.max_tdp if cooler else 220
            case_airflow_coef = float(case.airflow_coef) if case else 1.0
            gpu_vram = getattr(gpu, 'vram_gb', 8) or 8
            ram_channels = env.get("ram_channels") or getattr(ram, 'channels', 2) or 2

        ambient = float(env.get("ambient_temp_c") or 30.0)

        sim = calculate_heuristic_performance(
            gpu_score=gpu_score,
            cpu_score=cpu_score,
            cpu_tdp=cpu_tdp,
            gpu_tdp=gpu_tdp,
            cooler_max_tdp=cooler_max_tdp,
            case_airflow_coef=case_airflow_coef,
            game_name=test["game_name"],
            resolution=test["resolution"],
            gpu_vram_gb=gpu_vram,
            ambient_temp=ambient,
            ram_channels=ram_channels
        )

        actual_avg = float(test["ref_avg_fps"])
        pred_avg = float(sim["predicted_fps"])
        err_avg = pred_avg - actual_avg
        ape_avg = (abs(err_avg) / actual_avg) * 100.0

        actual_avg_list.append(actual_avg)
        pred_avg_list.append(pred_avg)

        actual_low = test.get("ref_1pct_low")
        pred_low = float(sim["fps_1pct_low"])
        err_low = None
        ape_low = None

        if actual_low is not None:
            actual_low = float(actual_low)
            err_low = pred_low - actual_low
            ape_low = (abs(err_low) / actual_low) * 100.0
            actual_low_list.append(actual_low)
            pred_low_list.append(pred_low)

        prov = test.get("provenance", {}) or {}
        results.append({
            "id": cid,
            "dataset_role": test.get("dataset_role", "calibration_in_sample"),
            "hardware": f"{cpu_name[:16]} + {gpu_name[:18]}",
            "cpu_id": cpu_id,
            "gpu_id": gpu_id,
            "game": test["game_name"],
            "res": test["resolution"],
            "actual_avg": actual_avg,
            "pred_avg": pred_avg,
            "error_avg_fps": round(err_avg, 1),
            "ape_avg_pct": round(ape_avg, 2),
            "actual_1pct": actual_low,
            "pred_1pct": pred_low,
            "error_1pct_fps": round(err_low, 1) if err_low is not None else None,
            "ape_1pct_pct": round(ape_low, 2) if ape_low is not None else None,
            "source_title": prov.get("source_title", "Unknown"),
            "eligibility": prov.get("eligibility", "unverified"),
            "notes": prov.get("notes")
        })

    avg_metrics = _compute_regression_metrics(actual_avg_list, pred_avg_list)
    low_metrics = _compute_regression_metrics(actual_low_list, pred_low_list)

    # Resolution Breakdown
    by_res = {}
    for res_name in ["1080p", "1440p", "4K"]:
        group = [r for r in results if r["res"] == res_name]
        if group:
            by_res[res_name] = {
                "count": len(group),
                "avg_fps": {
                    "mae": round(statistics.mean(abs(r["error_avg_fps"]) for r in group), 2),
                    "mape": round(statistics.mean(r["ape_avg_pct"] for r in group), 2),
                    "bias": round(statistics.mean(r["error_avg_fps"] for r in group), 2)
                },
                "low_fps": {
                    "mae": round(statistics.mean(abs(r["error_1pct_fps"]) for r in group if r["error_1pct_fps"] is not None), 2) if any(r["error_1pct_fps"] is not None for r in group) else None,
                    "mape": round(statistics.mean(r["ape_1pct_pct"] for r in group if r["ape_1pct_pct"] is not None), 2) if any(r["ape_1pct_pct"] is not None for r in group) else None
                }
            }

    # Game Title Breakdown
    by_game = {}
    for game_name in sorted(list(set(r["game"] for r in results))):
        group = [r for r in results if r["game"] == game_name]
        by_game[game_name] = {
            "count": len(group),
            "engine_type": "GPU-Bound AAA" if game_name in ["Cyberpunk 2077", "Elden Ring"] else "CPU-Bound Esports",
            "avg_fps": {
                "mae": round(statistics.mean(abs(r["error_avg_fps"]) for r in group), 2),
                "mape": round(statistics.mean(r["ape_avg_pct"] for r in group), 2),
                "bias": round(statistics.mean(r["error_avg_fps"] for r in group), 2)
            },
            "low_fps": {
                "mae": round(statistics.mean(abs(r["error_1pct_fps"]) for r in group if r["error_1pct_fps"] is not None), 2) if any(r["error_1pct_fps"] is not None for r in group) else None,
                "mape": round(statistics.mean(r["ape_1pct_pct"] for r in group if r["ape_1pct_pct"] is not None), 2) if any(r["ape_1pct_pct"] is not None for r in group) else None
            }
        }

    return {
        "dataset_path": str(dataset_path),
        "dataset_role": benchmarks[0].get("dataset_role", "calibration_in_sample"),
        "sample_size": len(results),
        "avg_metrics": avg_metrics,
        "low_metrics": low_metrics,
        "by_resolution": by_res,
        "by_game": by_game,
        "cases": results
    }


def print_evaluation_summary(eval_res: Dict[str, Any]):
    """Prints a structured academic evaluation table to standard output."""
    role = eval_res.get("dataset_role", "calibration_in_sample")
    n = eval_res.get("sample_size", 0)

    print("\n==========================================================================================")
    print("                  ECOBUILD PERFORMANCE ENGINE CALIBRATION & EVALUATION AUDIT              ")
    print("==========================================================================================")
    print(f" Dataset Role:        {role.upper()} ({n} cases)")
    print(f" Source File:         {eval_res.get('dataset_path')}")
    print(" Independent Holdout: PENDING — 0 eligible holdout cases currently approved.")
    print(" Thermal Model:       LETM (Uncalibrated Analytical Heuristic — physical thermocouples pending)")
    print("==========================================================================================\n")

    if n == 0:
        print("[!] Dataset contains 0 cases. No metrics computed.\n")
        return

    results = eval_res["cases"]
    print(f"| {'ID':<7} | {'Hardware Config':<34} | {'Workload':<20} | {'Avg Ref':<7} | {'Avg Pred':<8} | {'Diff':<6} | {'APE':<7} | {'1% Ref':<6} | {'1% Pred':<7} |")
    print("|---------|------------------------------------|----------------------|---------|----------|--------|---------|--------|---------|")
    for r in results:
        diff_str = f"{r['error_avg_fps']:+0.1f}"
        low_ref_str = f"{r['actual_1pct']:.0f}" if r['actual_1pct'] is not None else "--"
        low_pred_str = f"{r['pred_1pct']:.0f}"
        workload = f"{r['game']} ({r['res']})"
        print(f"| {r['id']:<7} | {r['hardware']:<34} | {workload:<20} | {r['actual_avg']:<7.0f} | {r['pred_avg']:<8.0f} | {diff_str:<6} | {r['ape_avg_pct']:<6.2f}% | {low_ref_str:<6} | {low_pred_str:<7} |")
    print("|---------|------------------------------------|----------------------|---------|----------|--------|---------|--------|---------|\n")

    avg_m = eval_res["avg_metrics"]
    low_m = eval_res["low_metrics"]

    print("------------------------------------------------------------------------------------------")
    print("                      PRIMARY STATISTICAL ACCURACY METRICS                                ")
    print("------------------------------------------------------------------------------------------")
    print(f"  • Sample Size:                         {n} Configurations")
    print(f"  • Average FPS — MAE:                   {avg_m['mae']:.2f} FPS")
    print(f"  • Average FPS — RMSE:                  {avg_m['rmse']:.2f} FPS")
    print(f"  • Average FPS — MAPE:                  {avg_m['mape']:.2f}%")
    print(f"  • Average FPS — R²:                    {avg_m['r2']:.4f}")
    print("  ----------------------------------------------------------------------------------------")
    print(f"  • 1% Low FPS  — MAE:                   {low_m['mae']:.2f} FPS")
    print(f"  • 1% Low FPS  — RMSE:                  {low_m['rmse']:.2f} FPS")
    print(f"  • 1% Low FPS  — MAPE:                  {low_m['mape']:.2f}%")
    print(f"  • 1% Low FPS  — R²:                    {low_m['r2']:.4f}")
    print("------------------------------------------------------------------------------------------\n")

    print("--- RESIDUAL ANALYSIS BY RESOLUTION (AVERAGE FPS) ---")
    for res_name, data in eval_res["by_resolution"].items():
        m = data["avg_fps"]
        bias_dir = "Over-predicting" if m["bias"] > 0 else "Under-predicting"
        print(f"  [{res_name:<5}] N={data['count']:<2} | MAE: {m['mae']:<5.1f} FPS | MAPE: {m['mape']:<5.2f}% | Bias: {m['bias']:+0.1f} FPS ({bias_dir})")

    print("\n--- RESIDUAL ANALYSIS BY GAME ENGINE (AVERAGE FPS) ---")
    for g_name, data in eval_res["by_game"].items():
        m = data["avg_fps"]
        print(f"  [{g_name:<14}] N={data['count']:<2} | MAE: {m['mae']:<5.1f} FPS | MAPE: {m['mape']:<5.2f}% | Net Bias: {m['bias']:+0.1f} FPS")
    print()


def export_calibration_artifacts(eval_res: Dict[str, Any], output_dir: Path = DATA_DIR):
    """Exports calibration_report.md and calibration_table.tex for thesis documentation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "calibration_report.md"
    tex_path = output_dir / "calibration_table.tex"

    avg_m = eval_res["avg_metrics"]
    low_m = eval_res["low_metrics"]
    cases = eval_res["cases"]
    n = eval_res["sample_size"]

    # 1. Export Markdown Report
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# EcoBuild Prediction Engine — In-Sample Model Calibration Report\n\n")
        f.write(f"**Date:** {datetime.now(timezone.utc).strftime('%B %Y')}  \n")
        f.write(f"**Dataset Role:** In-Sample Calibration Dataset (Internal Parameter Tuning)  \n")
        f.write(f"**Target System:** EcoBuild Heuristic Performance Engine (`real_engine.py`)  \n")
        f.write(f"**Sample Size:** {n} In-Sample Test Benches  \n\n")
        f.write("> **Academic Integrity Disclosure:**  \n")
        f.write("> These 19 benchmark records were used during internal parameter tuning. They demonstrate  \n")
        f.write("> calibration convergence of the dual-pipeline frame-time arbitration engine. Independent  \n")
        f.write("> out-of-sample holdout validation remains **PENDING** until eligible external datasets are approved.\n\n")

        f.write("## 1. Summary of Statistical Accuracy Metrics\n\n")
        f.write("| Metric | Average FPS | 1% Low FPS | Mathematical Formula | Academic Interpretation |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        f.write(f"| **Mean Absolute Error (MAE)** | **{avg_m['mae']:.2f} FPS** | **{low_m['mae']:.2f} FPS** | `(1/N) * Σ |y - ŷ|` | Mean absolute error distance |\n")
        f.write(f"| **Root Mean Square Error (RMSE)** | **{avg_m['rmse']:.2f} FPS** | **{low_m['rmse']:.2f} FPS** | `sqrt((1/N) * Σ (y - ŷ)²)` | Penalizes large outlier deviations |\n")
        f.write(f"| **Mean Absolute Percentage Error (MAPE)** | **{avg_m['mape']:.2f}%** | **{low_m['mape']:.2f}%** | `(1/N) * Σ |(y - ŷ)/y| * 100` | Percentage error relative to ground truth |\n")
        f.write(f"| **Coefficient of Determination (R²)** | **{avg_m['r2']:.4f}** | **{low_m['r2']:.4f}** | `1 - (SS_res / SS_tot)` | Proportion of total variance explained |\n\n")

        f.write("## 2. In-Sample Calibration Record Matrix\n\n")
        f.write("| Test ID | Hardware Configuration | Workload Target | Ref Avg | Pred Avg | Diff | APE (%) | Ref 1% | Pred 1% | Source / Provenance |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in cases:
            diff_str = f"{r['error_avg_fps']:+0.1f}"
            low_ref_str = f"{r['actual_1pct']:.0f}" if r['actual_1pct'] is not None else "--"
            low_pred_str = f"{r['pred_1pct']:.0f}"
            workload = f"{r['game']} ({r['res']})"
            f.write(f"| {r['id']} | {r['hardware']} | {workload} | {r['actual_avg']:.0f} | {r['pred_avg']:.0f} | {diff_str} | {r['ape_avg_pct']:.2f}% | {low_ref_str} | {low_pred_str} | {r['source_title']} |\n")

    # 2. Export LaTeX Table
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("% ==========================================================================\n")
        f.write("% LATEX TABLE: IN-SAMPLE CALIBRATION ACCURACY METRICS (CHAPTER 4)\n")
        f.write("% ==========================================================================\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\small\n")
        f.write("\\caption{In-Sample Model Calibration of EcoBuild Heuristic Engine against Reviewer Configurations}\n")
        f.write("\\label{tab:ecobuild_calibration_audit}\n")
        f.write("\\begin{tabular}{llccccc}\n")
        f.write("\\hline\n")
        f.write("\\textbf{ID} & \\textbf{Game \\& Resolution} & \\textbf{Ref Avg} & \\textbf{Pred Avg} & \\textbf{Diff} & \\textbf{APE (\\%)} & \\textbf{1\\% Low (Ref/Pred)} \\\\\n")
        f.write("\\hline\n")
        for r in cases:
            diff_str = f"{r['error_avg_fps']:+0.1f}"
            clean_game = f"{r['game']} ({r['res']})".replace("&", "\\&")
            low_ref_str = f"{r['actual_1pct']:.0f}" if r['actual_1pct'] is not None else "--"
            low_str = f"{low_ref_str}/{r['pred_1pct']:.0f}"
            f.write(f"{r['id']} & {clean_game} & {r['actual_avg']:.0f} & {r['pred_avg']:.0f} & {diff_str} & {r['ape_avg_pct']:.2f}\\% & {low_str} \\\\\n")
        f.write("\\hline\n")
        f.write(f"\\multicolumn{{7}}{{l}}{{\\textbf{{Average FPS:}} MAE = {avg_m['mae']:.2f} FPS, RMSE = {avg_m['rmse']:.2f} FPS, MAPE = {avg_m['mape']:.2f}\\%, $R^2$ = {avg_m['r2']:.4f}}} \\\\\n")
        f.write(f"\\multicolumn{{7}}{{l}}{{\\textbf{{1\\% Low FPS:}}  MAE = {low_m['mae']:.2f} FPS, RMSE = {low_m['rmse']:.2f} FPS, MAPE = {low_m['mape']:.2f}\\%, $R^2$ = {low_m['r2']:.4f}}} \\\\\n")
        f.write("\\hline\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    print(f"[Artifact] Saved Markdown Calibration Report -> {md_path}")
    print(f"[Artifact] Saved LaTeX Calibration Table     -> {tex_path}\n")


def evaluate_and_export_results(
    db: Any = None,
    offline: bool = False,
    dataset_path: Path = DEFAULT_CALIBRATION_DATASET
) -> Optional[Dict[str, Any]]:
    """
    Evaluates the dataset and exports backend/data/evaluation_results.json.
    Callable by the FastAPI /evaluation/metrics route or standalone.
    Falls back gracefully to offline mode if database is unavailable.
    """
    try:
        if not offline and db is None:
            from .database import SessionLocal
            db = SessionLocal()
            eval_res = evaluate_dataset(dataset_path=dataset_path, offline=False, db=db)
            db.close()
        else:
            eval_res = evaluate_dataset(dataset_path=dataset_path, offline=True)
    except Exception as e:
        print(f"[Evaluator] Live database connection skipped ({e}). Falling back to offline fixtures.")
        eval_res = evaluate_dataset(dataset_path=dataset_path, offline=True)

    if eval_res["sample_size"] == 0:
        return None

    avg_m = eval_res["avg_metrics"]
    low_m = eval_res["low_metrics"]
    cases = eval_res["cases"]

    negative_bias = sum(1 for r in cases if r["error_avg_fps"] < 0)
    positive_bias = sum(1 for r in cases if r["error_avg_fps"] > 0)

    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_size": eval_res["sample_size"],
            "engine_version": "2.1 (Decoupled Frame-Time Pipeline)",
            "dataset_role": "calibration_in_sample",
            "evaluation_mode": "offline" if offline or db is None else "database"
        },
        "metrics": {
            "average_fps": {
                "mae": avg_m["mae"],
                "rmse": avg_m["rmse"],
                "mape": avg_m["mape"],
                "r2": avg_m["r2"]
            },
            "fps_1pct_low": {
                "mae": low_m["mae"],
                "rmse": low_m["rmse"],
                "mape": low_m["mape"],
                "r2": low_m["r2"]
            },
            "residual_distribution": {
                "negative_underpredictions": negative_bias,
                "positive_overpredictions": positive_bias,
                "balanced_status": f"{negative_bias} Under / {positive_bias} Over"
            }
        },
        "by_game_engine": eval_res["by_game"],
        "by_resolution": eval_res["by_resolution"],
        "cases": cases,
        "disclosures": {
            "calibration_scope": (
                f"These {eval_res['sample_size']} benchmark configurations were used to calibrate the dual-pipeline "
                "engine exponents. While they demonstrate calibration convergence, an unseen independent holdout "
                "dataset will be evaluated separately once eligible evidence is verified."
            ),
            "holdout_status": "PENDING — 0 eligible independent holdout cases available.",
            "thermal_status": (
                "Thermal results are computed using an analytical Lumped-Element Thermal Model (LETM) "
                "at 30°C tropical ambient. These values represent a theoretical engineering heuristic and "
                "have NOT been empirically calibrated against physical laboratory thermocouples."
            )
        }
    }

    output_file = DATA_DIR / "evaluation_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    export_calibration_artifacts(eval_res, output_dir=DATA_DIR)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EcoBuild Performance Engine Evaluation Suite")
    parser.add_argument("--offline", action="store_true", default=True, help="Run evaluation offline using JSON fixtures without PostgreSQL")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_CALIBRATION_DATASET, help="Path to benchmark JSON dataset")
    args = parser.parse_args()

    eval_result = evaluate_dataset(dataset_path=args.dataset, offline=args.offline)
    print_evaluation_summary(eval_result)
    export_calibration_artifacts(eval_result)

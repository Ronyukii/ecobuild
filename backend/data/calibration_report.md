# EcoBuild Prediction Engine — In-Sample Model Calibration Report

**Date:** November 2026  
**Dataset Role:** In-Sample Calibration Dataset (Internal Parameter Tuning)  
**Target System:** EcoBuild Heuristic Performance Engine (`real_engine.py`)  
**Sample Size:** 19 In-Sample Test Benches  

> **Academic Integrity Disclosure:**  
> These 19 benchmark records were used during internal parameter tuning. They demonstrate  
> calibration convergence of the dual-pipeline frame-time arbitration engine. Independent  
> out-of-sample holdout validation remains **PENDING** until eligible external datasets are approved.

## 1. Summary of Statistical Accuracy Metrics

| Metric | Average FPS | 1% Low FPS | Mathematical Formula | Academic Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| **Mean Absolute Error (MAE)** | **30.32 FPS** | **33.84 FPS** | `(1/N) * Σ |y - ŷ|` | Mean absolute error distance |
| **Root Mean Square Error (RMSE)** | **50.40 FPS** | **59.62 FPS** | `sqrt((1/N) * Σ (y - ŷ)²)` | Penalizes large outlier deviations |
| **Mean Absolute Percentage Error (MAPE)** | **11.56%** | **17.54%** | `(1/N) * Σ |(y - ŷ)/y| * 100` | Percentage error relative to ground truth |
| **Coefficient of Determination (R²)** | **0.9053** | **0.6703** | `1 - (SS_res / SS_tot)` | Proportion of total variance explained |

## 2. In-Sample Calibration Record Matrix

| Test ID | Hardware Configuration | Workload Target | Ref Avg | Pred Avg | Diff | APE (%) | Ref 1% | Pred 1% | Source / Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-01 | Intel Core i5-12 + Zotac Gaming RTX 4 | Cyberpunk 2077 (1080p) | 72 | 71 | -1.0 | 1.39% | 58 | 57 | Hardware Unboxed |
| VAL-02 | Intel Core i5-12 + Zotac Gaming RTX 4 | Cyberpunk 2077 (1440p) | 48 | 49 | +1.0 | 2.08% | 37 | 30 | Hardware Unboxed |
| VAL-03 | AMD Ryzen 5 5600 + Sapphire Pulse RX  | Cyberpunk 2077 (1080p) | 54 | 57 | +3.0 | 5.56% | 42 | 46 | TechPowerUp |
| VAL-04 | Intel Core i3-12 + Palit RTX 3060 12G | Cyberpunk 2077 (1080p) | 58 | 60 | +2.0 | 3.45% | 45 | 48 | TechPowerUp |
| VAL-05 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Cyberpunk 2077 (1080p) | 118 | 111 | -7.0 | 5.93% | 94 | 89 | Internal Calibration Anchor |
| VAL-06 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Cyberpunk 2077 (1440p) | 84 | 88 | +4.0 | 4.76% | 68 | 71 | Internal Calibration Anchor |
| VAL-07 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Cyberpunk 2077 (4K) | 41 | 51 | +10.0 | 24.39% | 32 | 33 | Internal Calibration Anchor |
| VAL-08 | Intel Core i7-13 + Gigabyte RTX 4080  | Cyberpunk 2077 (1440p) | 132 | 117 | -15.0 | 11.36% | 105 | 93 | Gamers Nexus |
| VAL-09 | Intel Core i7-13 + Gigabyte RTX 4080  | Cyberpunk 2077 (4K) | 68 | 76 | +8.0 | 11.76% | 54 | 60 | Gamers Nexus |
| VAL-10 | Intel Core i5-12 + Zotac Gaming RTX 4 | Valorant (1080p) | 380 | 275 | -105.0 | 27.63% | 240 | 116 | Hardware Unboxed |
| VAL-11 | Intel Core i3-12 + Zotac Gaming RTX 4 | Valorant (1080p) | 290 | 221 | -69.0 | 23.79% | 175 | 66 | Hardware Unboxed |
| VAL-12 | AMD Ryzen 5 5600 + Sapphire Pulse RX  | Valorant (1080p) | 340 | 294 | -46.0 | 13.53% | 210 | 187 | TechPowerUp |
| VAL-13 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Valorant (1080p) | 580 | 450 | -130.0 | 22.41% | 390 | 226 | Internal Calibration Anchor |
| VAL-14 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Valorant (1440p) | 540 | 450 | -90.0 | 16.67% | 360 | 273 | Internal Calibration Anchor |
| VAL-15 | Intel Core i5-12 + Zotac Gaming RTX 4 | CS2 (1080p) | 240 | 171 | -69.0 | 28.75% | 155 | 86 | Gamers Nexus |
| VAL-16 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | CS2 (1440p) | 275 | 274 | -1.0 | 0.36% | 180 | 192 | Internal Calibration Anchor |
| VAL-17 | Intel Core i5-12 + Zotac Gaming RTX 4 | Elden Ring (1080p) | 95 | 84 | -11.0 | 11.58% | 76 | 67 | Hardware Unboxed |
| VAL-18 | Intel Core i5-12 + Zotac Gaming RTX 4 | Elden Ring (1440p) | 68 | 67 | -1.0 | 1.47% | 52 | 55 | Hardware Unboxed |
| VAL-19 | AMD Ryzen 7 7800 + GeForce RTX 4070 1 | Elden Ring (1440p) | 112 | 109 | -3.0 | 2.68% | 88 | 89 | Internal Calibration Anchor |

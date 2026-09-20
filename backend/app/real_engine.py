import math

# ---------------------------------------------------------------------------
# 1. REFERENCE DATA & ANCHORS
# ---------------------------------------------------------------------------

# Resolution scaling relative to 1080p baseline.
RESOLUTION_SCALE = {
    "1080p": 1.00,
    "1440p": 0.72,   # ~28% FPS drop vs 1080p
    "4K": 0.45,      # ~55% FPS drop vs 1080p
}

# The anchor GPU against which all other GPUs are scaled.
# We use the RTX 4070 as our Ground Truth Anchor (TimeSpy Score: ~18000)
REFERENCE_GPU_SCORE = 18000 

# Reference FPS anchors: known, verified empirical FPS for a specific game 
# using the Reference GPU (RTX 4070) at 1080p.
GAME_REFERENCE = {
    "Cyberpunk 2077": {
        "reference_fps": 82,          # RTX 4070 @ 1080p Ultra
        "complexity_index": 1.00,
    },
    "CS2": {
        "reference_fps": 380,         # RTX 4070 @ 1080p High
        "complexity_index": 1.00,
    },
    "Valorant": {
        "reference_fps": 450,         # RTX 4070 @ 1080p High
        "complexity_index": 1.00,
    },
    "Elden Ring": {
        "reference_fps": 115,         # RTX 4070 @ 1080p Max (Uncapped)
        "complexity_index": 1.00,
    }
}

# ---------------------------------------------------------------------------
# 2. CORE PREDICTION LOGIC
# ---------------------------------------------------------------------------

def calculate_heuristic_performance(
    gpu_score: int, cpu_score: int, cpu_tdp: int, 
    cooler_max_tdp: int, case_airflow_coef: float, 
    game_name: str, resolution: str, ambient_temp: float = 30.0
):
    """
    Implements the benchmark-anchored heuristic regression logic.
    """
    
    # --- 1. Fetch Game Anchors ---
    game = GAME_REFERENCE.get(game_name, GAME_REFERENCE["Cyberpunk 2077"])
    
    # --- 2. Relative GPU Scaling ---
    gpu_ratio = gpu_score / REFERENCE_GPU_SCORE
    res_scale = RESOLUTION_SCALE.get(resolution, 1.00)
    
    predicted_fps = game["reference_fps"] * gpu_ratio * res_scale * game["complexity_index"]

    # --- 3. CPU Bottleneck Correction ---
    # Dynamic Threshold: A faster GPU requires a proportionally faster CPU to feed it
    cpu_threshold_for_gpu = gpu_score * 1.35  # Empirical modifier for 1080p bottlenecking
    
    cpu_ratio = min(1.0, cpu_score / cpu_threshold_for_gpu)
    bottleneck_detected = cpu_ratio < 1.0
    bottleneck_severity_pct = round((1 - cpu_ratio) * 100, 1)

    final_fps = predicted_fps * cpu_ratio

    # --- 4. Thermal Dynamics & Throttling Penalty ---
    thermal_load = (cpu_tdp / float(cooler_max_tdp)) / float(case_airflow_coef)
    predicted_temp = ambient_temp + (thermal_load * 35.0)

    thermal_status = "Stable"
    thermal_penalty_applied = False

    if predicted_temp > 90.0:
        thermal_status = "THROTTLING"
        thermal_penalty_applied = True
        final_fps *= 0.85  # 15% thermal throttling penalty
    elif predicted_temp > 78.0:
        thermal_status = "High Load"

    return {
        "predicted_fps": round(final_fps),
        "predicted_temp_c": round(predicted_temp, 1),
        "thermal_status": thermal_status,
        "bottleneck_detected": bottleneck_detected,
        "bottleneck_severity_pct": bottleneck_severity_pct,
        "thermal_penalty_applied": thermal_penalty_applied
    }

# ---------------------------------------------------------------------------
# 3. GROUND-UP FIRST-PRINCIPLES PERFORMANCE MODEL
# ---------------------------------------------------------------------------

def calculate_ground_up_performance(
    gpu_cores: int, gpu_clock_mhz: int,
    gpu_bus_bit: int, gpu_speed_gbps: float,
    cpu_ipc: float, cpu_boost_ghz: float, cpu_l3_cache_mb: int, cpu_tdp: int,
    cooler_max_tdp: int, case_airflow_coef: float,
    ram_speed_mts: int, game_name: str, resolution: str
):
    """
    Computes theoretical FPS from first-principles architectural physics:
    TFLOPs, memory bandwidth, IPC throughput, and memory latency.
    """
    # 1. GPU Compute Power (Single-Precision FP32 TFLOPs)
    # Formula: (2 * Cores * Clock_MHz) / 1,000,000
    gpu_tflops = (2 * gpu_cores * gpu_clock_mhz) / 1_000_000.0

    # 2. GPU Memory Bandwidth (GB/s)
    # Formula: (Bus_Width_Bits * Transfer_Rate_Gbps) / 8
    gpu_bandwidth_gbs = (gpu_bus_bit * gpu_speed_gbps) / 8.0

    # Composite theoretical GPU index
    raw_gpu_index = (gpu_tflops * 0.75) + ((gpu_bandwidth_gbs / 30.0) * 0.25)

    # 3. CPU Throughput & Cache Index
    cpu_index = (cpu_ipc * cpu_boost_ghz * 8.5) + (cpu_l3_cache_mb * 0.20) + (ram_speed_mts / 2000.0)

    # 4. Target Game Complexity Weight
    game_scalar = {
        "Cyberpunk 2077": 5.4,
        "CS2": 24.5,
        "Valorant": 28.0,
        "Elden Ring": 7.8
    }.get(game_name, 6.0)

    res_scale = RESOLUTION_SCALE.get(resolution, 1.00)

    # 5. Base framerate from raw architectural hardware
    theoretical_fps = raw_gpu_index * game_scalar * res_scale

    # 6. Pipeline Feed Bottleneck Ratio
    required_cpu = raw_gpu_index * 1.65
    pipeline_feed_ratio = min(1.0, cpu_index / required_cpu)
    throttled_fps = theoretical_fps * (0.65 + 0.35 * pipeline_feed_ratio)

    # 7. Thermal Dissipation Penalty
    thermal_load = (cpu_tdp / float(cooler_max_tdp)) / float(case_airflow_coef)
    predicted_temp = 30.0 + (thermal_load * 35.0)
    thermal_penalty = 0.85 if predicted_temp > 90.0 else 1.0

    final_fps = throttled_fps * thermal_penalty

    return {
        "ground_up_fps": round(final_fps),
        "theoretical_tflops": round(gpu_tflops, 2),
        "memory_bandwidth_gbs": round(gpu_bandwidth_gbs, 1),
        "predicted_temp_c": round(predicted_temp, 1)
    }
import math

# ---------------------------------------------------------------------------
# 1. EMPIRICAL REFERENCE ANCHORS & ENGINE PROFILES
# ---------------------------------------------------------------------------

# Ground truth anchor points (RTX 4070 Time Spy: ~18,000, Ryzen 7800X3D CPU: ~42,000)
REFERENCE_GPU_SCORE = 18000
REFERENCE_CPU_SCORE = 42000

# Sub-linear scaling elasticity exponents by resolution
GPU_ELASTICITY = {
    "1080p": 0.88,  # Mid-tier cards perform better than synthetic 1440p Time Spy indicates
    "1440p": 0.95,  # Approaching linear compute limits
    "4K": 1.00      # Strict linear compute and memory bandwidth bound
}

# Empirical game profiles: reference FPS when paired with reference hardware at 1080p native
GAME_PROFILES = {
    "Cyberpunk 2077": {
        "gpu_anchor_fps": 118.0,  # RTX 4070 @ 1080p Ultra Native (No RT/DLSS)
        "cpu_anchor_fps": 145.0,  # Max draw-call potential on flagship CPU
        "cpu_sensitivity": 0.35,  # GPU-heavy modern AAA engine
        "vram_demand_gb": {"1080p": 7.5, "1440p": 9.8, "4K": 13.5},
        "baseline_1pct_ratio": 0.80
    },
    "CS2": {
        "gpu_anchor_fps": 380.0,
        "cpu_anchor_fps": 340.0,
        "cpu_sensitivity": 0.65,  # Balanced Source 2 engine
        "vram_demand_gb": {"1080p": 4.0, "1440p": 5.5, "4K": 7.5},
        "baseline_1pct_ratio": 0.70
    },
    "Valorant": {
        "gpu_anchor_fps": 750.0,  # GPUs can render massive frames; CPU is almost always the limiter
        "cpu_anchor_fps": 580.0,  # 7800X3D hits ~580 FPS average
        "cpu_sensitivity": 0.85,  # Extremely CPU-cache and IPC bound
        "vram_demand_gb": {"1080p": 2.5, "1440p": 3.5, "4K": 5.0},
        "baseline_1pct_ratio": 0.72
    },
    "Elden Ring": {
        "gpu_anchor_fps": 145.0,  # Uncapped 1080p Maximum preset
        "cpu_anchor_fps": 160.0,
        "cpu_sensitivity": 0.40,
        "vram_demand_gb": {"1080p": 5.5, "1440p": 7.0, "4K": 9.5},
        "baseline_1pct_ratio": 0.82
    }
}


# ---------------------------------------------------------------------------
# 2. LUMPED-ELEMENT THERMAL & DUAL-HEAT ENGINE
# ---------------------------------------------------------------------------

def calculate_lumped_thermals(
    cpu_tdp: int,
    gpu_tdp: int,
    cooler_max_tdp: int,
    case_airflow_coef: float,
    ambient_temp: float = 30.0
):
    """
    Simulates multi-chamber heat convection using Ohm's Law of Heat.
    """
    total_watts_in_case = cpu_tdp + gpu_tdp + 35.0

    # Internal chassis air temperature delta based on fan exhaust flow
    internal_air_delta = (total_watts_in_case / 22.0) / float(case_airflow_coef)
    t_case_internal = ambient_temp + internal_air_delta

    # CPU Junction Temperature
    cpu_thermal_load = cpu_tdp / float(cooler_max_tdp)
    t_cpu = t_case_internal + (cpu_thermal_load * 38.0)

    # GPU Junction Temperature
    gpu_thermal_load = gpu_tdp / 280.0
    t_gpu = t_case_internal + (gpu_thermal_load * 32.0)

    # Throttling evaluation
    cpu_throttling = t_cpu > 90.0
    gpu_throttling = t_gpu > 86.0

    thermal_penalty = 1.0
    if cpu_throttling:
        overheat_c = t_cpu - 90.0
        thermal_penalty *= max(0.70, 1.0 - (overheat_c * 0.025))
    if gpu_throttling:
        overheat_c = t_gpu - 86.0
        thermal_penalty *= max(0.75, 1.0 - (overheat_c * 0.020))

    thermal_status = "Stable"
    if cpu_throttling and gpu_throttling:
        thermal_status = "CRITICAL THROTTLE (CPU & GPU)"
    elif cpu_throttling:
        thermal_status = "CPU THROTTLING"
    elif gpu_throttling:
        thermal_status = "GPU THROTTLING"
    elif t_cpu > 80.0 or t_gpu > 78.0:
        thermal_status = "High Thermal Load"

    return {
        "ambient_temp_c": round(ambient_temp, 1),
        "case_internal_temp_c": round(t_case_internal, 1),
        "cpu_temp_c": round(t_cpu, 1),
        "gpu_temp_c": round(t_gpu, 1),
        "thermal_penalty": thermal_penalty,
        "thermal_status": thermal_status
    }


# ---------------------------------------------------------------------------
# 3. DECOUPLED DUAL-PIPELINE PERFORMANCE ENGINE
# ---------------------------------------------------------------------------

def calculate_heuristic_performance(
    gpu_score: int,
    cpu_score: int,
    cpu_tdp: int,
    gpu_tdp: int,
    cooler_max_tdp: int,
    case_airflow_coef: float,
    game_name: str,
    resolution: str,
    gpu_vram_gb: int = 8,
    ambient_temp: float = 30.0,
    ram_channels: int = 2
):
    """
    Computes Average FPS, 1% Lows, and Bottlenecks using a decoupled
    frame-time latency model (t_frame = max(t_cpu, t_gpu) + t_sync).
    """
    profile = GAME_PROFILES.get(game_name, GAME_PROFILES["Cyberpunk 2077"])

    # 1. Workload-Dependent Resolution Elasticity
    # Heavy GPU games drop sharply (~28% at 1440p); esports CPU titles drop mildly (~10%)
    sensitivity = profile["cpu_sensitivity"]
    if resolution == "1080p":
        res_scale = 1.00
    elif resolution == "1440p":
        res_scale = 0.72 + (0.18 * sensitivity)
    else:  # 4K
        res_scale = 0.44 + (0.12 * sensitivity)

    # 2. Non-Linear GPU Scaling Pipeline Potential (t_gpu in milliseconds)
    alpha = GPU_ELASTICITY.get(resolution, 0.95)
    normalized_gpu_ratio = math.pow(gpu_score / REFERENCE_GPU_SCORE, alpha)
    potential_gpu_fps = profile["gpu_anchor_fps"] * normalized_gpu_ratio * res_scale
    t_gpu_ms = 1000.0 / max(1.0, potential_gpu_fps)

    # 3. CPU Pipeline Potential (t_cpu in milliseconds)
    # CPU potential is mostly resolution-invariant (handles draw calls/physics)
    cpu_scaling_ratio = math.pow(cpu_score / REFERENCE_CPU_SCORE, 0.78)
    potential_cpu_fps = profile["cpu_anchor_fps"] * cpu_scaling_ratio
    
    # Single-channel memory penalty on CPU draw-call dispatch
    if ram_channels <= 1:
        potential_cpu_fps *= (1.0 - (0.14 * sensitivity))

    t_cpu_ms = 1000.0 / max(1.0, potential_cpu_fps)

    # 4. Decoupled Frame-Time Pipeline Arbitration
    # The slower pipeline stage dominates frame generation
    t_sync_ms = 0.5
    t_frame_ms = max(t_gpu_ms, t_cpu_ms) + t_sync_ms
    base_avg_fps = 1000.0 / t_frame_ms

    # Bottleneck detection
    # If CPU latency exceeds GPU latency by more than 15%, it's a CPU bottleneck
    bottleneck_detected = t_cpu_ms > (t_gpu_ms * 1.15)
    bottleneck_severity_pct = 0.0
    if bottleneck_detected:
        bottleneck_severity_pct = round(((t_cpu_ms - t_gpu_ms) / t_cpu_ms) * 100.0, 1)

    # 5. VRAM Saturation & Paging Degradation
    demanded_vram = profile["vram_demand_gb"].get(resolution, 8.0)
    vram_deficit = max(0.0, demanded_vram - gpu_vram_gb)
    
    vram_penalty_avg = 1.0
    vram_penalty_lows = 1.0
    vram_status = "Optimal Capacity"

    if vram_deficit > 0:
        vram_penalty_avg = max(0.75, 1.0 - (vram_deficit * 0.055))
        vram_penalty_lows = max(0.55, 1.0 - (vram_deficit * 0.13))
        vram_status = f"VRAM Deficit: Demands {demanded_vram}GB, GPU has {gpu_vram_gb}GB"

    # 6. Thermal Dissipation Impact
    thermals = calculate_lumped_thermals(
        cpu_tdp=cpu_tdp,
        gpu_tdp=gpu_tdp,
        cooler_max_tdp=cooler_max_tdp,
        case_airflow_coef=case_airflow_coef,
        ambient_temp=ambient_temp
    )

    # 7. Final Output Consolidation
    final_avg_fps = base_avg_fps * vram_penalty_avg * thermals["thermal_penalty"]

    # 1% Lows & Micro-Stutter Stability
    cpu_gpu_ratio = min(1.0, t_gpu_ms / max(0.1, t_cpu_ms))
    bottleneck_stutter_penalty = math.pow(cpu_gpu_ratio, 1.4)
    ram_stutter_mult = 1.0 if ram_channels >= 2 else (1.0 - (0.22 * sensitivity))

    final_1pct_low = (
        final_avg_fps
        * profile["baseline_1pct_ratio"]
        * bottleneck_stutter_penalty
        * vram_penalty_lows
        * ram_stutter_mult
    )

    stability_pct = round((final_1pct_low / max(1.0, final_avg_fps)) * 100, 1)

    return {
        "predicted_fps": round(final_avg_fps),
        "fps_1pct_low": round(final_1pct_low),
        "frametime_stability_pct": stability_pct,
        "t_gpu_ms": round(t_gpu_ms, 2),
        "t_cpu_ms": round(t_cpu_ms, 2),
        "t_frame_ms": round(t_frame_ms, 2),
        "cpu_temp_c": thermals["cpu_temp_c"],
        "gpu_temp_c": thermals["gpu_temp_c"],
        "case_internal_temp_c": thermals["case_internal_temp_c"],
        "ambient_temp_c": thermals["ambient_temp_c"],
        "thermal_status": thermals["thermal_status"],
        "bottleneck_detected": bottleneck_detected,
        "bottleneck_severity_pct": bottleneck_severity_pct,
        "vram_status": vram_status
    }


# ---------------------------------------------------------------------------
# 4. FIRST-PRINCIPLES THEORETICAL CALCULATOR
# ---------------------------------------------------------------------------

def calculate_ground_up_performance(
    gpu_cores: int, gpu_clock_mhz: int,
    gpu_bus_bit: int, gpu_speed_gbps: float,
    cpu_ipc: float, cpu_boost_ghz: float, cpu_l3_cache_mb: int, cpu_tdp: int,
    cooler_max_tdp: int, case_airflow_coef: float,
    ram_speed_mts: int, game_name: str, resolution: str
):
    gpu_tflops = (2 * gpu_cores * gpu_clock_mhz) / 1_000_000.0
    gpu_bandwidth_gbs = (gpu_bus_bit * gpu_speed_gbps) / 8.0

    raw_gpu_index = (gpu_tflops * 0.75) + ((gpu_bandwidth_gbs / 30.0) * 0.25)
    cpu_index = (cpu_ipc * cpu_boost_ghz * 8.5) + (cpu_l3_cache_mb * 0.20) + (ram_speed_mts / 2000.0)

    game_scalar = {
        "Cyberpunk 2077": 5.4,
        "CS2": 24.5,
        "Valorant": 28.0,
        "Elden Ring": 7.8
    }.get(game_name, 6.0)

    res_scale = {"1080p": 1.0, "1440p": 0.72, "4K": 0.45}.get(resolution, 1.00)
    theoretical_fps = raw_gpu_index * game_scalar * res_scale

    required_cpu = raw_gpu_index * 1.65
    pipeline_feed_ratio = min(1.0, cpu_index / required_cpu)
    throttled_fps = theoretical_fps * (0.65 + 0.35 * pipeline_feed_ratio)

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


# ---------------------------------------------------------------------------
# 5. PHYSICAL CLEARANCE & GEOMETRIC COLLISION ENGINE
# ---------------------------------------------------------------------------

HARDWARE_DIMENSIONS = {
    "gpus": {
        "rtx_5090_strix": 358, "rtx_5090_gaming_trio": 340, "rtx_5080_gaming_oc": 315,
        "rtx_5080_ventus": 305, "rtx_5070_ti_tuf": 305, "rtx_5070_s_twin": 228,
        "rtx_5070_gaming_oc": 295, "rtx_4090_trio": 337, "rtx_4080_s_gaming_oc": 342,
        "rtx_4070_ti_s_tuf": 305, "rtx_4070_s_twin": 234, "rtx_4070_s_gaming_oc": 300,
        "rtx_4060_twin": 222, "rtx_4060_eagle": 272, "rx_7900_xtx_nitro": 320,
        "rx_7900_gre_hellhound": 322, "rx_7800_xt_nitro": 320, "rx_7700_xt_pure": 320,
        "rx_7600_xt_steel": 248, "rx_7600_pulse": 204, "arc_b580_limited": 250,
        "arc_b570_challenger": 240, "arc_a750_le": 267, "rx_6700_xt_qick": 323,
        "rx_6600_sapphire": 200, "rtx_3060_dual": 245, "rtx_3060_ti_twin": 222
    },
    "coolers": {
        "stock": {"type": "Air", "height_mm": 47, "rad_size_mm": 0},
        "assassin_x120": {"type": "Air", "height_mm": 148, "rad_size_mm": 0},
        "air_ag400": {"type": "Air", "height_mm": 150, "rad_size_mm": 0},
        "hyper_212_halo": {"type": "Air", "height_mm": 154, "rad_size_mm": 0},
        "peerless_120": {"type": "Air", "height_mm": 155, "rad_size_mm": 0},
        "phantom_spirit_120": {"type": "Air", "height_mm": 157, "rad_size_mm": 0},
        "air_ak620": {"type": "Air", "height_mm": 160, "rad_size_mm": 0},
        "aio_thermalright_aqua_240": {"type": "AIO", "height_mm": 52, "rad_size_mm": 240},
        "aio_240": {"type": "AIO", "height_mm": 52, "rad_size_mm": 240},
        "aio_deepcool_le720": {"type": "AIO", "height_mm": 52, "rad_size_mm": 360},
        "aio_liquid_freezer_240": {"type": "AIO", "height_mm": 65, "rad_size_mm": 240},
        "aio_liquid_freezer_360": {"type": "AIO", "height_mm": 65, "rad_size_mm": 360},
        "aio_360": {"type": "AIO", "height_mm": 52, "rad_size_mm": 360},
        "aio_kraken_360": {"type": "AIO", "height_mm": 53, "rad_size_mm": 360}
    },
    "cases": {
        "matx_glass": {"name": "InWin 301 Compact Glass", "max_gpu_len_mm": 330, "max_cooler_height_mm": 158, "max_radiator_mm": 240},
        "matx_mesh": {"name": "Tecware Forge M Mesh", "max_gpu_len_mm": 300, "max_cooler_height_mm": 160, "max_radiator_mm": 240},
        "matx_nexus_air": {"name": "Tecware Nexus Air M2", "max_gpu_len_mm": 330, "max_cooler_height_mm": 165, "max_radiator_mm": 240},
        "matx_ap201": {"name": "ASUS Prime AP201 Mesh", "max_gpu_len_mm": 338, "max_cooler_height_mm": 170, "max_radiator_mm": 360},
        "montech_air_100": {"name": "Montech Air 100 ARGB", "max_gpu_len_mm": 330, "max_cooler_height_mm": 161, "max_radiator_mm": 240},
        "atx_mesh": {"name": "Corsair 4000D Airflow", "max_gpu_len_mm": 360, "max_cooler_height_mm": 170, "max_radiator_mm": 360},
        "montech_air_903": {"name": "Montech Air 903 Max", "max_gpu_len_mm": 400, "max_cooler_height_mm": 180, "max_radiator_mm": 360},
        "phanteks_xt_pro": {"name": "Phanteks XT Pro Ultra", "max_gpu_len_mm": 415, "max_cooler_height_mm": 184, "max_radiator_mm": 360},
        "nzxt_h5_flow": {"name": "NZXT H5 Flow", "max_gpu_len_mm": 365, "max_cooler_height_mm": 165, "max_radiator_mm": 280},
        "lianli_lancool_216": {"name": "Lian Li Lancool 216", "max_gpu_len_mm": 392, "max_cooler_height_mm": 180, "max_radiator_mm": 360},
        "lianli_o11d_mini": {"name": "Lian Li O11 Dynamic Mini", "max_gpu_len_mm": 395, "max_cooler_height_mm": 170, "max_radiator_mm": 280},
        "fractal_north": {"name": "Fractal Design North", "max_gpu_len_mm": 355, "max_cooler_height_mm": 170, "max_radiator_mm": 240},
        "itx_compact": {"name": "Cooler Master NR200", "max_gpu_len_mm": 330, "max_cooler_height_mm": 155, "max_radiator_mm": 240},
        "ssupd_meshlicious": {"name": "SSUPD Meshlicious ITX", "max_gpu_len_mm": 336, "max_cooler_height_mm": 73, "max_radiator_mm": 280}
    }
}

def check_physical_clearances(gpu_id: str, cooler_id: str, case_id: str) -> dict:
    case_spec = HARDWARE_DIMENSIONS["cases"].get(case_id, {
        "name": "Standard Chassis", "max_gpu_len_mm": 320, "max_cooler_height_mm": 160, "max_radiator_mm": 240
    })
    gpu_len = HARDWARE_DIMENSIONS["gpus"].get(gpu_id, 260)
    cooler_spec = HARDWARE_DIMENSIONS["coolers"].get(cooler_id, {
        "type": "Air", "height_mm": 150, "rad_size_mm": 0
    })

    conflicts = []

    if gpu_len > case_spec["max_gpu_len_mm"]:
        conflicts.append(f"GPU Collision: Card length ({gpu_len}mm) exceeds {case_spec['name']} clearance ({case_spec['max_gpu_len_mm']}mm).")

    if cooler_spec["type"] == "Air" and cooler_spec["height_mm"] > case_spec["max_cooler_height_mm"]:
        conflicts.append(f"Cooler Height Conflict: Air cooler ({cooler_spec['height_mm']}mm) exceeds {case_spec['name']} limit ({case_spec['max_cooler_height_mm']}mm).")

    if cooler_spec["type"] == "AIO" and cooler_spec["rad_size_mm"] > case_spec["max_radiator_mm"]:
        conflicts.append(f"Radiator Conflict: Cooler requires {cooler_spec['rad_size_mm']}mm mounting, but {case_spec['name']} accommodates up to {case_spec['max_radiator_mm']}mm.")

    return {
        "is_compatible": len(conflicts) == 0,
        "conflicts": conflicts,
        "metrics": {
            "gpu_length_mm": gpu_len,
            "max_gpu_allowed_mm": case_spec["max_gpu_len_mm"],
            "cooler_height_mm": cooler_spec["height_mm"],
            "max_cooler_allowed_mm": case_spec["max_cooler_height_mm"]
        }
    }
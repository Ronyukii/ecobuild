import math

# ---------------------------------------------------------------------------
# 1. EMPIRICAL REFERENCE ANCHORS & ENGINE PROFILES
# ---------------------------------------------------------------------------

# Resolution scaling factor relative to 1080p rasterization baseline
RESOLUTION_SCALE = {
    "1080p": 1.00,
    "1440p": 0.72,   # ~28% rasterization drop vs 1080p
    "4K": 0.45,      # ~55% rasterization drop vs 1080p
}

# Ground truth anchor GPU (NVIDIA RTX 4070, TimeSpy Graphics: ~18,000, 12GB VRAM)
REFERENCE_GPU_SCORE = 18000 

# Game architectural profiles detailing engine bias and VRAM footprint demands
GAME_PROFILES = {
    "Cyberpunk 2077": {
        "reference_fps": 82,
        "cpu_sensitivity": 0.35,  # GPU-heavy modern AAA engine
        "vram_demand_gb": {"1080p": 7.5, "1440p": 9.8, "4K": 13.5},
        "baseline_1pct_ratio": 0.78  # Standard 1% low is ~78% of average FPS
    },
    "CS2": {
        "reference_fps": 380,
        "cpu_sensitivity": 0.65,  # Balanced Source 2 engine
        "vram_demand_gb": {"1080p": 4.0, "1440p": 5.5, "4K": 7.5},
        "baseline_1pct_ratio": 0.70
    },
    "Valorant": {
        "reference_fps": 450,
        "cpu_sensitivity": 0.85,  # Extremely CPU-cache and IPC bound
        "vram_demand_gb": {"1080p": 2.5, "1440p": 3.5, "4K": 5.0},
        "baseline_1pct_ratio": 0.75
    },
    "Elden Ring": {
        "reference_fps": 115,
        "cpu_sensitivity": 0.40,
        "vram_demand_gb": {"1080p": 5.5, "1440p": 7.0, "4K": 9.5},
        "baseline_1pct_ratio": 0.80
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
    ambient_temp: float = 30.0  # Default Malaysian tropical room temperature
):
    """
    Simulates multi-chamber heat convection using Ohm's Law of Heat:
    Stage 1: Calculate internal chassis air equilibrium temperature.
    Stage 2: Calculate individual CPU and GPU junction temperatures.
    """
    # Total heat dissipation inside chassis (CPU + GPU + ~35W Motherboard/VRM/RAM)
    total_watts_in_case = cpu_tdp + gpu_tdp + 35.0

    # Internal chassis air temperature delta based on fan exhaust flow
    # Airflow coefficient: 1.0 (Mesh/High Flow) down to 0.65 (Choked ITX/Solid Glass)
    internal_air_delta = (total_watts_in_case / 22.0) / float(case_airflow_coef)
    t_case_internal = ambient_temp + internal_air_delta

    # CPU Junction Temperature: Heatsink dissipates heat into internal chassis air
    cpu_thermal_load = cpu_tdp / float(cooler_max_tdp)
    t_cpu = t_case_internal + (cpu_thermal_load * 38.0)

    # GPU Junction Temperature: Standard dual/triple fan shroud dissipation into case air
    gpu_thermal_load = gpu_tdp / 280.0
    t_gpu = t_case_internal + (gpu_thermal_load * 32.0)

    # Throttling evaluation
    cpu_throttling = t_cpu > 90.0
    gpu_throttling = t_gpu > 86.0

    thermal_penalty = 1.0
    if cpu_throttling:
        # Dynamic clock degradation beyond 90C
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
# 3. COMPREHENSIVE HEURISTIC PERFORMANCE PREDICTION
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
    ambient_temp: float = 30.0
):
    """
    Computes Average FPS, 1% Low Frametime Stability, Bottleneck Severity,
    VRAM Paging Penalties, and Dual-Component Thermals.
    """
    profile = GAME_PROFILES.get(game_name, GAME_PROFILES["Cyberpunk 2077"])

    # 1. Base GPU Scaling & Resolution Scaling
    gpu_ratio = gpu_score / REFERENCE_GPU_SCORE
    res_scale = RESOLUTION_SCALE.get(resolution, 1.00)
    raw_fps = profile["reference_fps"] * gpu_ratio * res_scale

    # 2. Dynamic CPU Bottlenecking (Weighted by Engine Bias)
    # CPU-heavy titles demand higher CPU scores to keep GPU saturated
    sensitivity = profile["cpu_sensitivity"]
    cpu_target = gpu_score * (1.10 + (sensitivity * 0.40))
    cpu_feed_ratio = min(1.0, cpu_score / cpu_target)
    
    bottleneck_detected = cpu_feed_ratio < 0.95
    bottleneck_severity_pct = round((1.0 - cpu_feed_ratio) * 100, 1) if bottleneck_detected else 0.0

    # Bottleneck dampens average FPS based on how CPU-dependent the title is
    fps_after_cpu = raw_fps * (1.0 - (1.0 - cpu_feed_ratio) * sensitivity)

    # 3. VRAM Memory Saturation & Paging Penalty
    demanded_vram = profile["vram_demand_gb"].get(resolution, 8.0)
    vram_deficit = max(0.0, demanded_vram - gpu_vram_gb)
    
    vram_penalty_avg = 1.0
    vram_penalty_lows = 1.0
    vram_status = "Optimal Capacity"

    if vram_deficit > 0:
        # PCIe Bus asset paging causes framerate drop and intense frame micro-stutters
        vram_penalty_avg = max(0.75, 1.0 - (vram_deficit * 0.06))
        vram_penalty_lows = max(0.55, 1.0 - (vram_deficit * 0.14))
        vram_status = f"VRAM Deficit: Demands {demanded_vram}GB, GPU has {gpu_vram_gb}GB"

    # 4. Multi-Chamber Dual Thermal Equilibrium
    thermals = calculate_lumped_thermals(
        cpu_tdp=cpu_tdp,
        gpu_tdp=gpu_tdp,
        cooler_max_tdp=cooler_max_tdp,
        case_airflow_coef=case_airflow_coef,
        ambient_temp=ambient_temp
    )

    # 5. Final Average FPS Calculation
    final_avg_fps = fps_after_cpu * vram_penalty_avg * thermals["thermal_penalty"]

    # 6. 1% Low FPS & Micro-Stutter Stability
    # CPU bottlenecks and VRAM overflow hit 1% Lows significantly harder than average FPS
    bottleneck_stutter_penalty = math.pow(cpu_feed_ratio, 1.8)
    final_1pct_low = (
        final_avg_fps
        * profile["baseline_1pct_ratio"]
        * bottleneck_stutter_penalty
        * vram_penalty_lows
    )

    # Frametime stability index percentage (100% = perfectly flat frametime pacing)
    stability_pct = round((final_1pct_low / max(1.0, final_avg_fps)) * 100, 1)

    return {
        "predicted_fps": round(final_avg_fps),
        "fps_1pct_low": round(final_1pct_low),
        "frametime_stability_pct": stability_pct,
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
    """
    Computes theoretical FPS from first-principles architectural physics:
    TFLOPs, memory bandwidth, IPC throughput, and memory latency.
    """
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

    res_scale = RESOLUTION_SCALE.get(resolution, 1.00)
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

# Real-world manufacturer millimeter specifications
HARDWARE_DIMENSIONS = {
    "gpus": {
        # NVIDIA RTX 50 Series
        "rtx_5090_strix": 358,
        "rtx_5090_gaming_trio": 340,
        "rtx_5080_gaming_oc": 315,
        "rtx_5080_ventus": 305,
        "rtx_5070_ti_tuf": 305,
        "rtx_5070_s_twin": 228,
        "rtx_5070_gaming_oc": 295,
        # NVIDIA RTX 40 Series
        "rtx_4090_trio": 337,
        "rtx_4080_s_gaming_oc": 342,
        "rtx_4070_ti_s_tuf": 305,
        "rtx_4070_s_twin": 234,
        "rtx_4070_s_gaming_oc": 300,
        "rtx_4060_twin": 222,
        "rtx_4060_eagle": 272,
        # AMD Radeon RX 7000 Series
        "rx_7900_xtx_nitro": 320,
        "rx_7900_gre_hellhound": 322,
        "rx_7800_xt_nitro": 320,
        "rx_7700_xt_pure": 320,
        "rx_7600_xt_steel": 248,
        "rx_7600_pulse": 204,
        # Intel Arc Series
        "arc_b580_limited": 250,
        "arc_b570_challenger": 240,
        "arc_a750_le": 267,
        # Legacy
        "rx_6700_xt_qick": 323,
        "rx_6600_sapphire": 200,
        "rtx_3060_dual": 245,
        "rtx_3060_ti_twin": 222
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
    """
    Validates physical millimeter dimensions:
    - GPU length vs chassis interior clearance
    - CPU air cooler height vs case width
    - Liquid AIO radiator mount compatibility
    """
    case_spec = HARDWARE_DIMENSIONS["cases"].get(case_id, {
        "name": "Standard Chassis",
        "max_gpu_len_mm": 320,
        "max_cooler_height_mm": 160,
        "max_radiator_mm": 240
    })
    gpu_len = HARDWARE_DIMENSIONS["gpus"].get(gpu_id, 260)
    cooler_spec = HARDWARE_DIMENSIONS["coolers"].get(cooler_id, {
        "type": "Air", "height_mm": 150, "rad_size_mm": 0
    })

    conflicts = []

    # 1. GPU Length Clearance Check
    if gpu_len > case_spec["max_gpu_len_mm"]:
        conflicts.append(
            f"GPU Collision: Graphics card length ({gpu_len}mm) exceeds {case_spec['name']} maximum GPU clearance ({case_spec['max_gpu_len_mm']}mm)."
        )

    # 2. CPU Cooler Height Clearance (Air)
    if cooler_spec["type"] == "Air" and cooler_spec["height_mm"] > case_spec["max_cooler_height_mm"]:
        conflicts.append(
            f"Cooler Height Conflict: Air cooler ({cooler_spec['height_mm']}mm) exceeds {case_spec['name']} clearance ({case_spec['max_cooler_height_mm']}mm). Side panel cannot close."
        )

    # 3. Liquid Radiator Mounting Support (AIO)
    if cooler_spec["type"] == "AIO" and cooler_spec["rad_size_mm"] > case_spec["max_radiator_mm"]:
        conflicts.append(
            f"Radiator Mount Conflict: Cooler requires {cooler_spec['rad_size_mm']}mm radiator mounting, but {case_spec['name']} only accommodates up to {case_spec['max_radiator_mm']}mm."
        )

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
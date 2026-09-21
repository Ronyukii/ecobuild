from app.real_engine import calculate_heuristic_performance

print("\n--- TEST CASE 1: Standard Room (31°C) vs Air-Conditioned (24°C) ---")
hot_room = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
    cooler_max_tdp=220, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
    resolution="1080p", gpu_vram_gb=12, ambient_temp=31.0
)
ac_room = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=21500, cpu_tdp=65, gpu_tdp=200,
    cooler_max_tdp=220, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
    resolution="1080p", gpu_vram_gb=12, ambient_temp=24.0
)
print(f"Non-AC Room (31°C) -> Case Air: {hot_room['case_internal_temp_c']}°C | CPU: {hot_room['cpu_temp_c']}°C | GPU: {hot_room['gpu_temp_c']}°C")
print(f"AC Room (24°C)     -> Case Air: {ac_room['case_internal_temp_c']}°C | CPU: {ac_room['cpu_temp_c']}°C | GPU: {ac_room['gpu_temp_c']}°C")

print("\n--- TEST CASE 2: VRAM Saturation Penalty at 4K (8GB Card vs 16GB Card) ---")
card_8gb = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=34000, cpu_tdp=125, gpu_tdp=220,
    cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
    resolution="4K", gpu_vram_gb=8, ambient_temp=30.0
)
card_16gb = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=34000, cpu_tdp=125, gpu_tdp=220,
    cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Cyberpunk 2077",
    resolution="4K", gpu_vram_gb=16, ambient_temp=30.0
)
print(f"8GB Card @ 4K  -> Avg FPS: {card_8gb['predicted_fps']} | 1% Lows: {card_8gb['fps_1pct_low']} FPS | Status: {card_8gb['vram_status']}")
print(f"16GB Card @ 4K -> Avg FPS: {card_16gb['predicted_fps']} | 1% Lows: {card_16gb['fps_1pct_low']} FPS | Status: {card_16gb['vram_status']}")

print("\n--- TEST CASE 3: CPU Bottleneck & Frametime Stability Impact ---")
balanced_build = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=34000, cpu_tdp=125, gpu_tdp=200,
    cooler_max_tdp=260, case_airflow_coef=1.0, game_name="Valorant",
    resolution="1080p", gpu_vram_gb=12
)
bottleneck_build = calculate_heuristic_performance(
    gpu_score=18000, cpu_score=14200, cpu_tdp=58, gpu_tdp=200,
    cooler_max_tdp=65, case_airflow_coef=1.0, game_name="Valorant",
    resolution="1080p", gpu_vram_gb=12
)
print(f"Strong CPU (i7) -> Avg: {balanced_build['predicted_fps']} FPS | 1% Lows: {balanced_build['fps_1pct_low']} FPS | Stability: {balanced_build['frametime_stability_pct']}%")
print(f"Weak CPU (i3)   -> Avg: {bottleneck_build['predicted_fps']} FPS | 1% Lows: {bottleneck_build['fps_1pct_low']} FPS | Stability: {bottleneck_build['frametime_stability_pct']}% (Stutter!)")
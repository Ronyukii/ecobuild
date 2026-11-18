import ast
import json
import glob
from pathlib import Path

main_src = Path("backend/app/main.py").read_text(encoding="utf-8")
engine_src = Path("backend/app/real_engine.py").read_text(encoding="utf-8")
eval_src = Path("backend/app/evaluate_accuracy.py").read_text(encoding="utf-8")

print("=== 1. MAIN.PY CALL-SITE CHECK ===")
tree = ast.parse(main_src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in ("simulate_build_configuration", "optimize_build_configuration", "export_bill_of_materials"):
        calls = [
            f"line {c.lineno}: kwargs={[kw.arg for kw in c.keywords]}"
            for c in ast.walk(node)
            if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "calculate_heuristic_performance"
        ]
        print(f"  {node.name}: {calls}")

print("\n=== 2. REAL_ENGINE.PY FALLBACK & CONSTANTS CHECK ===")
print("  unknown-game fallback present:", 'GAME_PROFILES.get(game_name, GAME_PROFILES["Cyberpunk 2077"])' in engine_src)
print("  UnsupportedGameError defined:", "class UnsupportedGameError" in engine_src)

print("\n=== 3. EVALUATE_ACCURACY.PY CHECK ===")
for line in eval_src.splitlines():
    if "CALIBRATION_DATASET" in line or "ram_channels=" in line or "load_offline_catalogs" in line or "low_metrics" in line:
        print(" ", line.strip())

print("\n=== 4. CATALOGUE FIXTURE SUMMARY (backend/data/*.json) ===")
for f in sorted(glob.glob("backend/data/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if isinstance(d, list):
        print(f"  {f}: {len(d)} items | sample keys={list(d[0].keys()) if d else []}")
    elif isinstance(d, dict):
        print(f"  {f}: dict keys={list(d.keys())}")

print("\n=== 5. RTX 4070 CANONICAL REFERENCE CHECK ===")
gpus = json.load(open("backend/data/gpus.json", encoding="utf-8"))
rtx4070 = next((g for g in gpus if g["gpu_id"] == "rtx_4070_dual"), None)
if rtx4070:
    print(f"  rtx_4070_dual found: base_score={rtx4070.get('base_score')}, TDP={rtx4070.get('tdp_watts')}W, VRAM={rtx4070.get('vram_gb')}GB, length_mm={rtx4070.get('length_mm')}")
else:
    print("  ERROR: rtx_4070_dual NOT found in gpus.json!")

print("\n=== 6. CALIBRATION DATASET INTEGRITY CHECK ===")
cal_path = Path("backend/data/calibration_dataset.json")
if cal_path.exists():
    cal_data = json.load(open(cal_path, encoding="utf-8"))
    print(f"  Records loaded: {len(cal_data)}")
    roles = set(r.get("dataset_role") for r in cal_data)
    print(f"  Dataset roles present: {roles}")
    anchors = sum(1 for r in cal_data if "Internal calibration anchor" in r.get("provenance", {}).get("notes", ""))
    provenanced = len(cal_data) - anchors
    print(f"  Provenanced reviewer records: {provenanced}, Anchor records: {anchors}")
else:
    print("  ERROR: calibration_dataset.json not found!")

holdout_path = Path("backend/data/validation_holdout_dataset.json")
if holdout_path.exists():
    holdout_data = json.load(open(holdout_path, encoding="utf-8"))
    print(f"  Holdout records (must be 0): {len(holdout_data)}")

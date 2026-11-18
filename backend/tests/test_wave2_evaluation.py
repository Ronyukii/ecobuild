"""
backend/tests/test_wave2_evaluation.py

Wave 2 Evaluation Integrity & Methodology Test Suite
- Verifies in-sample calibration dataset classification and granular provenance
- Verifies empty independent holdout dataset state
- Verifies benchmark schema v2 compliance
- Verifies offline evaluation functionality without database dependency
- Verifies dual-metric computation (Average FPS and 1% Lows reported separately)
- Verifies explicit exception on missing hardware IDs (no silent dropping)
- Verifies generated documentation artifacts
"""

import os
import sys
import json
import pytest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluate_accuracy import (
    evaluate_dataset,
    load_offline_catalogs,
    DEFAULT_CALIBRATION_DATASET,
    DEFAULT_HOLDOUT_DATASET,
    DATA_DIR
)


class TestWave2EvaluationIntegrity:

    def test_calibration_dataset_classification_and_count(self):
        """The calibration dataset must contain exactly 19 in-sample records."""
        assert DEFAULT_CALIBRATION_DATASET.exists(), "calibration_dataset.json must exist"
        with open(DEFAULT_CALIBRATION_DATASET, "r", encoding="utf-8") as f:
            records = json.load(f)

        assert len(records) == 19, f"Expected 19 calibration records, found {len(records)}"

        # Every record must be explicitly classified as in-sample calibration
        for r in records:
            assert r["dataset_role"] == "calibration_in_sample", (
                f"Record {r['id']} has role '{r.get('dataset_role')}', expected 'calibration_in_sample'"
            )
            assert r["measurement_origin"] == "direct_measurement"
            assert r["ref_avg_fps"] > 0
            assert r["provenance"]["eligibility"] == "calibration_only"

    def test_calibration_provenance_distinction(self):
        """Must distinguish the 12 provenanced reviewer records from the 7 anchor records."""
        with open(DEFAULT_CALIBRATION_DATASET, "r", encoding="utf-8") as f:
            records = json.load(f)

        anchor_ids = {"VAL-05", "VAL-06", "VAL-07", "VAL-13", "VAL-14", "VAL-16", "VAL-19"}
        provenanced_ids = {r["id"] for r in records} - anchor_ids

        assert len(anchor_ids) == 7
        assert len(provenanced_ids) == 12

        for r in records:
            if r["id"] in anchor_ids:
                assert "Internal calibration anchor" in r["provenance"]["notes"], (
                    f"Anchor {r['id']} must note internal calibration role"
                )
            else:
                assert r["provenance"]["publisher"] in ["Hardware Unboxed", "TechPowerUp", "Gamers Nexus"], (
                    f"Record {r['id']} must have documented external reviewer provenance"
                )
                assert r["provenance"]["preset"] is not None
                assert r["provenance"]["test_method"] is not None

    def test_validation_holdout_dataset_remains_empty(self):
        """Independent holdout collection must remain an empty array until approved."""
        assert DEFAULT_HOLDOUT_DATASET.exists(), "validation_holdout_dataset.json must exist"
        with open(DEFAULT_HOLDOUT_DATASET, "r", encoding="utf-8") as f:
            records = json.load(f)

        assert isinstance(records, list), "Holdout dataset must be a list"
        assert len(records) == 0, f"Holdout dataset must be empty ([]), but contains {len(records)} records"

    def test_benchmark_schema_v2_structure(self):
        """benchmark_schema.v2.json must enforce role separation and optional test environment."""
        schema_path = DATA_DIR / "benchmark_schema.v2.json"
        assert schema_path.exists(), "benchmark_schema.v2.json must exist"

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        required_fields = schema["items"]["required"]
        assert "dataset_role" in required_fields
        assert "measurement_origin" in required_fields
        assert "provenance" in required_fields

        role_enum = schema["items"]["properties"]["dataset_role"]["enum"]
        assert "calibration_in_sample" in role_enum
        assert "independent_validation" in role_enum

    def test_offline_evaluator_on_calibration_dataset(self):
        """Offline evaluation must process all 19 cases and return separate dual metrics."""
        eval_res = evaluate_dataset(dataset_path=DEFAULT_CALIBRATION_DATASET, offline=True)

        assert eval_res["sample_size"] == 19
        assert eval_res["dataset_role"] == "calibration_in_sample"

        avg_m = eval_res["avg_metrics"]
        low_m = eval_res["low_metrics"]

        # Average FPS metrics check
        assert avg_m["n"] == 19
        assert avg_m["mae"] > 0.0
        assert avg_m["rmse"] > 0.0
        assert avg_m["mape"] > 0.0
        assert 0.0 <= avg_m["r2"] <= 1.0

        # 1% Low FPS metrics check
        assert low_m["n"] == 19
        assert low_m["mae"] > 0.0
        assert low_m["rmse"] > 0.0
        assert low_m["mape"] > 0.0
        assert 0.0 <= low_m["r2"] <= 1.0

        # Confirm average and 1% low metrics are mathematically distinct
        assert avg_m["mae"] != low_m["mae"]
        assert avg_m["mape"] != low_m["mape"]

    def test_offline_evaluator_missing_hardware_raises_error(self, tmp_path):
        """Referencing an uncatalogued hardware ID must raise ValueError, not silently drop."""
        invalid_dataset = [
            {
                "id": "VAL-99",
                "dataset_role": "calibration_in_sample",
                "measurement_origin": "direct_measurement",
                "cpu_id": "nonexistent_cpu_999",
                "gpu_id": "rtx_4070_dual",
                "game_name": "Cyberpunk 2077",
                "resolution": "1080p",
                "ref_avg_fps": 60.0,
                "provenance": {"source_title": "Test", "eligibility": "calibration_only"}
            }
        ]
        tmp_file = tmp_path / "invalid_bench.json"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(invalid_dataset, f)

        with pytest.raises(ValueError) as exc_info:
            evaluate_dataset(dataset_path=tmp_file, offline=True)

        assert "Integrity check failed" in str(exc_info.value)
        assert "nonexistent_cpu_999" in str(exc_info.value)

    def test_offline_evaluator_empty_holdout(self):
        """Evaluating the empty holdout dataset must return sample_size == 0 safely."""
        eval_res = evaluate_dataset(dataset_path=DEFAULT_HOLDOUT_DATASET, offline=True)
        assert eval_res["sample_size"] == 0
        assert eval_res["status"] == "EMPTY"

    def test_artifacts_exist_and_contain_required_disclosures(self):
        """Calibration report and LaTeX table must exist and contain honest disclosures."""
        md_path = DATA_DIR / "calibration_report.md"
        tex_path = DATA_DIR / "calibration_table.tex"
        json_path = DATA_DIR / "evaluation_results.json"

        assert md_path.exists(), "calibration_report.md must exist"
        assert tex_path.exists(), "calibration_table.tex must exist"
        assert json_path.exists(), "evaluation_results.json must exist"

        md_content = md_path.read_text(encoding="utf-8")
        assert "In-Sample Calibration" in md_content
        assert "PENDING" in md_content
        assert "1% Low FPS" in md_content

        with open(json_path, "r", encoding="utf-8") as f:
            res_data = json.load(f)

        assert "average_fps" in res_data["metrics"]
        assert "fps_1pct_low" in res_data["metrics"]
        assert "LETM" in res_data["disclosures"]["thermal_status"]
        assert "PENDING" in res_data["disclosures"]["holdout_status"]

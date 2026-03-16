"""Tests for growpy.utils.yield_tables module."""

import json
from pathlib import Path

import numpy as np
import pytest

from growpy.utils.yield_tables import (
    YieldTableData,
    compute_dbh_static_overrides,
    compute_grow_length_curve,
    compute_thicken_tips_curve,
    estimate_flushes_per_year,
    interpolate_yield_table,
    load_local_yield_table,
    write_calibration_to_seed_json,
)


class TestYieldTableData:
    """Tests for YieldTableData dataclass."""

    def test_basic_creation(self):
        yt = YieldTableData(
            ages=[0, 10, 20],
            heights=[0.5, 5.0, 12.0],
            dbhs=[0.0, 0.04, 0.10],
            title="Test",
            source="local",
        )
        assert yt.ages == [0, 10, 20]
        assert yt.source == "local"
        assert yt.yield_class is None
        assert yt.table_id is None

    def test_optional_fields(self):
        yt = YieldTableData(
            ages=[10],
            heights=[5.0],
            dbhs=[0.04],
            title="API",
            source="openyieldtables",
            yield_class=1.5,
            table_id=42,
        )
        assert yt.yield_class == 1.5
        assert yt.table_id == 42


class TestLoadLocalYieldTable:
    """Tests for load_local_yield_table."""

    def test_valid_csv(self, tmp_path):
        csv = tmp_path / "norway_spruce.csv"
        csv.write_text("age,height,dbh\n0,0.5,0\n10,5.2,4.5\n20,12.3,10.2\n")
        result = load_local_yield_table("norway_spruce", tmp_path)
        assert result is not None
        assert result.ages == [0, 10, 20]
        assert result.heights == [0.5, 5.2, 12.3]
        # DBH should be converted from cm to m
        assert result.dbhs == pytest.approx([0.0, 0.045, 0.102])
        assert result.source == "local"

    def test_missing_file_returns_none(self, tmp_path):
        assert load_local_yield_table("nonexistent", tmp_path) is None

    def test_missing_columns_returns_none(self, tmp_path):
        csv = tmp_path / "bad.csv"
        csv.write_text("age,wrong_col\n10,5\n")
        assert load_local_yield_table("bad", tmp_path) is None

    def test_sorts_by_age(self, tmp_path):
        csv = tmp_path / "unsorted.csv"
        csv.write_text("age,height,dbh\n20,12,10\n0,0.5,0\n10,5,4\n")
        result = load_local_yield_table("unsorted", tmp_path)
        assert result.ages == [0, 10, 20]
        assert result.heights == [0.5, 5.0, 12.0]


class TestEstimateFlushesPerYear:
    """Tests for estimate_flushes_per_year."""

    def test_short_grove_heights_returns_default(self):
        assert estimate_flushes_per_year([1, 2, 3], [10, 20], [5, 12]) == 1.0

    def test_short_yield_data_returns_default(self):
        assert estimate_flushes_per_year([1] * 10, [10], [5]) == 1.0

    def test_very_small_grove_max_returns_default(self):
        assert estimate_flushes_per_year([0.1] * 10, [10, 20], [5, 12]) == 1.0

    def test_matching_curves_gives_near_one(self):
        # Yield table: ages and STRICTLY increasing heights
        # estimate_flushes_per_year prepends (0.5 height), so first yield height must be > 0.5
        ages = [10, 20, 30, 40, 50]
        heights = [5.0, 12.0, 18.0, 22.0, 24.0]
        # Grove heights that grow steadily
        grove = [0.5 + i * 0.47 for i in range(50)]
        fpy = estimate_flushes_per_year(grove, ages, heights)
        assert 0.3 <= fpy <= 3.0

    def test_result_is_clamped(self):
        ages = [10, 20, 30, 40, 50]
        heights = [5.0, 12.0, 18.0, 22.0, 24.0]
        # Very fast Grove growth -> fpy should be clamped to 3.0 max
        grove = [i * 2.0 for i in range(50)]
        fpy = estimate_flushes_per_year(grove, ages, heights)
        assert fpy <= 3.0
        assert fpy >= 0.3


class TestInterpolateYieldTable:
    """Tests for interpolate_yield_table."""

    def test_basic_interpolation(self):
        ages = [10, 20, 30]
        heights = [5.0, 12.0, 18.0]
        cycles, values = interpolate_yield_table(ages, heights, max_cycles=30)
        assert len(cycles) == 30
        assert len(values) == 30
        assert all(v >= 0 for v in values)

    def test_initial_value(self):
        ages = [10, 20]
        heights = [5.0, 12.0]
        _, vals = interpolate_yield_table(
            ages, heights, max_cycles=5, initial_value=1.0
        )
        # First value should be near initial_value at cycle 1
        assert vals[0] > 0

    def test_flushes_per_year_scaling(self):
        ages = [10, 20, 30]
        heights = [5.0, 12.0, 18.0]
        _, vals_1 = interpolate_yield_table(ages, heights, 30, flushes_per_year=1.0)
        _, vals_2 = interpolate_yield_table(ages, heights, 30, flushes_per_year=2.0)
        # With 2 flushes/year, each cycle covers less time so heights should be lower
        assert vals_2[-1] < vals_1[-1]

    def test_non_negative_output(self):
        ages = [10, 20]
        heights = [5.0, 12.0]
        _, vals = interpolate_yield_table(ages, heights, 50)
        assert all(v >= 0 for v in vals)


class TestComputeGrowLengthCurve:
    """Tests for compute_grow_length_curve."""

    def test_output_length_matches_input(self):
        grove_h = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        target_h = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = compute_grow_length_curve(grove_h, target_h, base_grow_length=0.3)
        assert len(result) == 10

    def test_matching_curves_near_base(self):
        grove_h = [float(i) for i in range(1, 21)]
        target_h = np.array([float(i) for i in range(1, 21)])
        result = compute_grow_length_curve(grove_h, target_h, base_grow_length=0.3)
        # When curves match, grow_length should stay near base
        for v in result:
            assert 0.2 <= v <= 0.5

    def test_values_are_clamped(self):
        grove_h = [float(i) for i in range(1, 21)]
        # Target grows much faster
        target_h = np.array([float(i * 5) for i in range(1, 21)])
        result = compute_grow_length_curve(grove_h, target_h, base_grow_length=0.3)
        for v in result:
            assert v <= 0.65  # max ceiling


class TestComputeThickenTipsCurve:
    """Tests for compute_thicken_tips_curve."""

    def test_output_length(self):
        grove_dbh = [0.01 * i for i in range(1, 21)]
        target_dbh = np.array([0.01 * i for i in range(1, 21)])
        result = compute_thicken_tips_curve(grove_dbh, target_dbh, base_thicken_tips=0.01)
        assert len(result) == 20

    def test_values_clamped(self):
        grove_dbh = [0.01 * i for i in range(1, 21)]
        target_dbh = np.array([0.05 * i for i in range(1, 21)])
        result = compute_thicken_tips_curve(grove_dbh, target_dbh, base_thicken_tips=0.01)
        for v in result:
            assert v <= 0.03  # ceiling


class TestComputeDbhStaticOverrides:
    """Tests for compute_dbh_static_overrides."""

    def test_returns_empty_dict_normally(self):
        result = compute_dbh_static_overrides(
            [0.01, 0.02, 0.03],
            np.array([0.01, 0.02, 0.03]),
        )
        assert result == {}

    def test_returns_empty_for_short_data(self):
        result = compute_dbh_static_overrides([0.01], np.array([0.01]))
        assert result == {}

    def test_zeroes_deadwood_if_present(self):
        result = compute_dbh_static_overrides(
            [0.01, 0.02, 0.03],
            np.array([0.01, 0.02, 0.03]),
            base_thicken_deadwood=0.5,
        )
        assert result.get("thicken_deadwood") == 0.0


class TestWriteCalibrationToSeedJson:
    """Tests for write_calibration_to_seed_json."""

    def test_writes_calibration_block(self, tmp_path):
        presets_dir = tmp_path
        preset_path = presets_dir / "norway_spruce.seed.json"
        preset_path.write_text(json.dumps({"grow_length": 0.3}))

        result = write_calibration_to_seed_json(
            species_name="Norway spruce",
            grow_lengths=[0.3, 0.31, 0.29],
            table_title="Test Table",
            presets_dir=presets_dir,
        )
        assert result == preset_path

        data = json.loads(preset_path.read_text())
        cal = data["_yield_table_calibration"]
        assert cal["table_title"] == "Test Table"
        assert len(cal["grow_length_per_cycle"]) == 3
        assert cal["flushes_per_year"] == 1.0

    def test_missing_preset_returns_none(self, tmp_path):
        result = write_calibration_to_seed_json(
            "Missing species", [0.3], "Table", tmp_path,
        )
        assert result is None

    def test_optional_fields_written(self, tmp_path):
        preset = tmp_path / "test_species.seed.json"
        preset.write_text(json.dumps({"grow_length": 0.3}))
        write_calibration_to_seed_json(
            "Test species",
            [0.3],
            "Table",
            tmp_path,
            yield_class=1.5,
            table_id=42,
            thicken_tips_per_cycle=[0.01],
            static_overrides={"thicken_deadwood": 0.0},
            target_dbh_per_cycle=[0.05],
            flushes_per_year=1.2,
        )
        data = json.loads(preset.read_text())
        cal = data["_yield_table_calibration"]
        assert cal["yield_class"] == 1.5
        assert cal["table_id"] == 42
        assert cal["thicken_tips_per_cycle"] == [0.01]
        assert cal["static_overrides"] == {"thicken_deadwood": 0.0}
        assert cal["target_dbh_per_cycle"] == [0.05]
        assert cal["flushes_per_year"] == 1.2

"""Tests for growpy.config.preset_overrides module."""

import json

import pytest

from growpy.config.preset_overrides import (
    InterpolatedOverride,
    PresetOverrides,
    StaticOverride,
    create_overrides_from_args,
    load_curves_from_preset,
    load_height_dbh_model_from_preset,
    load_target_dbh_from_preset,
    parse_curve_arg,
    parse_override_arg,
    predict_dbh_from_height_model,
)


class TestStaticOverride:
    """Tests for StaticOverride dataclass."""

    def test_creation(self):
        o = StaticOverride(param="drop_decay", value=0.1)
        assert o.param == "drop_decay"
        assert o.value == 0.1


class TestInterpolatedOverride:
    """Tests for InterpolatedOverride dataclass."""

    def test_defaults(self):
        o = InterpolatedOverride(param="drop_decay", start=0.0, end=0.3)
        assert o.easing == "linear"
        assert o.power == 2.0
        assert o.midpoint == 0.5
        assert o.midpoint_cycle is None
        assert o.transition_cycle is None


class TestPresetOverrides:
    """Tests for PresetOverrides container."""

    def test_add_static(self):
        overrides = PresetOverrides()
        overrides.add_static("drop_decay", 0.1)
        assert overrides.static_overrides["drop_decay"] == 0.1

    def test_add_static_chaining(self):
        overrides = PresetOverrides()
        result = overrides.add_static("drop_decay", 0.1).add_static("drop_weak", 0.2)
        assert result is overrides
        assert len(overrides.static_overrides) == 2

    def test_add_interpolated(self):
        overrides = PresetOverrides()
        overrides.add_interpolated("drop_decay", start=0.0, end=0.3)
        assert len(overrides.interpolated_overrides) == 1
        assert overrides.interpolated_overrides[0].param == "drop_decay"
        assert overrides.interpolated_overrides[0].start == 0.0
        assert overrides.interpolated_overrides[0].end == 0.3

    def test_add_cycle_array(self):
        overrides = PresetOverrides()
        overrides.add_cycle_array("grow_length", [1.0, 1.2, 1.5, 1.8])
        assert len(overrides.cycle_array_overrides) == 1
        assert overrides.cycle_array_overrides[0].values == [1.0, 1.2, 1.5, 1.8]


class TestInterpolation:
    """Tests for interpolated value calculation."""

    def test_linear_at_start(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="linear"
        )
        value = overrides.get_value_at_cycle(override, 0, 10)
        assert value == pytest.approx(0.0)

    def test_linear_at_end(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="linear"
        )
        value = overrides.get_value_at_cycle(override, 9, 10)
        assert value == pytest.approx(1.0)

    def test_linear_at_midpoint(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="linear"
        )
        value = overrides.get_value_at_cycle(override, 4, 9)
        assert value == pytest.approx(0.5)

    def test_linear_reverse(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=1.0, end=0.0, easing="linear"
        )
        value = overrides.get_value_at_cycle(override, 9, 10)
        assert value == pytest.approx(0.0)

    def test_single_cycle_returns_end(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="linear"
        )
        value = overrides.get_value_at_cycle(override, 0, 1)
        assert value == pytest.approx(1.0)

    def test_ease_in_slower_at_start(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="ease_in"
        )
        early = overrides.get_value_at_cycle(override, 2, 10)
        linear_early = 2.0 / 9.0
        assert early < linear_early

    def test_ease_out_faster_at_start(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="ease_out"
        )
        early = overrides.get_value_at_cycle(override, 2, 10)
        linear_early = 2.0 / 9.0
        assert early > linear_early

    def test_ease_in_out_reaches_endpoints(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="test", start=0.0, end=1.0, easing="ease_in_out"
        )
        start_val = overrides.get_value_at_cycle(override, 0, 10)
        end_val = overrides.get_value_at_cycle(override, 9, 10)
        assert start_val == pytest.approx(0.0)
        assert end_val == pytest.approx(1.0)


class TestGetAllOverridesAtCycle:
    """Tests for combined override resolution."""

    def test_static_only(self):
        overrides = PresetOverrides()
        overrides.add_static("drop_decay", 0.1)
        result = overrides.get_all_overrides_at_cycle(0, 10)
        assert result["drop_decay"] == 0.1

    def test_interpolated_overrides_static(self):
        overrides = PresetOverrides()
        overrides.add_static("drop_decay", 0.1)
        overrides.add_interpolated("drop_decay", start=0.0, end=0.5)
        result = overrides.get_all_overrides_at_cycle(9, 10)
        # Interpolated takes priority over static
        assert result["drop_decay"] == pytest.approx(0.5)

    def test_cycle_array_overrides_interpolated(self):
        overrides = PresetOverrides()
        overrides.add_interpolated("grow_length", start=0.5, end=1.5)
        overrides.add_cycle_array("grow_length", [0.8, 0.9, 1.0])
        result = overrides.get_all_overrides_at_cycle(1, 3)
        # Cycle array takes priority
        assert result["grow_length"] == pytest.approx(0.9)

    def test_cycle_array_repeats_last_value(self):
        overrides = PresetOverrides()
        overrides.add_cycle_array("grow_length", [0.8, 0.9])
        result = overrides.get_all_overrides_at_cycle(5, 10)
        assert result["grow_length"] == pytest.approx(0.9)

    def test_memoization(self):
        overrides = PresetOverrides()
        overrides.add_interpolated("test", start=0.0, end=1.0)
        result1 = overrides.get_all_overrides_at_cycle(0, 10)
        result2 = overrides.get_all_overrides_at_cycle(0, 10)
        assert result1 == result2

    def test_cache_invalidation_on_add(self):
        overrides = PresetOverrides()
        overrides.add_interpolated("a", start=0.0, end=1.0)
        overrides.get_all_overrides_at_cycle(0, 10)
        assert len(overrides._lookup_table) > 0
        overrides.add_static("b", 2.0)
        assert len(overrides._lookup_table) == 0


class TestIsEmpty:
    """Tests for PresetOverrides.is_empty()."""

    def test_empty(self):
        assert PresetOverrides().is_empty()

    def test_not_empty_static(self):
        overrides = PresetOverrides()
        overrides.add_static("x", 1.0)
        assert not overrides.is_empty()

    def test_not_empty_interpolated(self):
        overrides = PresetOverrides()
        overrides.add_interpolated("x", 0.0, 1.0)
        assert not overrides.is_empty()

    def test_not_empty_cycle_array(self):
        overrides = PresetOverrides()
        overrides.add_cycle_array("x", [1.0])
        assert not overrides.is_empty()


class TestParseOverrideArg:
    """Tests for parse_override_arg."""

    def test_valid(self):
        param, value = parse_override_arg("drop_decay=0.1")
        assert param == "drop_decay"
        assert value == pytest.approx(0.1)

    def test_negative_value(self):
        param, value = parse_override_arg("offset=-3.5")
        assert param == "offset"
        assert value == pytest.approx(-3.5)

    def test_integer_value(self):
        _, value = parse_override_arg("count=5")
        assert value == pytest.approx(5.0)

    def test_whitespace_in_param(self):
        param, _ = parse_override_arg("  drop_decay  =0.1")
        assert param == "drop_decay"

    def test_missing_equals(self):
        with pytest.raises(ValueError, match="Expected 'param=value'"):
            parse_override_arg("drop_decay0.1")

    def test_non_numeric_value(self):
        with pytest.raises(ValueError, match="Invalid value"):
            parse_override_arg("drop_decay=abc")


class TestParseCurveArg:
    """Tests for parse_curve_arg."""

    def test_basic(self):
        param, start, end, easing = parse_curve_arg("drop_decay=0.3:0.1")
        assert param == "drop_decay"
        assert start == pytest.approx(0.3)
        assert end == pytest.approx(0.1)
        assert easing == "linear"

    def test_with_easing(self):
        _, _, _, easing = parse_curve_arg("drop_decay=0.3:0.1:ease_out")
        assert easing == "ease_out"

    def test_all_easing_types(self):
        for e in ["linear", "ease_in", "ease_out", "ease_in_out"]:
            _, _, _, easing = parse_curve_arg(f"x=0:1:{e}")
            assert easing == e

    def test_missing_equals(self):
        with pytest.raises(ValueError, match="Expected 'param=start:end'"):
            parse_curve_arg("no_equals")

    def test_missing_colon(self):
        with pytest.raises(ValueError, match="Expected 'param=start:end"):
            parse_curve_arg("x=0.5")

    def test_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid numeric"):
            parse_curve_arg("x=abc:def")

    def test_invalid_easing(self):
        with pytest.raises(ValueError, match="Invalid easing"):
            parse_curve_arg("x=0:1:bounce")


class TestCreateOverridesFromArgs:
    """Tests for create_overrides_from_args."""

    def test_static_only(self):
        o = create_overrides_from_args(static_args=["a=1.0", "b=2.0"])
        assert o.static_overrides == {"a": 1.0, "b": 2.0}
        assert o.interpolated_overrides == []

    def test_curves_only(self):
        o = create_overrides_from_args(curve_args=["x=0:1:ease_in"])
        assert len(o.interpolated_overrides) == 1
        assert o.interpolated_overrides[0].easing == "ease_in"

    def test_both(self):
        o = create_overrides_from_args(
            static_args=["a=1.0"],
            curve_args=["b=0:1"],
        )
        assert "a" in o.static_overrides
        assert len(o.interpolated_overrides) == 1

    def test_none_args(self):
        o = create_overrides_from_args()
        assert o.is_empty()


class TestPredictDbhFromHeightModel:
    """Tests for predict_dbh_from_height_model."""

    def test_basic_power_model(self):
        model = {"a": 0.5, "b": 1.0}
        assert predict_dbh_from_height_model(10.0, model) == pytest.approx(5.0)

    def test_quadratic(self):
        model = {"a": 0.01, "b": 2.0}
        assert predict_dbh_from_height_model(10.0, model) == pytest.approx(1.0)

    def test_zero_height(self):
        model = {"a": 0.5, "b": 1.0}
        assert predict_dbh_from_height_model(0.0, model) == 0.0

    def test_negative_height(self):
        model = {"a": 0.5, "b": 1.0}
        assert predict_dbh_from_height_model(-5.0, model) == 0.0

    def test_small_height(self):
        model = {"a": 0.5, "b": 0.5}
        result = predict_dbh_from_height_model(0.01, model)
        assert result >= 0.0


class TestInterpolationAdvanced:
    """Tests for easing with power and midpoint parameters."""

    def test_ease_in_with_higher_power(self):
        overrides = PresetOverrides()
        low_power = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_in", power=2.0
        )
        high_power = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_in", power=4.0
        )
        low = overrides.get_value_at_cycle(low_power, 3, 10)
        high = overrides.get_value_at_cycle(high_power, 3, 10)
        assert high < low  # Higher power = slower at start

    def test_ease_out_with_higher_power(self):
        overrides = PresetOverrides()
        low_power = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_out", power=2.0
        )
        high_power = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_out", power=4.0
        )
        low = overrides.get_value_at_cycle(low_power, 3, 10)
        high = overrides.get_value_at_cycle(high_power, 3, 10)
        assert high > low  # Higher power = faster at start for ease_out

    def test_transition_cycle_ease_in(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_in",
            transition_cycle=5,
        )
        val_at_5 = overrides.get_value_at_cycle(override, 5, 10)
        assert 0.3 < val_at_5 < 0.7  # Should be near midpoint

    def test_midpoint_cycle_ease_in_out(self):
        overrides = PresetOverrides()
        override = InterpolatedOverride(
            param="t", start=0.0, end=1.0, easing="ease_in_out",
            midpoint_cycle=3,
        )
        val = overrides.get_value_at_cycle(override, 3, 10)
        assert 0.3 < val < 0.7  # Around midpoint value


class TestLoadCurvesFromPreset:
    """Tests for load_curves_from_preset with temp files."""

    def test_basic_curve(self, tmp_path):
        preset = {
            "drop_decay": 0.3,
            "drop_decay_curve": {
                "start": 0.0,
                "end": 0.3,
                "easing": "ease_in",
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        assert len(overrides.interpolated_overrides) == 1
        o = overrides.interpolated_overrides[0]
        assert o.param == "drop_decay"
        assert o.start == 0.0
        assert o.end == 0.3
        assert o.easing == "ease_in"

    def test_curve_with_power_and_midpoint(self, tmp_path):
        preset = {
            "drop_decay_curve": {
                "start": 0.0,
                "end": 0.5,
                "easing": "ease_in_out",
                "power": 3.0,
                "midpoint": 0.7,
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        o = overrides.interpolated_overrides[0]
        assert o.power == 3.0
        assert o.midpoint == 0.7

    def test_invalid_easing_defaults_to_linear(self, tmp_path):
        preset = {
            "x_curve": {"start": 0.0, "end": 1.0, "easing": "bounce"},
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        assert overrides.interpolated_overrides[0].easing == "linear"

    def test_yield_table_calibration(self, tmp_path):
        preset = {
            "grow_length": 0.3,
            "_yield_table_calibration": {
                "grow_length_per_cycle": [0.5, 0.4, 0.3, 0.2],
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        assert len(overrides.cycle_array_overrides) == 1
        assert overrides.cycle_array_overrides[0].param == "grow_length"

    def test_yield_table_floor(self, tmp_path):
        preset = {
            "grow_length": 0.3,
            "_yield_table_calibration": {
                "grow_length_per_cycle": [0.5, 0.01, 0.3],
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        vals = overrides.cycle_array_overrides[0].values
        floor = 0.3 * 0.5
        assert vals[1] >= floor

    def test_static_calibration_overrides(self, tmp_path):
        preset = {
            "_yield_table_calibration": {
                "static_overrides": {"thicken_base_scale": 1.5},
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        assert overrides.static_overrides["thicken_base_scale"] == 1.5

    def test_missing_file_returns_empty(self, tmp_path):
        overrides = load_curves_from_preset(tmp_path / "missing.json")
        assert overrides.is_empty()

    def test_no_curves_returns_empty(self, tmp_path):
        preset = {"drop_decay": 0.3, "grow_length": 0.5}
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        overrides = load_curves_from_preset(p)
        assert overrides.is_empty()


class TestLoadTargetDbhFromPreset:
    """Tests for load_target_dbh_from_preset."""

    def test_with_data(self, tmp_path):
        preset = {
            "_yield_table_calibration": {
                "target_dbh_per_cycle": [0.05, 0.10, 0.15],
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        result = load_target_dbh_from_preset(p)
        assert result == [0.05, 0.10, 0.15]

    def test_missing_file(self, tmp_path):
        assert load_target_dbh_from_preset(tmp_path / "missing.json") == []

    def test_no_calibration(self, tmp_path):
        preset = {"grow_length": 0.3}
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        assert load_target_dbh_from_preset(p) == []


class TestLoadHeightDbhModelFromPreset:
    """Tests for load_height_dbh_model_from_preset."""

    def test_with_model(self, tmp_path):
        preset = {
            "_yield_table_calibration": {
                "height_dbh_model": {"a": 0.5, "b": 0.8},
            },
        }
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        result = load_height_dbh_model_from_preset(p)
        assert result == {"a": 0.5, "b": 0.8}

    def test_missing_file(self, tmp_path):
        assert load_height_dbh_model_from_preset(tmp_path / "missing.json") is None

    def test_no_model(self, tmp_path):
        preset = {"_yield_table_calibration": {}}
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        assert load_height_dbh_model_from_preset(p) is None

    def test_incomplete_model(self, tmp_path):
        preset = {"_yield_table_calibration": {"height_dbh_model": {"a": 0.5}}}
        p = tmp_path / "test.seed.json"
        p.write_text(json.dumps(preset))
        assert load_height_dbh_model_from_preset(p) is None

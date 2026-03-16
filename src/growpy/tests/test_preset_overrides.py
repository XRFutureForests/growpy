"""Tests for growpy.config.preset_overrides module."""

import pytest

from growpy.config.preset_overrides import (
    CycleArrayOverride,
    InterpolatedOverride,
    PresetOverrides,
    StaticOverride,
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

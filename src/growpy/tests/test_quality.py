"""Tests for growpy.config.quality module."""

import pytest

from growpy.config.quality import _DEFAULT, get_quality_preset


class TestDefaultPreset:
    """Tests for the default quality preset values."""

    def test_default_resolution(self):
        assert _DEFAULT["resolution"] == 16

    def test_default_resolution_reduce(self):
        assert _DEFAULT["resolution_reduce"] == 0.78

    def test_default_skeleton_length(self):
        assert _DEFAULT["skeleton_length"] == 2.0

    def test_default_build_cutoff_age(self):
        assert _DEFAULT["build_cutoff_age"] == 0

    def test_default_build_cutoff_thickness(self):
        assert _DEFAULT["build_cutoff_thickness"] == 0.0

    def test_default_build_blend(self):
        assert _DEFAULT["build_blend"] is True

    def test_default_build_end_cap(self):
        assert _DEFAULT["build_end_cap"] is True


class TestGetQualityPreset:
    """Tests for get_quality_preset function."""

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown quality preset"):
            get_quality_preset("nonexistent_preset_xyz")

    def test_preset_has_required_keys(self):
        # Uses default preset when no TOML is found
        try:
            preset = get_quality_preset("default")
        except ValueError:
            pytest.skip("No quality presets available without TOML")
            return

        required_keys = [
            "resolution",
            "resolution_reduce",
            "build_cutoff_age",
            "build_cutoff_thickness",
            "skeleton_length",
        ]
        for key in required_keys:
            assert key in preset

    def test_preset_values_are_numeric(self):
        try:
            preset = get_quality_preset("default")
        except ValueError:
            pytest.skip("No quality presets available without TOML")
            return

        assert isinstance(preset["resolution"], (int, float))
        assert isinstance(preset["skeleton_length"], (int, float))

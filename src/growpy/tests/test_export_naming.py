"""Tests for growpy.utils.export_naming module and density variant config."""

import pytest

from growpy.config.core import GrowPyConfig
from growpy.utils.export_naming import (
    format_dbh_for_filename,
    format_density_for_filename,
    format_height_for_filename,
)


class TestFormatHeightForFilename:
    """Tests for height formatting in filenames."""

    @pytest.mark.parametrize(
        "height_m,expected",
        [
            (15.0, "h15m"),
            (5.0, "h05m"),
            (30.0, "h30m"),
            (0.5, "h00m"),
            (14.7, "h15m"),
            (14.4, "h14m"),
            (1.0, "h01m"),
        ],
    )
    def test_height_formatting(self, height_m, expected):
        assert format_height_for_filename(height_m) == expected


class TestFormatDbhForFilename:
    """Tests for DBH formatting in filenames."""

    @pytest.mark.parametrize(
        "dbh_m,expected",
        [
            (0.32, "d32cm"),
            (0.10, "d10cm"),
            (0.05, "d05cm"),
            (1.0, "d100cm"),
            (0.001, "d00cm"),
            (0.325, "d32cm"),
        ],
    )
    def test_dbh_formatting(self, dbh_m, expected):
        assert format_dbh_for_filename(dbh_m) == expected


class TestFormatDensityForFilename:
    """Tests for density label mapping."""

    @pytest.mark.parametrize(
        "twig_density,expected",
        [
            (None, "full"),
            (1.0, "full"),
            (0.9, "full"),
            (0.95, "full"),
            (0.5, "reduced"),
            (0.3, "reduced"),
            (0.1, "reduced"),
            (0.01, "bare"),
            (0.0, "bare"),
            (0.005, "bare"),
        ],
    )
    def test_density_formatting(self, twig_density, expected):
        assert format_density_for_filename(twig_density) == expected


class TestDensityVariantConfig:
    """Tests for density variant configuration."""

    def test_empty_variants_returns_empty(self):
        config = GrowPyConfig(export_density_variants=[])
        assert config.get_density_variants() == []

    def test_default_returns_empty(self):
        config = GrowPyConfig()
        assert config.get_density_variants() == []

    def test_defined_variants_returned(self):
        config = GrowPyConfig(
            export_density_variants=["full", "bare"],
            density_variant_defs={
                "full": {"twig_density": 1.0},
                "bare": {"twig_density": 0.0, "build_cutoff_thickness": 0.02},
            },
        )
        variants = config.get_density_variants()
        assert len(variants) == 2
        assert variants[0][0] == "full"
        assert variants[0][1]["twig_density"] == 1.0
        assert variants[1][0] == "bare"
        assert variants[1][1]["twig_density"] == 0.0
        assert variants[1][1]["build_cutoff_thickness"] == 0.02

    def test_undefined_variant_raises(self):
        config = GrowPyConfig(
            export_density_variants=["full", "missing"],
            density_variant_defs={"full": {"twig_density": 1.0}},
        )
        with pytest.raises(ValueError, match="missing"):
            config.get_density_variants()

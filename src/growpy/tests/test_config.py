"""Tests for growpy.config.core module."""

from pathlib import Path

import pytest

from growpy.config.core import (
    GrowPyConfig,
    _find_config_dir,
    get_global_config,
    set_global_config,
)


class TestGrowPyConfigDefaults:
    """Tests for GrowPyConfig dataclass defaults."""

    def test_default_random_seed(self):
        config = GrowPyConfig()
        assert config.random_seed == 42

    def test_default_csv_file(self):
        config = GrowPyConfig()
        assert config.csv_file == Path("data/input/test.csv")

    def test_default_output_dir(self):
        config = GrowPyConfig()
        assert config.output_dir == Path("data/output/forest")

    def test_default_verbose_false(self):
        config = GrowPyConfig()
        assert config.verbose is False

    def test_default_profile_false(self):
        config = GrowPyConfig()
        assert config.profile is False

    def test_default_forest_quality(self):
        config = GrowPyConfig()
        assert config.forest_quality == "high"

    def test_default_export_skeletal(self):
        config = GrowPyConfig()
        assert config.export_skeletal is True

    def test_default_export_static(self):
        config = GrowPyConfig()
        assert config.export_static is False

    def test_default_export_twig_density_is_none(self):
        config = GrowPyConfig()
        assert config.export_twig_density is None

    def test_default_export_twig_density_conifer(self):
        config = GrowPyConfig()
        assert config.export_twig_density_conifer == 1.0

    def test_default_export_twig_density_broadleaf(self):
        config = GrowPyConfig()
        assert config.export_twig_density_broadleaf == 2.5

    def test_default_growth_models_cycles(self):
        config = GrowPyConfig()
        assert config.growth_models_cycles == 25

    def test_default_calibration_enabled(self):
        config = GrowPyConfig()
        assert config.calibration_enabled is True


class TestGrowPyConfigFromToml:
    """Tests for loading config from TOML files."""

    def test_load_from_toml(self, tmp_path):
        toml_content = b"""
[general]
random_seed = 99
verbose = true

[forest]
quality = "low"
growth_cycle_limit = 30
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.random_seed == 99
        assert config.verbose is True
        assert config.forest_quality == "low"
        assert config.forest_growth_cycle_limit == 30

    def test_toml_preserves_defaults_for_missing_keys(self, tmp_path):
        toml_content = b"""
[general]
verbose = true
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.verbose is True
        assert config.random_seed == 42  # default preserved
        assert config.forest_quality == "high"  # default preserved


class TestGrowPyConfigSurroundSection:
    """Tests for [surround] radii parsing."""

    def test_default_surround_radii(self):
        config = GrowPyConfig()
        assert config.surround_radii == [0.0]

    def test_loads_configured_radii_sorted(self, tmp_path):
        toml_content = b"""
[surround]
radii = [15.0, 0.0, 7.0]
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.surround_radii == [0.0, 7.0, 15.0]

    def test_zero_radius_always_included(self, tmp_path):
        toml_content = b"""
[surround]
radii = [7.0, 15.0]
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.surround_radii == [0.0, 7.0, 15.0]

    def test_surround_shape_params(self, tmp_path):
        toml_content = b"""
[surround]
radii = [0.0, 7.0]
density = 0.6
height = 4.0
grow = false
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.surround_density == pytest.approx(0.6)
        assert config.surround_height == pytest.approx(4.0)
        assert config.surround_grow is False

    def test_toml_export_section(self, tmp_path):
        toml_content = b"""
[export]
skeletal = false
static = true
twig_density = 0.5
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_skeletal is False
        assert config.export_static is True
        assert config.export_twig_density == 0.5

    def test_toml_export_twig_density_conifer_broadleaf(self, tmp_path):
        toml_content = b"""
[export]
twig_density_conifer = 0.8
twig_density_broadleaf = 3.0
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_twig_density is None
        assert config.export_twig_density_conifer == 0.8
        assert config.export_twig_density_broadleaf == 3.0

    def test_toml_density_variants(self, tmp_path):
        toml_content = b"""
[export]
density_variants = ["full", "bare"]

[density_variant.full]
twig_density = 1.0

[density_variant.bare]
twig_density = 0.0
build_cutoff_thickness = 0.02
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_density_variants == ["full", "bare"]
        assert config.density_variant_defs["full"]["twig_density"] == 1.0
        assert config.density_variant_defs["bare"]["twig_density"] == 0.0

    def test_toml_calibration_species(self, tmp_path):
        toml_content = b"""
[calibration]
enabled = true

[calibration.species."European beech"]
table_id = 123
yield_class = "II"
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.calibration_enabled is True
        assert "European beech" in config.calibration_species
        assert config.calibration_species["European beech"]["table_id"] == 123


class TestGrowPyConfigResolve:
    """Tests for CLI argument resolution over config values."""

    def test_resolve_overrides_non_none(self):
        config = GrowPyConfig()

        class Args:
            verbose = True
            csv_file = None
            output_dir = None
            profile = None

        config.resolve(Args())
        assert config.verbose is True

    def test_resolve_preserves_config_when_none(self):
        config = GrowPyConfig(verbose=True)

        class Args:
            verbose = None

        config.resolve(Args())
        assert config.verbose is True


class TestGlobalConfig:
    """Tests for global config singleton management."""

    def setup_method(self):
        set_global_config(None)

    def test_set_and_get_global_config(self):
        config = GrowPyConfig(random_seed=123)
        set_global_config(config)
        assert get_global_config() is config
        assert get_global_config().random_seed == 123

    def test_global_config_initially_none(self):
        assert get_global_config() is None

    def teardown_method(self):
        set_global_config(None)


class TestFindConfigDir:
    """Tests for config directory discovery."""

    def test_env_var_file_resolves_to_parent_dir(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "custom.toml"
        toml_file.write_bytes(b"[general]\n")
        monkeypatch.setenv("GROWPY_CONFIG", str(toml_file))
        assert _find_config_dir() == tmp_path

    def test_env_var_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GROWPY_CONFIG", str(tmp_path))
        assert _find_config_dir() == tmp_path

    def test_env_var_nonexistent_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROWPY_CONFIG", "/nonexistent/path.toml")
        assert _find_config_dir() is None


class TestDensityVariants:
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

    def test_undefined_variant_raises(self):
        config = GrowPyConfig(
            export_density_variants=["full", "missing"],
            density_variant_defs={"full": {"twig_density": 1.0}},
        )
        with pytest.raises(ValueError, match="missing"):
            config.get_density_variants()



class TestGetTwigDensityBase:
    """Tests for GrowPyConfig.get_twig_density_base species-type resolution."""

    def test_explicit_override_wins_for_any_species(self, monkeypatch):
        config = GrowPyConfig(export_twig_density=0.7)
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: "broadleaf"
        )
        assert config.get_twig_density_base("European beech") == 0.7

    def test_broadleaf_species_uses_broadleaf_default(self, monkeypatch):
        config = GrowPyConfig()
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: "broadleaf"
        )
        assert config.get_twig_density_base("European beech") == 2.5

    def test_conifer_species_uses_conifer_default(self, monkeypatch):
        config = GrowPyConfig()
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: "conifer"
        )
        assert config.get_twig_density_base("Norway spruce") == 1.0

    def test_unclassified_species_falls_back_to_conifer_default(self, monkeypatch):
        config = GrowPyConfig()
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: None
        )
        assert config.get_twig_density_base("Unknown species") == 1.0

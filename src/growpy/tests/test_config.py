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

    def test_default_export_previews(self):
        config = GrowPyConfig()
        assert config.export_previews is True

    def test_default_export_control_images(self):
        config = GrowPyConfig()
        assert config.export_control_images is True

    def test_default_export_icons(self):
        config = GrowPyConfig()
        assert config.export_icons is True

    def test_default_export_twig_density_is_natural(self):
        # 1.0 == Grove's natural density, since cutoff losses are now recovered
        # rather than compensated for by a multiplier.
        config = GrowPyConfig()
        assert config.export_twig_density == 1.0

    def test_default_twig_reattach_threshold(self):
        config = GrowPyConfig()
        assert config.export_twig_reattach_threshold == 0.01

    def test_default_growth_models_cycles(self):
        config = GrowPyConfig()
        assert config.growth_models_cycles == 25

    def test_calibration_off_by_default(self):
        """Growth-pacing calibration is opt-in: it costs two Grove passes per
        species and only matters for multi-tree co-growth, not for dataset
        production, which grows trees to height milestones."""
        config = GrowPyConfig()
        assert config.calibration_enabled is False

    def test_dbh_from_allometry_on_by_default(self):
        """DBH realisation is independent of calibration -- its input is the
        allometry artifact, which needs no simulation."""
        config = GrowPyConfig()
        assert config.export_dbh_from_allometry is True


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

    def test_toml_export_previews_and_icons(self, tmp_path):
        toml_content = b"""
[export]
previews = false
export_control = false
icons = false
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_previews is False
        assert config.export_control_images is False
        assert config.export_icons is False

    def test_toml_retired_per_habit_density_keys_raise(self, tmp_path):
        # These were hand-set guesses at the cutoff loss. Failing loudly beats
        # silently ignoring them and shipping a crown at the wrong density.
        for key in ("twig_density_conifer", "twig_density_broadleaf"):
            toml_file = tmp_path / f"growpy_{key}.toml"
            toml_file.write_bytes(f"[export]\n{key} = 0.8\n".encode())
            with pytest.raises(ValueError, match="was retired"):
                GrowPyConfig.from_toml(toml_file, set_as_global=False)

    def test_toml_twig_reattach_threshold(self, tmp_path):
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(b"[export]\ntwig_reattach_threshold = 0.05\n")
        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_twig_reattach_threshold == 0.05

    def test_toml_export_mode_helios(self, tmp_path):
        toml_content = b"""
[export]
mode = "helios"
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.export_mode == "helios"

    def test_toml_export_mode_default_is_unreal(self):
        assert GrowPyConfig().export_mode == "unreal"

    def test_toml_export_mode_rejects_invalid_value(self, tmp_path):
        toml_content = b"""
[export]
mode = "bogus"
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        with pytest.raises(ValueError, match="export.mode"):
            GrowPyConfig.from_toml(toml_file, set_as_global=False)

    def test_toml_helios_simplification_per_species(self, tmp_path):
        toml_content = b"""
[helios.simplification]
enabled = true
bark = 0.2
wood = 0.2
leaf = 0.5
fruit = 0.2

[helios.simplification.per_species.selected_european_oak]
bark = 0.1
wood = 0.05
leaf = 0.25
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.helios_simplification_enabled is True
        assert config.helios_simplification_per_species == {
            "selected_european_oak": {"bark": 0.1, "wood": 0.05, "leaf": 0.25}
        }

    def test_toml_helios_simplification_leaf_per_species_ignored_with_warning(
        self, tmp_path, caplog
    ):
        toml_content = b"""
[helios.simplification]
enabled = true
leaf_per_species = { selected_european_beech = 0.2 }
"""
        toml_file = tmp_path / "growpy.toml"
        toml_file.write_bytes(toml_content)

        config = GrowPyConfig.from_toml(toml_file, set_as_global=False)
        assert config.helios_simplification_per_species == {}
        assert "leaf_per_species" in caplog.text

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

    def test_resolve_cli_false_overrides_toml_true(self):
        """A bool config field defaulting True can be forced False from the CLI."""
        config = GrowPyConfig(export_skeletal=True)

        class Args:
            skeletal = False

        config.resolve(Args())
        assert config.export_skeletal is False

    def test_resolve_cli_true_overrides_toml_false(self):
        """A bool config field defaulting False can be forced True from the CLI."""
        config = GrowPyConfig(export_static=False)

        class Args:
            static = True

        config.resolve(Args())
        assert config.export_static is True

    def test_resolve_no_flag_keeps_toml_value(self):
        """Omitting the flag (None) leaves the TOML/default value untouched."""
        config = GrowPyConfig(export_skeletal=False)

        class Args:
            skeletal = None

        config.resolve(Args())
        assert config.export_skeletal is False

    def test_resolve_densify_maps_to_twigs_densify(self):
        """--densify/--no-densify now goes through the generic mapping, replacing
        the old no_densify special case."""
        config = GrowPyConfig(twigs_densify=True)

        class Args:
            densify = False

        config.resolve(Args())
        assert config.twigs_densify is False


class TestCliMappingsConsistency:
    """Regression guard for the resolve() CLI_MAPPINGS drift found in the
    2026-07-31 growpy review (XRFF-292): a mapping pointing at a CLI arg no
    parser defines, or the reverse -- a TOML-settable field with no CLI
    override and no acknowledgment that this is intentional.
    """

    @staticmethod
    def _cli_defined_dests() -> set[str]:
        """Every argparse dest (or positional arg name) defined in cli/*.py."""
        import ast
        from pathlib import Path

        cli_dir = Path(__file__).resolve().parents[1] / "cli"
        dests: set[str] = set()
        for path in cli_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"
                ):
                    continue
                dest = None
                option_strings = []
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.startswith("--"):
                            option_strings.append(arg.value)
                        elif not arg.value.startswith("-"):
                            dest = arg.value
                for kw in node.keywords:
                    if kw.arg == "dest" and isinstance(kw.value, ast.Constant):
                        dest = kw.value.value
                if dest is None and option_strings:
                    dest = option_strings[-1].lstrip("-").replace("-", "_")
                if dest:
                    dests.add(dest)
        return dests

    @staticmethod
    def _toml_settable_fields() -> set[str]:
        """Every GrowPyConfig field from_toml() can populate, found from its
        ``kwargs["field_name"] = ...`` assignment targets."""
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(GrowPyConfig.from_toml))
        tree = ast.parse(source)
        fields: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
                if isinstance(node.value, ast.Name) and node.value.id == "kwargs":
                    key = node.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        fields.add(key.value)
        return fields

    def test_cli_mappings_keys_have_backing_cli_arg(self):
        cli_dests = self._cli_defined_dests()
        orphans = set(GrowPyConfig.CLI_MAPPINGS) - cli_dests
        assert not orphans, (
            f"CLI_MAPPINGS keys with no backing CLI parser: {sorted(orphans)}"
        )

    def test_toml_settable_fields_have_mapping_or_are_allowlisted(self):
        toml_fields = self._toml_settable_fields()
        covered = set(GrowPyConfig.CLI_MAPPINGS.values()) | set(
            GrowPyConfig.TOML_ONLY_FIELDS
        )
        uncovered = toml_fields - covered
        assert not uncovered, (
            f"TOML-settable fields with no CLI_MAPPINGS entry and no "
            f"TOML_ONLY_FIELDS allowlist reason: {sorted(uncovered)}"
        )

    def test_toml_only_fields_are_not_also_cli_mapped(self):
        """An allowlist entry claiming 'no CLI override' should actually have none."""
        overlap = set(GrowPyConfig.TOML_ONLY_FIELDS) & set(
            GrowPyConfig.CLI_MAPPINGS.values()
        )
        assert not overlap, f"Fields both allowlisted and CLI-mapped: {sorted(overlap)}"


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

    def test_unknown_key_raises(self):
        """XRFF-288: an unrecognized override key would otherwise silently
        do nothing, so it must fail loudly at config-load time instead."""
        config = GrowPyConfig(
            export_density_variants=["bare"],
            density_variant_defs={"bare": {"twig_density": 0.0, "typo_key": 1.0}},
        )
        with pytest.raises(ValueError, match="typo_key"):
            config.get_density_variants()

    def test_valid_keys_do_not_raise(self):
        config = GrowPyConfig(
            export_density_variants=["bare"],
            density_variant_defs={
                "bare": {
                    "twig_density": 0.0,
                    "build_cutoff_age": 5,
                    "build_cutoff_thickness": 0.02,
                }
            },
        )
        variants = config.get_density_variants()
        assert variants[0][0] == "bare"


class TestGetTwigDensityBase:
    """get_twig_density_base is now species-independent.

    The per-habit constants it used to resolve existed only to guess at the twig
    loss from build_cutoff_thickness. Recovery restores those twigs exactly, per
    tree, so the multiplier is purely artistic and must not vary by species.
    """

    def test_returns_configured_density(self):
        config = GrowPyConfig(export_twig_density=0.7)
        assert config.get_twig_density_base("European beech") == 0.7

    def test_default_is_natural_density(self):
        assert GrowPyConfig().get_twig_density_base("European oak") == 1.0

    def test_identical_across_growth_habits(self, monkeypatch):
        # Would have returned 2.5 vs 1.0 before; a beech and a spruce must now
        # get the same multiplier, because each tree self-calibrates.
        config = GrowPyConfig(export_twig_density=1.3)
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: "broadleaf"
        )
        broadleaf = config.get_twig_density_base("European beech")
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: "conifer"
        )
        assert config.get_twig_density_base("Norway spruce") == broadleaf == 1.3

    def test_unclassified_species_resolves(self, monkeypatch):
        config = GrowPyConfig(export_twig_density=0.9)
        monkeypatch.setattr(
            "growpy.config.paths.get_species_growth_habit", lambda species: None
        )
        assert config.get_twig_density_base("Unknown species") == 0.9


class TestGetSimplificationRatios:
    """Tests for GrowPyConfig.get_simplification_ratios per-species merge."""

    def test_unlisted_species_returns_all_globals(self):
        config = GrowPyConfig(
            helios_simplification_ratios={
                "bark": 0.2,
                "wood": 0.2,
                "leaf": 0.5,
                "fruit": 0.2,
            }
        )
        assert config.get_simplification_ratios("selected_scots_pine") == {
            "bark": 0.2,
            "wood": 0.2,
            "leaf": 0.5,
            "fruit": 0.2,
        }

    def test_per_species_override_merges_over_globals(self):
        config = GrowPyConfig(
            helios_simplification_ratios={
                "bark": 0.2,
                "wood": 0.2,
                "leaf": 0.5,
                "fruit": 0.2,
            },
            helios_simplification_per_species={
                "selected_european_oak": {"bark": 0.1},
            },
        )
        assert config.get_simplification_ratios("selected_european_oak") == {
            "bark": 0.1,
            "wood": 0.2,
            "leaf": 0.5,
            "fruit": 0.2,
        }

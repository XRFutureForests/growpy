"""Tests for growpy.config.paths module."""

from unittest.mock import patch

import pandas as pd
import pytest

from growpy.config.paths import (
    _find_species_row,
    _get_lookup_table,
    _normalize_grove_texture_name,
    assembly_glob,
    get_species_growth_habit,
    static_assembly_glob,
    stems_path,
    tree_ext,
    tree_output_dir,
    twig_ext,
)


class TestNormalizeGroveTextureName:
    """Tests for _normalize_grove_texture_name."""

    def test_simple_name_with_number(self):
        assert _normalize_grove_texture_name("Beech60.jpg") == ("beech_60", ".jpg")

    def test_multi_word_camel_case(self):
        stem, ext = _normalize_grove_texture_name("BaldCypress80.jpg")
        assert stem == "bald_cypress_80"
        assert ext == ".jpg"

    def test_no_number(self):
        stem, ext = _normalize_grove_texture_name("OakBark.png")
        assert stem == "oak_bark"
        assert ext == ".png"

    def test_single_word_lowercase(self):
        stem, ext = _normalize_grove_texture_name("birch.jpg")
        assert stem == "birch"
        assert ext == ".jpg"

    def test_single_letter_variant_code_not_split_from_number(self):
        # "MapleA60" is Maple + variant code "A60", not a species word ending
        # in letters directly before digits (c.f. Ash70 -> ash_70). The
        # asset on disk is maple_a60_bark.jpg, not maple_a_60_bark.jpg.
        stem, ext = _normalize_grove_texture_name("MapleA60.jpg")
        assert stem == "maple_a60"
        assert ext == ".jpg"

    def test_png_extension(self):
        _, ext = _normalize_grove_texture_name("SomeTex.png")


def _make_lookup_df():
    """Create a minimal lookup DataFrame for testing."""
    return pd.DataFrame(
        {
            "Common Name": ["European Beech", "Norway Spruce", "Silver Birch"],
            "Standardized Name": ["european_beech", "norway_spruce", "silver_birch"],
            "Scientific Name": [
                "Fagus sylvatica",
                "Picea abies",
                "Betula pendula",
            ],
            "Aliases": ["beech,fagus", "spruce", "birch,white birch"],
        }
    )


class TestFindSpeciesRow:
    """Tests for _find_species_row with mocked lookup table."""

    @patch("growpy.config.paths._get_lookup_table")
    def test_match_common_name(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        row = _find_species_row("European Beech", use_gbif=False)
        assert row["Common Name"] == "European Beech"

    @patch("growpy.config.paths._get_lookup_table")
    def test_match_common_name_case_insensitive(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        row = _find_species_row("european beech", use_gbif=False)
        assert row["Common Name"] == "European Beech"

    @patch("growpy.config.paths._get_lookup_table")
    def test_match_standardized_name(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        row = _find_species_row("norway_spruce", use_gbif=False)
        assert row["Common Name"] == "Norway Spruce"

    @patch("growpy.config.paths._get_lookup_table")
    def test_match_scientific_name(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        row = _find_species_row("Fagus sylvatica", use_gbif=False)
        assert row["Common Name"] == "European Beech"

    @patch("growpy.config.paths._get_lookup_table")
    def test_match_alias(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        row = _find_species_row("white birch", use_gbif=False)
        assert row["Common Name"] == "Silver Birch"

    @patch("growpy.config.paths._get_lookup_table")
    def test_not_found_raises(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df()
        _get_lookup_table.cache_clear()
        with pytest.raises(ValueError, match="not found"):
            _find_species_row("Douglas Fir", use_gbif=False)


class TestNormalizeGroveTextureNameExtra:
    """Additional texture name normalization tests."""

    def test_png_extension(self):
        _, ext = _normalize_grove_texture_name("SomeTex.png")
        assert ext == ".png"

    def test_multiple_numbers(self):
        stem, ext = _normalize_grove_texture_name("Pine120Bark.jpg")
        assert "pine" in stem
        assert "120" in stem
        assert ext == ".jpg"

    def test_already_snake_case(self):
        stem, _ = _normalize_grove_texture_name("some_texture.jpg")
        assert stem == "some_texture"



def _make_lookup_df_with_competition_group():
    return pd.DataFrame(
        {
            "Common Name": ["European Beech", "Norway Spruce", "Silver Birch"],
            "Standardized Name": ["european_beech", "norway_spruce", "silver_birch"],
            "Scientific Name": ["Fagus sylvatica", "Picea abies", "Betula pendula"],
            "Aliases": ["beech,fagus", "spruce", "birch,white birch"],
            "Competition Group": ["slow_broadleaf", "slow_conifer", float("nan")],
        }
    )


class TestGetSpeciesGrowthHabit:
    """Tests for get_species_growth_habit."""

    @patch("growpy.config.paths._get_lookup_table")
    def test_broadleaf_species(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df_with_competition_group()
        _get_lookup_table.cache_clear()
        assert get_species_growth_habit("European Beech") == "broadleaf"

    @patch("growpy.config.paths._get_lookup_table")
    def test_conifer_species(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df_with_competition_group()
        _get_lookup_table.cache_clear()
        assert get_species_growth_habit("Norway Spruce") == "conifer"

    @patch("growpy.config.paths._get_lookup_table")
    def test_missing_competition_group_returns_none(self, mock_lookup):
        mock_lookup.return_value = _make_lookup_df_with_competition_group()
        _get_lookup_table.cache_clear()
        assert get_species_growth_habit("Silver Birch") is None


class _FakeConfig:
    """Minimal stand-in for GrowPyConfig -- resolvers only read export_usd_format."""

    def __init__(self, export_usd_format: str):
        self.export_usd_format = export_usd_format


class TestTreeAndTwigExt:
    """tree_ext follows config; twig_ext is always .usda."""

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_tree_ext_follows_config(self, fmt):
        assert tree_ext(_FakeConfig(fmt)) == f".{fmt}"

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_twig_ext_always_usda(self, fmt):
        assert twig_ext(_FakeConfig(fmt)) == ".usda"


class TestAssemblyGlobs:
    """assembly_glob / static_assembly_glob track tree_ext, not twig_ext,
    and must not hardcode a density-variant label.
    """

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_assembly_glob(self, fmt):
        assert assembly_glob(_FakeConfig(fmt)) == f"*_assembly.{fmt}"

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_static_assembly_glob(self, fmt):
        assert static_assembly_glob(_FakeConfig(fmt)) == f"*_assembly_static.{fmt}"

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_assembly_glob_matches_both_layouts_and_density_labels(self, fmt, tmp_path):
        config = _FakeConfig(fmt)
        dataset_dir = tmp_path / "european_oak" / "r00"
        layout_dir = tmp_path / "european_oak" / "tree_0007"
        dataset_dir.mkdir(parents=True)
        layout_dir.mkdir(parents=True)
        (dataset_dir / f"European_Oak_r00_h05m_d04cm_full_assembly.{fmt}").write_text("x")
        (dataset_dir / f"European_Oak_r00_h12m_d18cm_dense_assembly.{fmt}").write_text("x")
        (layout_dir / f"european_oak_h05m_d04cm_full_assembly.{fmt}").write_text("x")
        (dataset_dir / f"some_other_file.{fmt}").write_text("x")

        matches = sorted((tmp_path / "european_oak").rglob(assembly_glob(config)))
        assert len(matches) == 3


class TestStemsPath:
    """stems_path resolves skeletal/static x both extensions."""

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    @pytest.mark.parametrize("kind", ["skeletal", "static"])
    def test_stems_path(self, kind, fmt, tmp_path):
        config = _FakeConfig(fmt)
        result = stems_path(tmp_path, "european_beech_h15m_d10cm", kind, config)
        assert result == tmp_path / f"european_beech_h15m_d10cm_stems_{kind}.{fmt}"

    def test_stems_path_rejects_invalid_kind(self, tmp_path):
        with pytest.raises(ValueError, match="kind must be"):
            stems_path(tmp_path, "base", "solid", _FakeConfig("usda"))


class TestTreeOutputDir:
    """tree_output_dir picks dataset-mode vs layout-mode shape."""

    def test_dataset_mode_uses_radius_label(self, tmp_path):
        result = tree_output_dir(tmp_path, "european_oak", radius=8.0)
        assert result == tmp_path / "european_oak" / "r08"

    def test_layout_mode_uses_zero_padded_fid(self, tmp_path):
        result = tree_output_dir(tmp_path, "european_oak", fid=7)
        assert result == tmp_path / "european_oak" / "tree_0007"

    def test_requires_exactly_one_of_radius_or_fid(self, tmp_path):
        with pytest.raises(ValueError, match="exactly one"):
            tree_output_dir(tmp_path, "european_oak")
        with pytest.raises(ValueError, match="exactly one"):
            tree_output_dir(tmp_path, "european_oak", radius=8.0, fid=7)

"""Tests for growpy.config.paths module."""

from unittest.mock import patch

import pandas as pd
import pytest

from growpy.config.paths import (
    _find_species_row,
    _get_lookup_table,
    _normalize_grove_texture_name,
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

"""Tests for growpy.utils.naming module."""

import pytest

from growpy.utils.naming import (
    camel_to_snake,
    standardize_species_name,
    standardize_twig_name,
)


class TestCamelToSnake:
    """Tests for CamelCase to snake_case conversion."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("EuropeanBeechTwig", "european_beech_twig"),
            ("NorthernRedOak60", "northern_red_oak_60"),
            ("BaldCypress80", "bald_cypress_80"),
            ("Beech60", "beech_60"),
            ("PacificSilverFirTwig", "pacific_silver_fir_twig"),
            ("ScotsPine", "scots_pine"),
            ("NorwaySpruce", "norway_spruce"),
            ("SilverBirch", "silver_birch"),
            ("Oak", "oak"),
            ("MapleC65", "maple_c65"),
            ("LondonPlaneTwig", "london_plane_twig"),
            ("MediterraneanStonePine", "mediterranean_stone_pine"),
        ],
    )
    def test_camel_to_snake(self, input_name, expected):
        assert camel_to_snake(input_name) == expected

    def test_already_snake_case(self):
        assert camel_to_snake("already_snake") == "already_snake"

    def test_single_word(self):
        assert camel_to_snake("Beech") == "beech"

    def test_empty_string(self):
        assert camel_to_snake("") == ""


class TestStandardizeSpeciesName:
    """Tests for species name standardization."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("European beech", "european_beech"),
            ("Norway spruce", "norway_spruce"),
            ("Red oak", "red_oak"),
            ("Silver birch", "silver_birch"),
            ("Scots pine", "scots_pine"),
            ("London plane", "london_plane"),
            ("Mediterranean stone pine", "mediterranean_stone_pine"),
            ("Bald cypress", "bald_cypress"),
            ("Paper Birch", "paper_birch"),
            ("Douglas fir", "douglas_fir"),
        ],
    )
    def test_species_names(self, input_name, expected):
        assert standardize_species_name(input_name) == expected

    def test_already_standardized(self):
        assert standardize_species_name("european_beech") == "european_beech"

    def test_extra_whitespace(self):
        assert standardize_species_name("  European  beech  ") == "european_beech"

    def test_hyphens(self):
        assert standardize_species_name("some-species") == "some_species"


class TestStandardizeTwigName:
    """Tests for twig name standardization."""

    def test_apical_twig(self):
        name, meta = standardize_twig_name("BeechApicalTwig", "beech")
        assert name == "beech_apical"
        assert meta["type"] == "apical"
        assert meta["species"] == "beech"

    def test_lateral_twig(self):
        name, meta = standardize_twig_name("BeechLateralTwig", "beech")
        assert name == "beech_lateral"
        assert meta["type"] == "lateral"

    def test_dead_twig(self):
        name, meta = standardize_twig_name("BeechDeadTwig", "beech")
        assert name == "beech_dead"
        assert meta["type"] == "dead"

    def test_variation_detection(self):
        name, meta = standardize_twig_name(
            "ScotsPineVariationCLateralTwig", "scots_pine"
        )
        assert meta["variation"] == "c"
        assert meta["type"] == "lateral"
        assert "c" in name

    def test_generic_twig(self):
        name, meta = standardize_twig_name("UnknownTwig", "unknown")
        assert meta["type"] == "generic"

    def test_metadata_original_name_preserved(self):
        _, meta = standardize_twig_name("BeechApicalTwig", "beech")
        assert meta["original_name"] == "BeechApicalTwig"
        assert meta["is_standardized"] is True

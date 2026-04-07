"""Tests for growpy.utils.gbif_species species matching logic.

Tests the pure data-matching functions without calling the GBIF API.
API-dependent functions (validate_scientific_name, get_vernacular_names)
are tested with mocked pygbif responses.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from growpy.utils.gbif_species import match_species_via_gbif, resolve_species_list


def _make_lookup_df():
    """Create a minimal species lookup DataFrame for testing."""
    return pd.DataFrame({
        "Common Name": ["European Beech", "Norway Spruce", "Silver Birch"],
        "Scientific Name": ["Fagus sylvatica", "Picea abies", "Betula pendula"],
        "Standardized Name": ["european_beech", "norway_spruce", "silver_birch"],
        "Aliases": ["beech, copper beech", "spruce", "birch, warty birch"],
    })


class TestResolveSpeciesListLocal:
    """Tests for local species matching (no GBIF calls)."""

    def test_match_by_common_name(self):
        df = _make_lookup_df()
        result = resolve_species_list(["European Beech"], df, use_gbif=False)
        assert "European Beech" in result
        assert result["European Beech"] is not None
        assert result["European Beech"]["Scientific Name"] == "Fagus sylvatica"

    def test_match_by_scientific_name(self):
        df = _make_lookup_df()
        result = resolve_species_list(["Picea abies"], df, use_gbif=False)
        assert result["Picea abies"] is not None

    def test_match_by_alias(self):
        df = _make_lookup_df()
        result = resolve_species_list(["copper beech"], df, use_gbif=False)
        assert result["copper beech"] is not None
        assert result["copper beech"]["Common Name"] == "European Beech"

    def test_case_insensitive_match(self):
        df = _make_lookup_df()
        result = resolve_species_list(["european beech"], df, use_gbif=False)
        assert result["european beech"] is not None

    def test_unmatched_species_returns_none(self):
        df = _make_lookup_df()
        result = resolve_species_list(["Unknown Tree"], df, use_gbif=False)
        assert result["Unknown Tree"] is None

    def test_multiple_species(self):
        df = _make_lookup_df()
        result = resolve_species_list(
            ["European Beech", "Norway Spruce", "Unknown"],
            df,
            use_gbif=False,
        )
        assert result["European Beech"] is not None
        assert result["Norway Spruce"] is not None
        assert result["Unknown"] is None

    def test_empty_list(self):
        df = _make_lookup_df()
        result = resolve_species_list([], df, use_gbif=False)
        assert result == {}

    def test_match_by_standardized_name(self):
        df = _make_lookup_df()
        result = resolve_species_list(["norway_spruce"], df, use_gbif=False)
        assert result["norway_spruce"] is not None

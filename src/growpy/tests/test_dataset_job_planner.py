"""Tests for growpy.pipelines.dataset_job_planner.

Species selection is a config question, not a filesystem one: it comes from the
``Dataset`` column of tree_asset_lookup.csv. The old behaviour globbed
``*_merged.csv``, which made a file's presence a second, hidden species switch
that could silently disagree with config.
"""

import types
from unittest.mock import patch

import pandas as pd

from growpy.pipelines.dataset_job_planner import (
    PILOT_SPECIES,
    display_names_from_stems,
    list_all_species,
    resolve_species,
)

DATASET_ROWS = pd.DataFrame(
    {
        "Common Name": ["Norway spruce", "European beech", "Silver birch"],
        "Max Height": [35, 30, 30],
    }
)


def _patch_dataset(rows=DATASET_ROWS):
    return patch(
        "growpy.pipelines.dataset_csv_planner._get_dataset_species",
        return_value=rows,
    )


class TestListAllSpecies:
    def test_lists_config_marked_species(self):
        with _patch_dataset():
            assert list_all_species() == [
                "european_beech",
                "norway_spruce",
                "silver_birch",
            ]

    def test_ignores_files_on_disk(self, tmp_path):
        """A stray merged CSV must not add a species, and its absence must not
        remove one."""
        (tmp_path / "wild_cherry_merged.csv").write_text("")
        with _patch_dataset():
            result = list_all_species(tmp_path)
        assert "wild_cherry" not in result
        assert "norway_spruce" in result

    def test_empty_dataset_gives_empty_list(self):
        empty = pd.DataFrame({"Common Name": [], "Max Height": []})
        with _patch_dataset(empty):
            assert list_all_species() == []

    def test_returns_sorted(self):
        with _patch_dataset():
            assert list_all_species() == sorted(list_all_species())


class TestDisplayNamesFromStems:
    def test_single_word(self):
        assert display_names_from_stems(["beech"]) == ["Beech"]

    def test_multi_word(self):
        assert display_names_from_stems(["norway_spruce"]) == ["Norway Spruce"]

    def test_multiple_species(self):
        stems = ["european_beech", "norway_spruce"]
        assert display_names_from_stems(stems) == ["European Beech", "Norway Spruce"]

    def test_empty_list(self):
        assert display_names_from_stems([]) == []


class TestResolveSpecies:
    def _make_args(self, **kwargs):
        args = types.SimpleNamespace(species=None, pilot=False, all=False)
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def test_single_species(self):
        args = self._make_args(species="European Beech")
        assert resolve_species(args) == ["European Beech"]

    def test_pilot_species(self):
        args = self._make_args(pilot=True)
        assert resolve_species(args) == list(PILOT_SPECIES)

    def test_all_species_comes_from_config(self):
        args = self._make_args(all=True)
        with _patch_dataset():
            result = resolve_species(args)
        assert result == ["European beech", "Norway spruce", "Silver birch"]

    def test_all_species_preserves_common_name_punctuation(self):
        """Must return the exact Common Name, not a round-trip through the
        standardized stem -- .title()'d stems lose hyphens (e.g. a stem of
        "small_leaved_linden" would come back as "Small Leaved Linden", not
        the lookup table's actual "Small-leaved linden"), which then fails
        exact matching in generate_forest.py."""
        rows = pd.DataFrame(
            {
                "Common Name": ["Small-leaved linden"],
                "Max Height": [25],
            }
        )
        args = self._make_args(all=True)
        with _patch_dataset(rows):
            result = resolve_species(args)
        assert result == ["Small-leaved linden"]

    def test_no_selection(self):
        assert resolve_species(self._make_args()) == []


class TestPilotSpeciesConstant:
    def test_contains_beech_and_spruce(self):
        assert "European Beech" in PILOT_SPECIES
        assert "Norway Spruce" in PILOT_SPECIES

    def test_is_list(self):
        assert isinstance(PILOT_SPECIES, list)

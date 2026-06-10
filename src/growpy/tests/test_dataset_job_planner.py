"""Tests for growpy.pipelines.dataset_job_planner."""

import types

from growpy.pipelines.dataset_job_planner import (
    PILOT_SPECIES,
    display_names_from_stems,
    find_species_csv,
    list_all_species,
    resolve_species,
)


class TestFindSpeciesCsv:
    """Tests for merged CSV file discovery."""

    def test_finds_existing_merged_csv(self, tmp_path):
        merged = tmp_path / "norway_spruce_merged.csv"
        merged.write_text("fid,species\n1,Norway spruce\n")
        result = find_species_csv("Norway Spruce", tmp_path)
        assert result == merged

    def test_returns_none_when_missing(self, tmp_path):
        result = find_species_csv("Nonexistent Tree", tmp_path)
        assert result is None

    def test_standardizes_name(self, tmp_path):
        merged = tmp_path / "european_beech_merged.csv"
        merged.write_text("fid,species\n1,European beech\n")
        result = find_species_csv("European Beech", tmp_path)
        assert result == merged


class TestListAllSpecies:
    """Tests for listing available species."""

    def test_empty_directory(self, tmp_path):
        assert list_all_species(tmp_path) == []

    def test_finds_merged_csvs(self, tmp_path):
        (tmp_path / "norway_spruce_merged.csv").write_text("")
        (tmp_path / "european_beech_merged.csv").write_text("")
        result = list_all_species(tmp_path)
        assert sorted(result) == ["european_beech", "norway_spruce"]

    def test_ignores_non_merged_csvs(self, tmp_path):
        (tmp_path / "all_species.csv").write_text("")
        (tmp_path / "norway_spruce_merged.csv").write_text("")
        result = list_all_species(tmp_path)
        assert result == ["norway_spruce"]

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "silver_birch_merged.csv").write_text("")
        (tmp_path / "european_beech_merged.csv").write_text("")
        (tmp_path / "norway_spruce_merged.csv").write_text("")
        result = list_all_species(tmp_path)
        assert result == ["european_beech", "norway_spruce", "silver_birch"]


class TestDisplayNamesFromStems:
    """Tests for stem-to-display-name conversion."""

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
    """Tests for CLI argument species resolution."""

    def _make_args(self, **kwargs):
        args = types.SimpleNamespace(species=None, pilot=False, all=False)
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def test_single_species(self, tmp_path):
        args = self._make_args(species="European Beech")
        result = resolve_species(args, tmp_path)
        assert result == ["European Beech"]

    def test_pilot_species(self, tmp_path):
        args = self._make_args(pilot=True)
        result = resolve_species(args, tmp_path)
        assert result == list(PILOT_SPECIES)

    def test_all_species(self, tmp_path):
        (tmp_path / "norway_spruce_merged.csv").write_text("")
        (tmp_path / "european_beech_merged.csv").write_text("")
        args = self._make_args(all=True)
        result = resolve_species(args, tmp_path)
        assert "European Beech" in result
        assert "Norway Spruce" in result

    def test_no_selection(self, tmp_path):
        args = self._make_args()
        result = resolve_species(args, tmp_path)
        assert result == []


class TestPilotSpeciesConstant:
    """Tests for pilot species list."""

    def test_contains_beech_and_spruce(self):
        assert "European Beech" in PILOT_SPECIES
        assert "Norway Spruce" in PILOT_SPECIES

    def test_is_list(self):
        assert isinstance(PILOT_SPECIES, list)

"""Tests for the dataset orchestration modules."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from growpy.pipelines.dataset_csv_planner import (
    DENSITY_VARIANTS,
    OPEN_TREE_X,
    _polygon_neighbors,
    generate_dataset_csvs,
    generate_merged_csv,
)
from growpy.pipelines.dataset_job_planner import (
    DATASET_DIR,
    PILOT_SPECIES,
    display_names_from_stems,
    find_species_csv,
    list_all_species,
    resolve_species,
)
from growpy.pipelines.step_runner import (
    STEP_SCRIPTS,
    _build_step4_command,
    run_parallel_step4,
    run_species_step4,
    run_step123,
)

# ---------------------------------------------------------------------------
# dataset_csv_planner
# ---------------------------------------------------------------------------


class TestPolygonNeighbors:
    def test_returns_three_neighbors(self):
        neighbors = _polygon_neighbors(10.0)
        assert len(neighbors) == 3

    def test_fids_101_to_103(self):
        neighbors = _polygon_neighbors(10.0)
        fids = [fid for fid, _, _ in neighbors]
        assert fids == [101, 102, 103]

    def test_spacing_used_as_x_offset(self):
        spacing = 8.0
        neighbors = _polygon_neighbors(spacing)
        fid_101 = next(n for n in neighbors if n[0] == 101)
        assert fid_101[1] == spacing  # (101, spacing, 0.0)

    def test_symmetric_y_values(self):
        neighbors = _polygon_neighbors(10.0)
        by_fid = {fid: (x, y) for fid, x, y in neighbors}
        assert by_fid[102][1] == -by_fid[103][1]  # mirror across x-axis


class TestGenerateMergedCsv:
    def test_has_correct_fids(self):
        df = generate_merged_csv("European Beech", 30, 8)
        fids = set(df["fid"].tolist())
        assert 1 in fids  # open-grown
        assert 2 in fids  # competition center
        assert all(f in fids for f in range(101, 104))  # 3 neighbors

    def test_open_tree_x_offset(self):
        df = generate_merged_csv("European Beech", 30, 8)
        open_row = df[df["fid"] == 1].iloc[0]
        assert open_row["x"] == OPEN_TREE_X

    def test_competition_center_at_origin(self):
        df = generate_merged_csv("European Beech", 30, 8)
        center = df[df["fid"] == 2].iloc[0]
        assert center["x"] == 0.0
        assert center["y"] == 0.0

    def test_individual_type_labels(self):
        df = generate_merged_csv("European Beech", 30, 8)
        assert df[df["fid"] == 1]["individual_type"].iloc[0] == "open_grown"
        assert df[df["fid"] == 2]["individual_type"].iloc[0] == "competition"

    def test_twig_density_applied(self):
        df = generate_merged_csv("Norway Spruce", 25, 6, twig_density=0.5)
        assert (df["twig_density"] == 0.5).all()

    def test_species_column(self):
        df = generate_merged_csv("Norway Spruce", 25, 6)
        assert (df["species"] == "Norway Spruce").all()

    def test_total_rows(self):
        df = generate_merged_csv("European Beech", 30, 8)
        assert len(df) == 5  # 1 open + 1 center + 3 neighbors


class TestDensityVariants:
    def test_full_is_one(self):
        assert DENSITY_VARIANTS["full"] == 1.0

    def test_reduced_is_half(self):
        assert DENSITY_VARIANTS["reduced"] == 0.5

    def test_bare_is_zero(self):
        assert DENSITY_VARIANTS["bare"] == 0.0


class TestGenerateDatasetCsvs:
    def test_creates_merged_and_all_species(self, tmp_path):
        mock_df = pd.DataFrame(
            {
                "Common Name": ["European Beech", "Norway Spruce"],
                "Max Height": [30, 25],
                "Competition Spacing": [8, 6],
            }
        )
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_dataset_species",
            return_value=mock_df,
        ):
            paths = generate_dataset_csvs(tmp_path, "full")

        names = [p.name for p in paths]
        assert "european_beech_merged.csv" in names
        assert "norway_spruce_merged.csv" in names
        assert "all_species.csv" in names

    def test_all_species_csv_has_one_row_per_species(self, tmp_path):
        mock_df = pd.DataFrame(
            {
                "Common Name": ["European Beech", "Norway Spruce"],
                "Max Height": [30, 25],
                "Competition Spacing": [8, 6],
            }
        )
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_dataset_species",
            return_value=mock_df,
        ):
            generate_dataset_csvs(tmp_path, "full")

        all_species = pd.read_csv(tmp_path / "all_species.csv")
        assert len(all_species) == 2

    def test_density_variant_applied(self, tmp_path):
        mock_df = pd.DataFrame(
            {
                "Common Name": ["European Beech"],
                "Max Height": [30],
                "Competition Spacing": [8],
            }
        )
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_dataset_species",
            return_value=mock_df,
        ):
            generate_dataset_csvs(tmp_path, "bare")

        merged = pd.read_csv(tmp_path / "european_beech_merged.csv")
        assert (merged["twig_density"] == 0.0).all()


# ---------------------------------------------------------------------------
# dataset_job_planner
# ---------------------------------------------------------------------------


class TestListAllSpecies:
    def test_returns_stems_without_merged(self, tmp_path):
        (tmp_path / "european_beech_merged.csv").write_text("fid\n1\n")
        (tmp_path / "norway_spruce_merged.csv").write_text("fid\n1\n")
        result = list_all_species(tmp_path)
        assert "european_beech" in result
        assert "norway_spruce" in result

    def test_empty_directory(self, tmp_path):
        assert list_all_species(tmp_path) == []

    def test_ignores_non_merged_csvs(self, tmp_path):
        (tmp_path / "all_species.csv").write_text("fid\n1\n")
        (tmp_path / "european_beech_merged.csv").write_text("fid\n1\n")
        result = list_all_species(tmp_path)
        assert result == ["european_beech"]


class TestFindSpeciesCsv:
    def test_finds_existing_csv(self, tmp_path):
        csv = tmp_path / "european_beech_merged.csv"
        csv.write_text("fid\n1\n")
        result = find_species_csv("European Beech", tmp_path)
        assert result == csv

    def test_returns_none_if_missing(self, tmp_path):
        result = find_species_csv("European Beech", tmp_path)
        assert result is None


class TestDisplayNamesFromStems:
    def test_converts_stem_to_title(self):
        result = display_names_from_stems(["european_beech", "norway_spruce"])
        assert result == ["European Beech", "Norway Spruce"]


class TestResolveSpecies:
    def _args(self, **kwargs):
        defaults = {"species": None, "pilot": False, "all": False}
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_species_flag(self):
        args = self._args(species="European Beech")
        assert resolve_species(args) == ["European Beech"]

    def test_pilot_flag(self):
        args = self._args(pilot=True)
        assert resolve_species(args) == list(PILOT_SPECIES)

    def test_all_flag(self, tmp_path):
        (tmp_path / "european_beech_merged.csv").write_text("fid\n1\n")
        args = self._args(all=True)
        result = resolve_species(args, tmp_path)
        assert "European Beech" in result

    def test_no_selection_returns_empty(self):
        args = self._args()
        assert resolve_species(args) == []


# ---------------------------------------------------------------------------
# step_runner
# ---------------------------------------------------------------------------


class TestStepScripts:
    def test_all_four_steps_defined(self):
        assert set(STEP_SCRIPTS.keys()) == {1, 2, 3, 4}

    def test_step4_is_generate_forest(self):
        assert "generate_forest" in STEP_SCRIPTS[4].name


class TestBuildStep4Command:
    def test_includes_csv_path(self):
        csv = Path("data/input/dataset/european_beech_merged.csv")
        cmd = _build_step4_command(csv)
        assert str(csv) in cmd

    def test_includes_export_trees_flag(self):
        cmd = _build_step4_command(Path("some.csv"))
        assert "--export-trees" in cmd
        assert "1,2" in cmd

    def test_max_height_included_when_nonzero(self):
        cmd = _build_step4_command(Path("some.csv"), max_height=15.0)
        assert "--max-height" in cmd
        assert "15.0" in cmd

    def test_max_height_excluded_when_zero(self):
        cmd = _build_step4_command(Path("some.csv"), max_height=0)
        assert "--max-height" not in cmd


class TestRunStep123:
    def test_dry_run_returns_true_and_does_not_call_subprocess(self):
        with patch("growpy.pipelines.step_runner.subprocess.run") as mock_run:
            result = run_step123(3, Path("all_species.csv"), dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    def test_returns_true_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("growpy.pipelines.step_runner.subprocess.run", return_value=mock_result):
            result = run_step123(1, Path("all_species.csv"))
        assert result is True

    def test_returns_false_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("growpy.pipelines.step_runner.subprocess.run", return_value=mock_result):
            result = run_step123(2, Path("all_species.csv"))
        assert result is False


class TestRunSpeciesStep4:
    def test_dry_run_returns_true_without_subprocess(self, tmp_path):
        csv = tmp_path / "european_beech_merged.csv"
        csv.write_text("fid\n1\n")
        with patch("growpy.pipelines.step_runner.subprocess.run") as mock_run:
            result = run_species_step4("European Beech", tmp_path, dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    def test_returns_false_when_csv_missing(self, tmp_path):
        result = run_species_step4("European Beech", tmp_path)
        assert result is False

    def test_returns_true_on_subprocess_success(self, tmp_path):
        csv = tmp_path / "european_beech_merged.csv"
        csv.write_text("fid\n1\n")
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("growpy.pipelines.step_runner.subprocess.run", return_value=mock_result):
            result = run_species_step4("European Beech", tmp_path)
        assert result is True

    def test_returns_false_on_subprocess_failure(self, tmp_path):
        csv = tmp_path / "european_beech_merged.csv"
        csv.write_text("fid\n1\n")
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("growpy.pipelines.step_runner.subprocess.run", return_value=mock_result):
            result = run_species_step4("European Beech", tmp_path)
        assert result is False

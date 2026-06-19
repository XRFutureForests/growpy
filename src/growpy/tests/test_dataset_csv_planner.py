"""Tests for growpy.pipelines.dataset_csv_planner."""

import math
from unittest.mock import patch

import pandas as pd
import pytest

from growpy.pipelines.dataset_csv_planner import (
    DENSITY_VARIANTS,
    OPEN_TREE_X,
    _get_dataset_species,
    _polygon_neighbors,
    generate_merged_csv,
    synchronize_dataset_csvs,
)


class TestPolygonNeighbors:
    """Tests for polygon neighbor placement."""

    def test_returns_three_neighbors(self):
        result = _polygon_neighbors(10.0)
        assert len(result) == 3

    def test_fids_are_101_102_103(self):
        result = _polygon_neighbors(10.0)
        fids = [r[0] for r in result]
        assert fids == [101, 102, 103]

    def test_distance_from_origin(self):
        spacing = 12.0
        result = _polygon_neighbors(spacing)
        for _, x, y in result:
            dist = math.sqrt(x**2 + y**2)
            assert dist == pytest.approx(spacing, abs=0.01)

    def test_equilateral_triangle(self):
        result = _polygon_neighbors(8.0)
        coords = [(x, y) for _, x, y in result]
        # Check pairwise distances are equal
        dists = []
        for i in range(3):
            for j in range(i + 1, 3):
                dx = coords[i][0] - coords[j][0]
                dy = coords[i][1] - coords[j][1]
                dists.append(math.sqrt(dx**2 + dy**2))
        assert dists[0] == pytest.approx(dists[1], rel=1e-4)
        assert dists[1] == pytest.approx(dists[2], rel=1e-4)

    def test_zero_spacing(self):
        result = _polygon_neighbors(0.0)
        for _, x, y in result:
            assert x == 0.0
            assert y == 0.0

    def test_four_neighbors(self):
        result = _polygon_neighbors(10.0, n=4)
        assert len(result) == 4

    def test_six_neighbors(self):
        result = _polygon_neighbors(10.0, n=6)
        assert len(result) == 6


class TestGenerateMergedCsv:
    """Tests for merged CSV generation."""

    def test_returns_dataframe(self):
        df = generate_merged_csv("Norway spruce", 30, 8)
        assert isinstance(df, pd.DataFrame)

    def test_five_rows_total(self):
        df = generate_merged_csv("Test Species", 25, 10)
        assert len(df) == 5

    def test_fid_values(self):
        df = generate_merged_csv("Test Species", 25, 10)
        fids = sorted(df["fid"].tolist())
        assert fids == [1, 2, 101, 102, 103]

    def test_open_tree_at_offset(self):
        df = generate_merged_csv("Test Species", 25, 10)
        open_row = df[df["fid"] == 1].iloc[0]
        assert open_row["x"] == OPEN_TREE_X
        assert open_row["individual_type"] == "open_grown"

    def test_competition_center_at_origin(self):
        df = generate_merged_csv("Test Species", 25, 10)
        center = df[df["fid"] == 2].iloc[0]
        assert center["x"] == 0.0
        assert center["y"] == 0.0
        assert center["individual_type"] == "competition"

    def test_species_propagated(self):
        df = generate_merged_csv("European Beech", 32, 8)
        assert (df["species"] == "European Beech").all()

    def test_max_height_propagated(self):
        df = generate_merged_csv("Test", 42, 10)
        assert (df["height"] == 42).all()

    def test_twig_density_default(self):
        df = generate_merged_csv("Test", 25, 10)
        assert (df["twig_density"] == 1.0).all()

    def test_twig_density_custom(self):
        df = generate_merged_csv("Test", 25, 10, twig_density=0.5)
        assert (df["twig_density"] == 0.5).all()

    def test_all_z_zero(self):
        df = generate_merged_csv("Test", 25, 10)
        assert (df["z"] == 0.0).all()

    def test_required_columns(self):
        df = generate_merged_csv("Test", 25, 10)
        expected_cols = {"fid", "species", "x", "y", "z", "height", "twig_density", "individual_type"}
        assert expected_cols.issubset(set(df.columns))


class TestDensityVariants:
    """Tests for density variant constants."""

    def test_full_is_one(self):
        assert DENSITY_VARIANTS["full"] == 1.0

    def test_reduced_is_half(self):
        assert DENSITY_VARIANTS["reduced"] == 0.5

    def test_bare_is_zero(self):
        assert DENSITY_VARIANTS["bare"] == 0.0


class TestSynchronizeDatasetCsvs:
    """Tests for CSV synchronization."""

    def test_no_op_when_no_all_species(self, tmp_path):
        synchronize_dataset_csvs(tmp_path)

    def test_no_op_when_missing_species_column(self, tmp_path):
        all_csv = tmp_path / "all_species.csv"
        pd.DataFrame({"fid": [1], "name": ["spruce"]}).to_csv(all_csv, index=False)
        synchronize_dataset_csvs(tmp_path)

    def test_removes_orphan_merged_csv(self, tmp_path):
        all_csv = tmp_path / "all_species.csv"
        pd.DataFrame({"fid": [1], "species": ["Norway spruce"]}).to_csv(all_csv, index=False)
        # Create matching merged CSV
        (tmp_path / "norway_spruce_merged.csv").write_text("fid,species\n1,Norway spruce\n")
        # Create orphan merged CSV (no matching entry in all_species)
        (tmp_path / "silver_birch_merged.csv").write_text("fid,species\n1,Silver birch\n")

        synchronize_dataset_csvs(tmp_path)
        assert not (tmp_path / "silver_birch_merged.csv").exists()
        assert (tmp_path / "norway_spruce_merged.csv").exists()

    def test_removes_species_without_merged_csv(self, tmp_path):
        all_csv = tmp_path / "all_species.csv"
        pd.DataFrame({
            "fid": [1, 2],
            "species": ["Norway spruce", "European beech"],
        }).to_csv(all_csv, index=False)
        # Only create merged CSV for Norway spruce
        (tmp_path / "norway_spruce_merged.csv").write_text("fid,species\n1,Norway spruce\n")

        synchronize_dataset_csvs(tmp_path)
        updated = pd.read_csv(all_csv)
        assert len(updated) == 1
        assert updated.iloc[0]["species"] == "Norway spruce"

    def test_no_changes_when_synchronized(self, tmp_path):
        all_csv = tmp_path / "all_species.csv"
        pd.DataFrame({"fid": [1], "species": ["Norway spruce"]}).to_csv(all_csv, index=False)
        (tmp_path / "norway_spruce_merged.csv").write_text("fid,species\n1,Norway spruce\n")

        synchronize_dataset_csvs(tmp_path)
        updated = pd.read_csv(all_csv)
        assert len(updated) == 1


class TestGetDatasetSpecies:
    """Tests for Dataset-column-driven species selection."""

    def _lookup(self, dataset=("yes", "", "")):
        return pd.DataFrame(
            {
                "Common Name": ["Norway spruce", "Grand fir", "Hornbeam"],
                "Max Height": [35, 35, 20],
                "Competition Group": ["slow_conifer", "slow_conifer", "fast_broadleaf"],
                "Dataset": list(dataset),
            }
        )

    def test_only_marked_rows_selected(self):
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_lookup_table",
            return_value=self._lookup(),
        ):
            result = _get_dataset_species()
        assert result["Common Name"].tolist() == ["Norway spruce"]

    def test_marker_is_case_insensitive(self):
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_lookup_table",
            return_value=self._lookup(dataset=("YES", "True", "")),
        ):
            result = _get_dataset_species()
        assert set(result["Common Name"]) == {"Norway spruce", "Grand fir"}

    def test_missing_dataset_column_raises(self):
        lookup = self._lookup().drop(columns=["Dataset"])
        with patch(
            "growpy.pipelines.dataset_csv_planner._get_lookup_table",
            return_value=lookup,
        ):
            with pytest.raises(KeyError, match="Dataset"):
                _get_dataset_species()

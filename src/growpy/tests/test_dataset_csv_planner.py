"""Tests for growpy.pipelines.dataset_csv_planner."""

from unittest.mock import patch

import pandas as pd
import pytest

from growpy.pipelines.dataset_csv_planner import (
    DENSITY_VARIANTS,
    OPEN_TREE_X,
    _get_dataset_species,
    generate_merged_csv,
    synchronize_dataset_csvs,
)


class TestGenerateMergedCsv:
    """Tests for merged CSV generation (open-grown + surround, one tree each)."""

    def test_returns_dataframe(self):
        df = generate_merged_csv("Norway spruce", 30)
        assert isinstance(df, pd.DataFrame)

    def test_two_rows_total(self):
        df = generate_merged_csv("Test Species", 25)
        assert len(df) == 2

    def test_fid_values(self):
        df = generate_merged_csv("Test Species", 25)
        fids = sorted(df["fid"].tolist())
        assert fids == [1, 2]

    def test_open_tree_at_offset(self):
        df = generate_merged_csv("Test Species", 25)
        open_row = df[df["fid"] == 1].iloc[0]
        assert open_row["x"] == OPEN_TREE_X
        assert open_row["individual_type"] == "open_grown"

    def test_surround_tree_at_origin(self):
        df = generate_merged_csv("Test Species", 25)
        surround = df[df["fid"] == 2].iloc[0]
        assert surround["x"] == 0.0
        assert surround["y"] == 0.0
        assert surround["individual_type"] == "surround"

    def test_species_propagated(self):
        df = generate_merged_csv("European Beech", 32)
        assert (df["species"] == "European Beech").all()

    def test_max_height_propagated(self):
        df = generate_merged_csv("Test", 42)
        assert (df["height"] == 42).all()

    def test_twig_density_default(self):
        df = generate_merged_csv("Test", 25)
        assert (df["twig_density"] == 1.0).all()

    def test_twig_density_custom(self):
        df = generate_merged_csv("Test", 25, twig_density=0.5)
        assert (df["twig_density"] == 0.5).all()

    def test_all_z_zero(self):
        df = generate_merged_csv("Test", 25)
        assert (df["z"] == 0.0).all()

    def test_required_columns(self):
        df = generate_merged_csv("Test", 25)
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

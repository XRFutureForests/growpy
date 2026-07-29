"""Tests for growpy.pipelines.dataset_csv_planner."""

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from growpy.pipelines.dataset_csv_planner import (
    DENSITY_VARIANTS,
    OPEN_TREE_X,
    _get_dataset_species,
    build_job_matrix,
    generate_merged_csv,
)


def _mock_radii(radii):
    return patch(
        "growpy.config.get_config",
        return_value=SimpleNamespace(surround_radii=radii),
    )


class TestGenerateMergedCsv:
    """Tests for merged CSV generation (one row per configured surround radius)."""

    def test_returns_dataframe(self):
        with _mock_radii([0.0, 7.0, 15.0]):
            df = generate_merged_csv("Norway spruce", 30)
        assert isinstance(df, pd.DataFrame)

    def test_row_count_matches_radii(self):
        with _mock_radii([0.0, 7.0, 15.0]):
            df = generate_merged_csv("Test Species", 25)
        assert len(df) == 3

    def test_fid_values(self):
        with _mock_radii([0.0, 7.0, 15.0]):
            df = generate_merged_csv("Test Species", 25)
        assert sorted(df["fid"].tolist()) == [1, 2, 3]

    def test_surround_radius_values(self):
        with _mock_radii([0.0, 7.0, 15.0]):
            df = generate_merged_csv("Test Species", 25)
        assert sorted(df["surround_radius"].tolist()) == [0.0, 7.0, 15.0]

    def test_open_grown_row_at_origin(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test Species", 25)
        open_row = df[df["surround_radius"] == 0.0].iloc[0]
        assert open_row["x"] == 0.0

    def test_rows_offset_along_x(self):
        with _mock_radii([0.0, 7.0, 15.0]):
            df = generate_merged_csv("Test Species", 25)
        assert sorted(df["x"].tolist()) == [0.0, OPEN_TREE_X, OPEN_TREE_X * 2]

    def test_single_radius(self):
        with _mock_radii([0.0]):
            df = generate_merged_csv("Test Species", 25)
        assert len(df) == 1
        assert df.iloc[0]["surround_radius"] == 0.0

    def test_species_propagated(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 32)
        assert (df["species"] == "European Beech").all()

    def test_max_height_propagated(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 42)
        assert (df["height"] == 42).all()

    def test_twig_density_default(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 25)
        assert (df["twig_density"] == 1.0).all()

    def test_twig_density_custom(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 25, twig_density=0.5)
        assert (df["twig_density"] == 0.5).all()

    def test_all_z_zero(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 25)
        assert (df["z"] == 0.0).all()

    def test_required_columns(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 25)
        expected_cols = {"fid", "species", "x", "y", "z", "height", "twig_density", "surround_radius"}
        assert expected_cols.issubset(set(df.columns))

    def test_no_individual_type_column(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Test", 25)
        assert "individual_type" not in df.columns


class TestDensityVariants:
    """Tests for density variant constants."""

    def test_full_is_one(self):
        assert DENSITY_VARIANTS["full"] == 1.0

    def test_reduced_is_half(self):
        assert DENSITY_VARIANTS["reduced"] == 0.5

    def test_bare_is_zero(self):
        assert DENSITY_VARIANTS["bare"] == 0.0


class TestBuildJobMatrix:
    """The dataset job matrix is derived from config alone.

    Nothing is read from disk and nothing needs regenerating, so the rows
    cannot drift from config the way a CSV file could.
    """

    def _species_row(self, max_height=45):
        return pd.Series({"Common Name": "Douglas fir", "Max Height": max_height})

    def _patched(self, max_height=45, radii=(0.0, 5.0, 10.0)):
        return (
            patch(
                "growpy.config.paths._find_species_row",
                return_value=self._species_row(max_height),
            ),
            _mock_radii(list(radii)),
        )

    def test_one_row_per_configured_radius(self):
        find, radii = self._patched(radii=(0.0, 5.0, 10.0))
        with find, radii:
            df = build_job_matrix("Douglas fir")
        assert len(df) == 3
        assert sorted(df["surround_radius"]) == [0.0, 5.0, 10.0]

    def test_height_comes_from_lookup_table(self):
        find, radii = self._patched(max_height=45)
        with find, radii:
            df = build_job_matrix("Douglas fir")
        assert (df["height"] == 45).all()

    def test_x_offsets_separate_the_variants(self):
        find, radii = self._patched(radii=(0.0, 5.0, 10.0))
        with find, radii:
            df = build_job_matrix("Douglas fir")
        assert df["x"].tolist() == [0.0, OPEN_TREE_X, 2 * OPEN_TREE_X]
        assert (df["y"] == 0.0).all()

    def test_raises_without_max_height(self):
        find = patch(
            "growpy.config.paths._find_species_row",
            return_value=pd.Series({"Common Name": "Mystery tree", "Max Height": None}),
        )
        with find, _mock_radii([0.0]), pytest.raises(ValueError, match="Max Height"):
            build_job_matrix("Mystery tree")

    def test_matches_generate_merged_csv(self):
        """The in-memory matrix and the inspection CSV must not diverge."""
        find, radii = self._patched(max_height=45, radii=(0.0, 5.0, 10.0))
        with find, radii:
            built = build_job_matrix("Douglas fir")
        with _mock_radii([0.0, 5.0, 10.0]):
            dumped = generate_merged_csv("Douglas fir", 45)
        pd.testing.assert_frame_equal(built, dumped)


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

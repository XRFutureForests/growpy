"""Tests for the dataset orchestration modules."""

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from growpy.pipelines.dataset_csv_planner import (
    DENSITY_VARIANTS,
    OPEN_TREE_X,
    generate_dataset_csvs,
    generate_merged_csv,
)
from growpy.pipelines.dataset_job_planner import (
    PILOT_SPECIES,
    display_names_from_stems,
    list_all_species,
    resolve_species,
)
from growpy.pipelines.step_runner import (
    STEP_SCRIPTS,
    _build_step4_command,
    run_species_step4,
    run_step123,
)

# ---------------------------------------------------------------------------
# dataset_csv_planner
# ---------------------------------------------------------------------------


def _mock_radii(radii):
    return patch(
        "growpy.config.get_config",
        return_value=SimpleNamespace(surround_radii=radii),
    )


class TestGenerateMergedCsv:
    def test_has_correct_fids(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 30)
        fids = set(df["fid"].tolist())
        assert fids == {1, 2}

    def test_open_grown_row_at_origin(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 30)
        open_row = df[df["surround_radius"] == 0.0].iloc[0]
        assert open_row["x"] == 0.0

    def test_surround_row_offset(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 30)
        surround = df[df["surround_radius"] == 7.0].iloc[0]
        assert surround["x"] == OPEN_TREE_X
        assert surround["y"] == 0.0

    def test_surround_radius_values(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 30)
        assert sorted(df["surround_radius"].tolist()) == [0.0, 7.0]

    def test_twig_density_applied(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Norway Spruce", 25, twig_density=0.5)
        assert (df["twig_density"] == 0.5).all()

    def test_species_column(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("Norway Spruce", 25)
        assert (df["species"] == "Norway Spruce").all()

    def test_total_rows(self):
        with _mock_radii([0.0, 7.0]):
            df = generate_merged_csv("European Beech", 30)
        assert len(df) == 2


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
    """Membership comes from config, not from files on disk."""

    def test_lists_species_marked_in_lookup_table(self):
        result = list_all_species()
        assert "european_beech" in result
        assert "norway_spruce" in result

    def test_files_on_disk_do_not_change_membership(self, tmp_path):
        (tmp_path / "wild_cherry_merged.csv").write_text("fid\n1\n")
        assert list_all_species(tmp_path) == list_all_species()


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

    def test_all_flag(self):
        args = self._args(all=True)
        assert "European beech" in resolve_species(args)

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
    """Only what the child cannot derive crosses the process boundary."""

    def test_passes_species_not_a_csv(self):
        cmd = _build_step4_command("European Beech")
        assert "--species" in cmd
        assert cmd[cmd.index("--species") + 1] == "European Beech"
        assert not any(str(c).endswith(".csv") for c in cmd)

    def test_no_export_trees_filter(self):
        # The child builds every job row for the species itself.
        assert "--export-trees" not in _build_step4_command("European Beech")

    def test_max_height_included_when_nonzero(self):
        cmd = _build_step4_command("European Beech", max_height=15.0)
        assert "--max-height" in cmd
        assert "15.0" in cmd

    def test_max_height_excluded_when_zero(self):
        cmd = _build_step4_command("European Beech", max_height=0)
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

    def test_dataset_mode_passes_no_csv(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch(
            "growpy.pipelines.step_runner.subprocess.run", return_value=mock_result
        ) as mock_run:
            run_step123(1, dataset_mode=True)
        cmd = mock_run.call_args[0][0]
        assert "--dataset" in cmd
        assert "--csv" not in cmd


class TestRunSpeciesStep4:
    """No CSV needs to exist -- the child derives its rows from config."""

    def test_dry_run_returns_true_without_subprocess(self):
        with patch("growpy.pipelines.step_runner.subprocess.run") as mock_run:
            result = run_species_step4("European Beech", dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    def test_returns_true_on_subprocess_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch(
            "growpy.pipelines.step_runner.subprocess.run", return_value=mock_result
        ):
            result = run_species_step4("European Beech")
        assert result is True

    def test_returns_false_on_subprocess_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch(
            "growpy.pipelines.step_runner.subprocess.run", return_value=mock_result
        ):
            result = run_species_step4("European Beech")
        assert result is False

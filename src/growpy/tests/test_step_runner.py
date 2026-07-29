"""Tests for growpy.pipelines.step_runner."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from growpy.pipelines.step_runner import (
    STEP_SCRIPTS,
    _build_step4_command,
    _build_step123_command,
    check_environment,
    run_species_step4,
    run_step123,
)


class TestStepScripts:
    """Tests for step script path constants."""

    def test_all_four_steps_defined(self):
        assert set(STEP_SCRIPTS.keys()) == {1, 2, 3, 4}

    def test_scripts_are_paths(self):
        for path in STEP_SCRIPTS.values():
            assert isinstance(path, Path)

    def test_step4_is_generate_forest(self):
        assert STEP_SCRIPTS[4].name == "generate_forest.py"


class TestCheckEnvironment:
    """Tests for bpy availability check."""

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_returns_true_when_bpy_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_environment() is True

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_returns_false_when_bpy_unavailable(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert check_environment() is False

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_calls_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        check_environment()
        mock_run.assert_called_once_with(
            [sys.executable, "-c", "import bpy"],
            capture_output=True,
        )


class TestBuildStep4Command:
    """Tests for step 4 command construction."""

    def test_basic_command(self):
        cmd = _build_step4_command("European Beech")
        assert cmd[0] == sys.executable
        assert str(STEP_SCRIPTS[4]) in cmd[1]
        assert cmd[2] == "--species"
        assert cmd[3] == "European Beech"

    def test_passes_no_csv(self):
        cmd = _build_step4_command("European Beech")
        assert not any(str(c).endswith(".csv") for c in cmd)

    def test_no_export_trees_filter(self):
        # The child builds every job row for the species itself, so there is
        # nothing to filter down to.
        assert "--export-trees" not in _build_step4_command("European Beech")

    def test_with_max_height(self):
        cmd = _build_step4_command("European Beech", max_height=15.0)
        assert "--max-height" in cmd
        idx = cmd.index("--max-height")
        assert cmd[idx + 1] == "15.0"

    def test_without_max_height(self):
        cmd = _build_step4_command("European Beech", max_height=0)
        assert "--max-height" not in cmd

    def test_skip_unreal_scripts(self):
        cmd = _build_step4_command("European Beech", skip_unreal_scripts=True)
        assert "--no-unreal-scripts" in cmd

    def test_no_unreal_scripts_by_default(self):
        cmd = _build_step4_command("European Beech")
        assert "--no-unreal-scripts" not in cmd


class TestBuildStep123Command:
    """Tests for step 1-3 command construction."""

    def test_dataset_mode_passes_no_csv(self):
        cmd = _build_step123_command(1, dataset_mode=True)
        assert "--dataset" in cmd
        assert "--csv" not in cmd
        assert not any(str(c).endswith(".csv") for c in cmd)

    def test_csv_mode_passes_path(self):
        cmd = _build_step123_command(
            2, dataset_mode=False, csv_path=Path("data/all.csv")
        )
        assert "--csv" in cmd
        assert str(Path("data/all.csv")) in cmd
        assert "--dataset" not in cmd

    def test_verbose_appended(self):
        cmd = _build_step123_command(3, dataset_mode=True, verbose=True)
        assert "--verbose" in cmd

    def test_extra_args_appended(self):
        cmd = _build_step123_command(
            3, dataset_mode=True, extra_args=["--ingest-yield-tables"]
        )
        assert "--ingest-yield-tables" in cmd


class TestRunStep123:
    """Tests for steps 1-3 subprocess execution."""

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_dry_run_returns_true(self, mock_run):
        result = run_step123(1, Path("all.csv"), dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_dataset_mode_passes_no_csv(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_step123(1, dataset_mode=True)
        cmd = mock_run.call_args[0][0]
        assert "--dataset" in cmd
        assert "--csv" not in cmd

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_success_returns_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = run_step123(2, Path("all.csv"))
        assert result is True

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_failure_returns_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = run_step123(3, Path("all.csv"))
        assert result is False

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_includes_csv_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_step123(1, Path("data/all.csv"))
        cmd = mock_run.call_args[0][0]
        assert "--csv" in cmd
        assert str(Path("data/all.csv")) in cmd

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_extra_args_appended(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_step123(3, Path("all.csv"), extra_args=["--ingest-yield-tables"])
        cmd = mock_run.call_args[0][0]
        assert "--ingest-yield-tables" in cmd


class TestRunSpeciesStep4:
    """Tests for per-species step 4 execution.

    No CSV needs to exist: the child rebuilds its job rows from config, so
    there is no file to look up and nothing to fail on when one is absent.
    """

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_dry_run_returns_true(self, mock_run):
        result = run_species_step4("European Beech", dry_run=True)
        assert result is True
        mock_run.assert_not_called()

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_success_returns_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = run_species_step4("European Beech")
        assert result is True

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_failure_returns_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = run_species_step4("European Beech")
        assert result is False

    @patch("growpy.pipelines.step_runner.subprocess.run")
    def test_species_reaches_the_child(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_species_step4("Douglas fir")
        cmd = mock_run.call_args[0][0]
        assert "--species" in cmd
        assert "Douglas fir" in cmd

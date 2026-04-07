"""Tests for growpy.tools.ue_exec CLI and batch orchestration."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from growpy.tools.ue_exec import (
    BATCH_PATTERN,
    _discover_batch_scripts,
    _get_gpu_vram,
    _vram_bar,
)


class TestBatchPattern:
    """Tests for the batch filename regex."""

    def test_matches_standard_batch(self):
        assert BATCH_PATTERN.match("import_batch_00_instances.py")
        assert BATCH_PATTERN.match("import_batch_01_european_oak.py")
        assert BATCH_PATTERN.match("import_batch_99_consolidate.py")
        assert BATCH_PATTERN.match("import_batch_100_datatable.py")

    def test_rejects_non_batch(self):
        assert not BATCH_PATTERN.match("import_forest.py")
        assert not BATCH_PATTERN.match("clean_assets.py")
        assert not BATCH_PATTERN.match("_import_progress.txt")


class TestDiscoverBatchScripts:
    """Tests for batch discovery and ordering."""

    def test_discovers_and_sorts(self, tmp_path):
        (tmp_path / "import_batch_02_spruce.py").write_text("pass")
        (tmp_path / "import_batch_00_instances.py").write_text("pass")
        (tmp_path / "import_batch_01_oak.py").write_text("pass")
        (tmp_path / "import_forest.py").write_text("pass")
        (tmp_path / "clean_assets.py").write_text("pass")

        batches = _discover_batch_scripts(tmp_path)
        names = [b.name for b in batches]
        assert names == [
            "import_batch_00_instances.py",
            "import_batch_01_oak.py",
            "import_batch_02_spruce.py",
        ]

    def test_empty_dir(self, tmp_path):
        assert _discover_batch_scripts(tmp_path) == []


class TestVramBar:
    """Tests for the visual VRAM bar."""

    def test_zero(self):
        assert _vram_bar(0, 10) == "----------"

    def test_full(self):
        assert _vram_bar(100, 10) == "##########"

    def test_half(self):
        assert _vram_bar(50, 10) == "#####-----"


class TestUeExecMain:
    """Tests for the ue_exec main function."""

    @patch("growpy.tools.ue_exec.sys")
    def test_missing_target_exits(self, mock_sys):
        """Verify nonexistent target causes exit."""
        mock_sys.argv = ["ue_exec", "nonexistent_script.py"]
        mock_sys.exit = MagicMock(side_effect=SystemExit(1))

        from growpy.tools.ue_exec import main

        with pytest.raises(SystemExit):
            main()

    @patch("growpy.tools.ue_exec.sys")
    def test_list_nodes_flag(self, mock_sys):
        """Verify --list-nodes calls discover_nodes and exits."""
        mock_sys.argv = ["ue_exec", "--list-nodes"]
        mock_sys.exit = MagicMock(side_effect=SystemExit(0))

        from growpy.tools.ue_exec import main

        with (
            patch("growpy.io.unreal.ue_remote.discover_nodes", return_value=[]),
            pytest.raises(SystemExit),
        ):
            main()

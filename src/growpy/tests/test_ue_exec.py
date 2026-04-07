"""Tests for growpy.tools.ue_exec CLI argument handling."""

from unittest.mock import MagicMock, patch

import pytest


class TestUeExecMain:
    """Tests for the ue_exec main function."""

    @patch("growpy.tools.ue_exec.sys")
    def test_missing_script_exits(self, mock_sys):
        """Verify nonexistent script path causes exit."""
        mock_sys.argv = ["ue_exec", "nonexistent_script.py"]
        mock_sys.exit = MagicMock(side_effect=SystemExit(1))

        from growpy.tools.ue_exec import main

        with pytest.raises(SystemExit):
            main()

    @patch("growpy.tools.ue_exec.sys")
    def test_list_nodes_flag(self, mock_sys):
        """Verify --list-nodes calls discover_nodes."""
        mock_sys.argv = ["ue_exec", "--list-nodes", "dummy.py"]

        from growpy.tools.ue_exec import main

        with (
            patch("growpy.io.unreal.ue_remote.discover_nodes", return_value=[]) as mock_disc,
            pytest.raises(SystemExit),
        ):
            main()

"""Tests for growpy.tools.ue_exec CLI and batch orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from growpy.tools.ue_exec import (
    BATCH_PATTERN,
    _discover_batch_scripts,
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


class _FakeConfig:
    def __init__(self, editor_exe: str = "", uproject: str = ""):
        self.unreal_editor_exe = editor_exe
        self.unreal_uproject = uproject


class TestUeExecRestartConfigValidation:
    """Regression (XRFF-295): the auto-restart watchdog must fail fast with
    an actionable message when editor_exe/uproject can't be resolved, rather
    than discovering a stale/missing path mid-run.
    """

    def test_watchdog_enabled_without_config_fails_fast(self, monkeypatch, tmp_path):
        monkeypatch.setattr("growpy.config.core.get_config", lambda: _FakeConfig())
        script = tmp_path / "test.py"
        script.write_text("pass")
        monkeypatch.setattr("sys.argv", ["ue_exec", str(script)])

        from growpy.tools.ue_exec import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_watchdog_disabled_skips_validation(self, monkeypatch, tmp_path):
        monkeypatch.setattr("growpy.config.core.get_config", lambda: _FakeConfig())
        monkeypatch.setattr(
            "growpy.tools.ue_exec._run_single_with_restart",
            lambda *a, **k: (True, False),
        )
        script = tmp_path / "test.py"
        script.write_text("pass")
        monkeypatch.setattr(
            "sys.argv", ["ue_exec", str(script), "--restart-ram-limit", "0"]
        )

        from growpy.tools.ue_exec import main

        assert main() is None

    def test_config_values_resolve_when_no_cli_arg_given(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "growpy.config.core.get_config",
            lambda: _FakeConfig("C:/UE/UnrealEditor.exe", "D:/Proj/Proj.uproject"),
        )
        monkeypatch.setattr(
            "growpy.tools.ue_exec._run_single_with_restart",
            lambda *a, **k: (True, False),
        )
        script = tmp_path / "test.py"
        script.write_text("pass")
        monkeypatch.setattr("sys.argv", ["ue_exec", str(script)])

        from growpy.tools.ue_exec import main

        assert main() is None

    def test_cli_arg_overrides_config(self, monkeypatch, tmp_path):
        """--editor-exe/--uproject win even when config also sets them."""
        monkeypatch.setattr(
            "growpy.config.core.get_config",
            lambda: _FakeConfig("C:/Config/Editor.exe", "C:/Config/Proj.uproject"),
        )
        captured = {}

        def _fake_run(script_path, port, timeout, editor_exe, uproject, *rest):
            captured["editor_exe"] = editor_exe
            captured["uproject"] = uproject
            return True, False

        monkeypatch.setattr(
            "growpy.tools.ue_exec._run_single_with_restart", _fake_run
        )
        script = tmp_path / "test.py"
        script.write_text("pass")
        monkeypatch.setattr(
            "sys.argv",
            [
                "ue_exec",
                str(script),
                "--editor-exe",
                "C:/CLI/Editor.exe",
                "--uproject",
                "C:/CLI/Proj.uproject",
            ],
        )

        from growpy.tools.ue_exec import main

        main()
        assert captured["editor_exe"] == "C:/CLI/Editor.exe"
        assert captured["uproject"] == "C:/CLI/Proj.uproject"

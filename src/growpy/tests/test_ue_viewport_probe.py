"""Tests for growpy.tools.ue_viewport_probe.

No live UE editor / no real Remote Execution socket traffic. The "UE side"
of a live run is simulated by monkeypatching
growpy.io.unreal.ue_remote.run_file to write the result JSON the generated
in-editor script would have written, mirroring test_ue_exec.py's approach
of mocking at the transport boundary rather than the orchestration logic.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from growpy.tools.ue_viewport_probe import (
    CAMERA_FOV_DEG,
    EDITOR_IDLE_FRAME_MS,
    FRONT_CAMERA_LOCATION,
    RESULT_JSON_NAME,
    SCRIPT_NAME,
    SIDE_CAMERA_ROTATION,
    SUN_INTENSITY_LUX,
    SUN_ROTATION,
    generate_viewport_probe_script,
    main,
    run_viewport_probe,
)


class TestGenerateScript:
    def test_writes_script_file(self, tmp_path):
        path = generate_viewport_probe_script(tmp_path, ["/Game/Trees/SK_Oak_assembly"])
        assert path == tmp_path / SCRIPT_NAME
        assert path.is_file()

    def test_generated_script_is_valid_python(self, tmp_path):
        """The script is only ever exec'd inside UE, so a syntax error would
        otherwise surface as an opaque remote-exec failure."""
        import ast

        path = generate_viewport_probe_script(
            tmp_path, ["/Game/Trees/SK_Oak_assembly", "/Game/Trees/SK_Ash_assembly"]
        )
        ast.parse(path.read_text(encoding="utf-8"))

    def test_bakes_asset_paths(self, tmp_path):
        assets = ["/Game/Trees/SK_Oak_assembly", "/Game/Trees/SK_Beech_assembly"]
        path = generate_viewport_probe_script(tmp_path, assets)
        text = path.read_text(encoding="utf-8")
        for a in assets:
            assert a in text

    def test_bakes_camera_and_lighting_constants(self, tmp_path):
        path = generate_viewport_probe_script(tmp_path, ["/Game/Trees/SK_Oak_assembly"])
        text = path.read_text(encoding="utf-8")
        assert repr(float(CAMERA_FOV_DEG)) in text
        assert str(FRONT_CAMERA_LOCATION[0]) in text
        assert str(SIDE_CAMERA_ROTATION[1]) in text
        assert str(SUN_INTENSITY_LUX) in text

    def test_deterministic_across_calls(self, tmp_path):
        """Same inputs must produce byte-identical scripts -- a visual
        critic diffs screenshots across rounds, so the generator itself
        must not introduce nondeterminism (e.g. dict/set ordering)."""
        assets = ["/Game/Trees/SK_Oak_assembly"]
        p1 = generate_viewport_probe_script(tmp_path / "a", assets)
        p2 = generate_viewport_probe_script(tmp_path / "b", assets)

        # Strip the only path-dependent lines (script_path/result_json_path/
        # screenshot_dir differ because output_dir differs) before comparing.
        def _strip_paths(text):
            return "\n".join(
                line
                for line in text.splitlines()
                if "SCRIPT_PATH" not in line
                and "RESULT_JSON_PATH" not in line
                and "SCREENSHOT_DIR" not in line
                and "exec(open" not in line
            )

        assert _strip_paths(p1.read_text(encoding="utf-8")) == _strip_paths(
            p2.read_text(encoding="utf-8")
        )

    def test_custom_window_and_resolution(self, tmp_path):
        path = generate_viewport_probe_script(
            tmp_path,
            ["/Game/Trees/SK_Oak_assembly"],
            width=1280,
            height=720,
            measurement_window_s=2.5,
        )
        text = path.read_text(encoding="utf-8")
        assert "SCREENSHOT_WIDTH = 1280" in text
        assert "SCREENSHOT_HEIGHT = 720" in text
        assert "MEASUREMENT_WINDOW_S = 2.5" in text


class TestGeneratedScriptAvoidsKnownFailureModes:
    """Guards against regressions of bugs found against a live UE 5.7.4 editor."""

    def _script(self, tmp_path):
        return generate_viewport_probe_script(
            tmp_path, ["/Game/Trees/SK_Oak_assembly"]
        ).read_text(encoding="utf-8")

    def test_no_kismet_system_library(self, tmp_path):
        # unreal.KismetSystemLibrary does not exist in UE 5.7's Python API;
        # unreal.SystemLibrary is the real symbol.
        assert "KismetSystemLibrary" not in self._script(tmp_path)

    def test_no_queued_screenshot_apis(self, tmp_path):
        # take_high_res_screenshot / HighResShot only queue a request for a
        # later viewport draw, which never arrives while a Remote Execution
        # script holds the game thread. The abandoned requests also crashed
        # the editor once GC collected them.
        # (Both are named in the script's explanatory comments, so assert on
        # call syntax rather than on the bare names.)
        text = self._script(tmp_path)
        assert "unreal.AutomationLibrary" not in text
        assert "execute_console_command" not in text

    def test_no_blocking_sleep_around_frame_count(self, tmp_path):
        # Sleeping inside the script cannot measure frames: the editor
        # cannot tick until the script returns.
        text = self._script(tmp_path)
        assert "time.sleep" not in text

    def test_uses_slate_post_tick_callback(self, tmp_path):
        text = self._script(tmp_path)
        assert "register_slate_post_tick_callback" in text
        assert "unregister_slate_post_tick_callback" in text

    def test_captures_via_scene_capture(self, tmp_path):
        text = self._script(tmp_path)
        assert "SceneCapture2D" in text
        assert "capture_scene()" in text
        assert "export_render_target" in text

    def test_rotators_built_by_keyword(self, tmp_path):
        # unreal.Rotator's positional order is (roll, pitch, yaw), but this
        # module's constants are (pitch, yaw, roll). Passing them
        # positionally pitched the side camera 90 degrees at the sky.
        text = self._script(tmp_path)
        assert "unreal.Rotator(*rotation)" not in text
        assert "unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)" in text

    def test_does_not_save_a_level_asset(self, tmp_path):
        # LevelEditorSubsystem.new_level(asset_path) *saves* a new level
        # asset at asset_path; pointing it at an /Engine template failed and
        # left the user's own level open to be spawned into.
        text = self._script(tmp_path)
        assert "new_blank_map" in text
        assert "unreal.LevelEditorSubsystem" not in text
        assert ".new_level(" not in text
        assert ".new_level_from_template(" not in text

    def test_aborts_when_scratch_map_does_not_load(self, tmp_path):
        text = self._script(tmp_path)
        assert "Refusing to place actors" in text


class TestRunViewportProbeDryRun:
    def test_dry_run_writes_but_does_not_deliver(self, tmp_path):
        with patch("growpy.io.unreal.ue_remote.run_file") as mock_run_file:
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=True
            )
        mock_run_file.assert_not_called()
        assert record["dry_run"] is True
        assert Path(record["script_path"]).is_file()
        assert record["asset_count"] == 1

    def test_dry_run_result_json_not_created(self, tmp_path):
        run_viewport_probe(tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=True)
        assert not (tmp_path / RESULT_JSON_NAME).is_file()


def _fake_success_result_json(output_dir: Path, **overrides):
    payload = {
        "schema_version": "2.0",
        "complete": True,
        "engine_version": "5.7.4-51494982+++UE5+Release-5.7",
        "scratch_map": "new_blank_map -> /Temp/Untitled_1.Untitled_1",
        "asset_count_requested": 1,
        "asset_count_placed": 1,
        "screenshots": {
            "front": {
                "path": str(output_dir / "screenshots" / "front.png"),
                "method": "scene_capture_2d",
            },
            "side": {
                "path": str(output_dir / "screenshots" / "side.png"),
                "method": "scene_capture_2d",
            },
        },
        "screenshot_method": "scene_capture_2d",
        "render_time_ms": 9.0,
        "render_time_stats": {
            "samples": 10,
            "median_ms": 9.0,
            "mean_ms": 9.4,
            "min_ms": 8.8,
            "max_ms": 14.2,
        },
        "render_flush_baseline": {"samples": 10, "median_ms": 1.66},
        "render_time_method": "scene_capture_2d capture_scene()+GPU flush",
        "frame_time_ms": 35.0,
        "frame_count_measured": 143,
        "measurement_window_s": 5.0,
        "frame_time_method": "slate_post_tick_wall_clock",
        "editor_throttled": False,
        "frame_time_notes": ["143 slate post-tick callbacks over 5.010s"],
        "camera_constants": {"fov_deg": CAMERA_FOV_DEG},
        "lighting_constants": {"sun_rotation": list(SUN_ROTATION)},
        "errors": [],
    }
    payload.update(overrides)
    (output_dir / RESULT_JSON_NAME).write_text(json.dumps(payload), encoding="utf-8")
    return payload


class TestRunViewportProbeLive:
    def test_success_reads_back_payload(self, tmp_path):
        def _fake_run_file(*args, **kwargs):
            _fake_success_result_json(tmp_path)
            return {"success": True, "output": [{"output": "Viewport probe complete"}]}

        with patch("growpy.io.unreal.ue_remote.run_file", side_effect=_fake_run_file):
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["dry_run"] is False
        assert record["remote_exec_success"] is True
        assert record["ok"] is True
        assert record["measurement_complete"] is True
        assert record["payload"]["frame_time_ms"] == 35.0
        assert record["payload"]["frame_count_measured"] == 143
        assert record["payload"]["render_time_ms"] == 9.0

    def test_errors_in_payload_mark_not_ok(self, tmp_path):
        def _fake_run_file(*args, **kwargs):
            _fake_success_result_json(
                tmp_path, errors=["Could not spawn DirectionalLight"]
            )
            return {"success": True, "output": []}

        with patch("growpy.io.unreal.ue_remote.run_file", side_effect=_fake_run_file):
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["remote_exec_success"] is True
        assert record["ok"] is False  # payload reported errors

    def test_connection_error_is_reported_not_raised(self, tmp_path):
        with patch(
            "growpy.io.unreal.ue_remote.run_file",
            side_effect=ConnectionError("no UE editor found"),
        ):
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["ok"] is False
        assert "no UE editor found" in record["error"]

    def test_stale_result_json_is_not_reused_on_failure(self, tmp_path):
        # A previous run's result.json is on disk; this run's remote-exec
        # fails before the script can overwrite it -- must not report the
        # stale payload as this run's result.
        _fake_success_result_json(tmp_path)
        with patch(
            "growpy.io.unreal.ue_remote.run_file",
            side_effect=RuntimeError("editor did not respond"),
        ):
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["ok"] is False
        assert not (tmp_path / RESULT_JSON_NAME).is_file()

    def test_missing_result_json_after_success_is_handled(self, tmp_path):
        with patch(
            "growpy.io.unreal.ue_remote.run_file",
            return_value={"success": True, "output": []},
        ):
            record = run_viewport_probe(
                tmp_path,
                ["/Game/Trees/SK_Oak_assembly"],
                dry_run=False,
                collect_timeout_s=0.0,
            )
        assert record["remote_exec_success"] is True
        assert record["payload"] is None
        assert record["ok"] is False
        assert record["measurement_complete"] is False


class TestCollectPolling:
    """The editor only ticks after remote-exec returns, so the frame-time
    result lands in the JSON *after* run_file() has already come back."""

    def test_incomplete_payload_is_returned_with_a_note(self, tmp_path):
        def _fake_run_file(*args, **kwargs):
            # Synchronous phase only: screenshots done, frame timing pending.
            _fake_success_result_json(
                tmp_path,
                complete=False,
                frame_time_ms=None,
                frame_count_measured=0,
                frame_time_method=None,
                frame_time_notes=[],
            )
            return {"success": True, "output": []}

        with patch("growpy.io.unreal.ue_remote.run_file", side_effect=_fake_run_file):
            record = run_viewport_probe(
                tmp_path,
                ["/Game/Trees/SK_Oak_assembly"],
                dry_run=False,
                collect_timeout_s=0.0,
            )
        assert record["measurement_complete"] is False
        assert record["payload"] is not None
        # Screenshots from the synchronous phase survive.
        assert record["payload"]["screenshots"]["front"]["method"] == "scene_capture_2d"
        assert any(
            "stopped polling" in n for n in record["payload"]["frame_time_notes"]
        )

    def test_complete_payload_returns_without_waiting(self, tmp_path):
        """A payload already marked complete must short-circuit the poll
        loop so tests (and fast editors) never sleep."""

        def _fake_run_file(*args, **kwargs):
            _fake_success_result_json(tmp_path)
            return {"success": True, "output": []}

        with patch("growpy.io.unreal.ue_remote.run_file", side_effect=_fake_run_file):
            with patch("growpy.tools.ue_viewport_probe.time.sleep") as mock_sleep:
                record = run_viewport_probe(
                    tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
                )
        mock_sleep.assert_not_called()
        assert record["measurement_complete"] is True


class TestSummaryHonesty:
    def test_throttled_measurement_is_flagged(self, tmp_path, capsys):
        from growpy.tools.ue_viewport_probe import _print_summary

        payload = _fake_success_result_json(
            tmp_path,
            frame_time_ms=277.9,
            frame_rate_hz=3.6,
            frame_count_measured=19,
            editor_throttled=True,
        )
        _print_summary({"remote_exec_success": True, "payload": payload, "ok": False})
        out = capsys.readouterr().out
        assert "editor throttled" in out

    def test_idle_threshold_covers_observed_backgrounded_rates(self):
        """Both rates measured against a backgrounded live editor (333.4 ms
        with 3 assemblies, 277.9 ms with 9) must be classed as idle-bound,
        while the 35.0 ms measured with the editor focused must not."""
        assert 333.4 >= EDITOR_IDLE_FRAME_MS
        assert 277.9 >= EDITOR_IDLE_FRAME_MS
        assert 35.0 < EDITOR_IDLE_FRAME_MS

    def test_single_frame_measurement_is_flagged_as_noise(self, tmp_path, capsys):
        from growpy.tools.ue_viewport_probe import _print_summary

        payload = _fake_success_result_json(tmp_path, frame_count_measured=1)
        _print_summary(
            {"remote_exec_success": True, "payload": payload, "ok": False}
        )
        out = capsys.readouterr().out
        assert "noise" in out


class TestMain:
    def test_dry_run_with_explicit_assets_exits_0(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-viewport-probe",
                str(tmp_path),
                "--assets",
                "/Game/Trees/SK_Oak_assembly",
                "--dry-run",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_no_source_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv", ["growpy-ue-viewport-probe", str(tmp_path), "--dry-run"]
        )
        with pytest.raises(SystemExit):
            main()

    def test_tree_inventory_missing_file_exits_1(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-viewport-probe",
                str(tmp_path),
                "--tree-inventory",
                str(tmp_path / "nope.json"),
                "--dry-run",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_tree_inventory_sources_assets(self, monkeypatch, tmp_path):
        inventory = tmp_path / "tree_inventory.json"
        inventory.write_text(
            json.dumps(
                [
                    {"SkeletalMesh": "/Game/Trees/SK_Oak_assembly.SK_Oak_assembly"},
                    {"SkeletalMesh": "/Game/Trees/SK_Beech_assembly.SK_Beech_assembly"},
                ]
            ),
            encoding="utf-8",
        )
        out_dir = tmp_path / "out"
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-viewport-probe",
                str(out_dir),
                "--tree-inventory",
                str(inventory),
                "--count",
                "1",
                "--dry-run",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        script_text = (out_dir / SCRIPT_NAME).read_text(encoding="utf-8")
        assert "/Game/Trees/SK_Oak_assembly.SK_Oak_assembly" in script_text
        # --count 1 caps sourcing to the first row only.
        assert "/Game/Trees/SK_Beech_assembly.SK_Beech_assembly" not in script_text

    def test_dry_run_writes_json_record(self, monkeypatch, tmp_path):
        json_out = tmp_path / "record.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "growpy-ue-viewport-probe",
                str(tmp_path / "out"),
                "--assets",
                "/Game/Trees/SK_Oak_assembly",
                "--dry-run",
                "--json",
                str(json_out),
            ],
        )
        with pytest.raises(SystemExit):
            main()
        assert json_out.is_file()
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["dry_run"] is True

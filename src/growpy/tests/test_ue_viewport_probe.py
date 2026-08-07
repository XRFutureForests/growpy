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
        "schema_version": "1.0",
        "engine_version": "5.7.0-00000000+++UE5",
        "asset_count_requested": 1,
        "asset_count_placed": 1,
        "screenshots": {
            "front": {
                "path": str(output_dir / "screenshots" / "front.png"),
                "method": "automation_library",
            },
            "side": {
                "path": str(output_dir / "screenshots" / "side.png"),
                "method": "automation_library",
            },
        },
        "frame_time_ms": 16.7,
        "frame_count_measured": 299,
        "measurement_window_s": 5.0,
        "frame_time_method": "fps_chart_csv",
        "frame_time_notes": ["StartFPSChart/StopFPSChart CSV: fake.csv"],
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

        with patch(
            "growpy.io.unreal.ue_remote.run_file", side_effect=_fake_run_file
        ):
            record = run_viewport_probe(
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["dry_run"] is False
        assert record["remote_exec_success"] is True
        assert record["ok"] is True
        assert record["payload"]["frame_time_ms"] == 16.7
        assert record["payload"]["frame_count_measured"] == 299

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
                tmp_path, ["/Game/Trees/SK_Oak_assembly"], dry_run=False
            )
        assert record["remote_exec_success"] is True
        assert record["payload"] is None
        assert record["ok"] is False


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

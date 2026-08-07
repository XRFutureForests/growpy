"""Measurement probe: deterministic screenshot + frame-time capture in UE.

Generates a standalone UE Python script -- following the same
generate-a-script-and-deliver-via-Remote-Execution pattern already used by
``growpy.io.unreal.nanite_voxelize_script``, ``wind_import_script``, and
``pve_import_script`` -- that, inside the editor:

1. Loads a blank scratch level (the same ``Template_Default`` trick
   ``growpy.tools.ue_exec``'s ``_UE_CLEANUP_SCRIPT`` uses to reclaim Nanite
   VRAM) and never saves it, so nothing in the project is touched.
2. Places N assemblies at deterministic transforms.
3. Spawns exactly one directional light and two cameras (front/side) at
   the fixed transforms baked into this module -- see the "DETERMINISTIC
   CONSTANTS" section below. Any pre-existing Light actors in the scratch
   level are removed first so lighting is fully determined by this script,
   not by whatever the map template happens to ship with.
4. Captures front/side screenshots to a known path.
5. Measures frame time over a fixed wall-clock window and reports how many
   frames the average covers.
6. Writes a JSON result file to disk (host-readable) -- mirroring
   ``unreal_scripts._build_datatable_script``'s "always save to disk first"
   pattern, so a partial failure downstream (e.g. screenshot capture
   raising) does not lose whatever succeeded.

Frame-time API caveat (read before trusting the numbers)
----------------------------------------------------------
This was authored without a running UE 5.7 editor to test against (see the
HARD CONSTRAINT this tool was built under), so neither Python API below
could be verified live. The generated script tries them in order and
records which one actually worked:

* Primary: the console commands ``StartFPSChart`` / ``StopFPSChart``
  (``FPerformanceMonitor``, part of UE's engine-level performance-profiling
  surface since UE4, invoked the same way ``ue_exec``'s cleanup script
  invokes other console commands -- via
  ``KismetSystemLibrary.execute_console_command``). Stopping the chart
  writes a CSV under ``<Project>/Saved/Profiling/FPSChartStats/`` that
  includes both the frame count and the average frame time for the
  window; the script locates the newest CSV after stopping and parses it.
  This is chosen as primary because it is a stable, long-documented
  console-command surface rather than a specific Python reflection symbol
  that could differ by engine version.
* Fallback: sampling ``unreal.SystemLibrary.get_frame_count()`` before and
  after a fixed ``time.sleep()`` window and dividing elapsed wall-clock
  time by the frame delta. This mirrors the Blueprint "Get Frame Count"
  node (``UKismetSystemLibrary::GetFrameCount``), which has existed since
  early UE4 and is very likely still exposed, but note this counts engine
  ticks, not necessarily viewport redraws, when the editor viewport is not
  in realtime mode -- the generated script forces realtime on the active
  viewport first (``unreal.LevelEditorSubsystem.editor_set_game_view``/
  viewport realtime toggle, again multi-strategy) to make this
  meaningful, but that toggle itself could not be verified live either.

If both fail, the script records ``"frame_time_ms": null`` with an
explicit reason string rather than fabricating a number.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("growpy.ue_viewport_probe")

SCHEMA_VERSION = "1.0"

# --- DETERMINISTIC CONSTANTS -------------------------------------------
# These are baked into every generated script byte-for-byte identically.
# A visual critic diffs screenshots across probe rounds, so framing, FOV,
# camera transform, light direction/intensity, and exposure must never
# depend on editor state, viewport size, or whatever the user last had
# open. Do not derive any of these from live editor state -- if a value
# needs to change, change it here (and expect screenshots to no longer be
# diffable against older rounds).
CAMERA_FOV_DEG = 50.0
CAMERA_DISTANCE_CM = 1500.0
CAMERA_HEIGHT_CM = 400.0
FRONT_CAMERA_LOCATION = (-CAMERA_DISTANCE_CM, 0.0, CAMERA_HEIGHT_CM)
FRONT_CAMERA_ROTATION = (0.0, 0.0, 0.0)  # (pitch, yaw, roll) deg -- looks along +X
SIDE_CAMERA_LOCATION = (0.0, -CAMERA_DISTANCE_CM, CAMERA_HEIGHT_CM)
SIDE_CAMERA_ROTATION = (0.0, 90.0, 0.0)  # looks along +Y

SUN_ROTATION = (-45.0, -45.0, 0.0)  # (pitch, yaw, roll) deg
SUN_INTENSITY_LUX = 10.0
SUN_COLOR_RGB = (1.0, 1.0, 1.0)

# Manual exposure, fixed -- so screenshots don't shift with scene content.
EXPOSURE_METHOD = "MANUAL"
EXPOSURE_BIAS = 0.0
EXPOSURE_ISO = 100.0
EXPOSURE_APERTURE_FSTOP = 4.0
EXPOSURE_SHUTTER_SPEED = 1.0 / 60.0

ASSEMBLY_ROW_SPACING_CM = 500.0  # deterministic placement along +X, starting at origin

DEFAULT_MEASUREMENT_WINDOW_S = 5.0
DEFAULT_SCREENSHOT_WIDTH = 1920
DEFAULT_SCREENSHOT_HEIGHT = 1080

RESULT_JSON_NAME = "growpy_viewport_probe_result.json"
SCRIPT_NAME = "growpy_viewport_probe.py"


def _fmt_tuple(t: tuple[float, ...]) -> str:
    return "(" + ", ".join(repr(float(v)) for v in t) + ")"


_SCRIPT_BODY = '''"""
GrowPy Viewport Probe - Auto-generated (schema v{schema_version}).

Places {count} assembly/assemblies at deterministic transforms in a scratch
level, sets a fixed camera and fixed lighting (see the constants below --
these are baked in by the host-side generator and must be byte-identical
across probe rounds), captures front/side screenshots, and measures frame
time. Writes a JSON result file next to this script so the host-side probe
can read it back after Remote Execution returns.

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r"{script_path}").read())
"""

import gc
import glob
import json
import os
import time
import unreal


SCHEMA_VERSION = "{schema_version}"
ASSET_PATHS = {asset_paths!r}
RESULT_JSON_PATH = r"{result_json_path}"
SCREENSHOT_DIR = r"{screenshot_dir}"
FRONT_SCREENSHOT_PATH = os.path.join(SCREENSHOT_DIR, "front.png")
SIDE_SCREENSHOT_PATH = os.path.join(SCREENSHOT_DIR, "side.png")
SCREENSHOT_WIDTH = {width}
SCREENSHOT_HEIGHT = {height}
MEASUREMENT_WINDOW_S = {measurement_window_s}
ROW_SPACING_CM = {row_spacing}

# --- Deterministic camera/lighting constants (see ue_viewport_probe.py) ---
CAMERA_FOV_DEG = {camera_fov}
FRONT_CAMERA_LOCATION = {front_cam_loc}
FRONT_CAMERA_ROTATION = {front_cam_rot}
SIDE_CAMERA_LOCATION = {side_cam_loc}
SIDE_CAMERA_ROTATION = {side_cam_rot}
SUN_ROTATION = {sun_rot}
SUN_INTENSITY_LUX = {sun_intensity}
SUN_COLOR_RGB = {sun_color}
EXPOSURE_BIAS = {exposure_bias}
EXPOSURE_ISO = {exposure_iso}
EXPOSURE_APERTURE_FSTOP = {exposure_aperture}
EXPOSURE_SHUTTER_SPEED = {exposure_shutter}


def _get_editor_world():
    """Mirrors unreal_scripts._get_ue_world's dual-strategy lookup."""
    try:
        _sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        return _sub.get_editor_world()
    except Exception:
        pass
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None


def _get_actor_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        return None


def _get_all_level_actors():
    sub = _get_actor_subsystem()
    if sub is not None:
        try:
            return list(sub.get_all_level_actors())
        except Exception:
            pass
    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return []


def _spawn_actor(actor_class, location, rotation):
    """Multi-strategy actor spawn (EditorActorSubsystem, then legacy)."""
    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)
    sub = _get_actor_subsystem()
    if sub is not None:
        try:
            return sub.spawn_actor_from_class(actor_class, loc, rot)
        except Exception as e:
            print(f"  spawn_actor_from_class (subsystem) failed: {{e}}")
    try:
        return unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, loc, rot)
    except Exception as e:
        print(f"  spawn_actor_from_class (legacy) failed: {{e}}")
    return None


def _spawn_actor_from_object(asset, location, rotation):
    """Multi-strategy asset-actor spawn, mirroring the same fallback shape."""
    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)
    sub = _get_actor_subsystem()
    if sub is not None:
        try:
            return sub.spawn_actor_from_object(asset, loc, rot)
        except Exception as e:
            print(f"  spawn_actor_from_object (subsystem) failed: {{e}}")
    try:
        return unreal.EditorLevelLibrary.spawn_actor_from_object(asset, loc, rot)
    except Exception as e:
        print(f"  spawn_actor_from_object (legacy) failed: {{e}}")
    return None


def _new_scratch_level():
    """Load a blank template level without saving -- same trick ue_exec's
    _UE_CLEANUP_SCRIPT uses to release Nanite VRAM. Nothing here is ever
    persisted to disk."""
    try:
        sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        sub.new_level("/Engine/Maps/Templates/Template_Default")
        return True
    except Exception:
        pass
    try:
        unreal.EditorLevelLibrary.new_level("/Engine/Maps/Templates/Template_Default")
        return True
    except Exception as e:
        print(f"  Could not load scratch level: {{e}}")
        return False


def _clear_existing_lights():
    """Remove any Light-derived actors the template map ships with, so
    lighting is fully determined by SUN_ROTATION/SUN_INTENSITY_LUX below,
    not by whatever Template_Default happens to contain."""
    removed = 0
    for actor in _get_all_level_actors():
        try:
            if isinstance(actor, unreal.Light):
                actor.destroy_actor()
                removed += 1
        except Exception:
            pass
    print(f"  Removed {{removed}} pre-existing light actor(s)")
    return removed


def _set_manual_exposure(camera_actor):
    """Fix exposure so screenshots don't shift with scene content."""
    try:
        cam_comp = camera_actor.camera_component
        pp = cam_comp.post_process_settings
        pp.set_editor_property("bOverride_AutoExposureMethod", True)
        pp.set_editor_property(
            "auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL
        )
        pp.set_editor_property("bOverride_AutoExposureBias", True)
        pp.set_editor_property("auto_exposure_bias", EXPOSURE_BIAS)
        pp.set_editor_property("bOverride_CameraISO", True)
        pp.set_editor_property("camera_iso", EXPOSURE_ISO)
        pp.set_editor_property("bOverride_DepthOfFieldFstop", True)
        pp.set_editor_property("depth_of_field_fstop", EXPOSURE_APERTURE_FSTOP)
        cam_comp.post_process_settings = pp
        cam_comp.set_editor_property("field_of_view", CAMERA_FOV_DEG)
        return True
    except Exception as e:
        print(f"  Could not fix camera exposure/FOV: {{e}}")
        return False


def _take_screenshot(camera_actor, out_path):
    """Multi-strategy screenshot capture: AutomationLibrary first (ties the
    shot to a specific camera), console-command HighResShot as fallback
    (ties to whichever viewport/camera is currently active)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        unreal.AutomationLibrary.take_high_res_screenshot(
            SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT, out_path,
            camera=camera_actor.camera_component,
        )
        time.sleep(2.0)  # screenshot capture is asynchronous
        if os.path.isfile(out_path):
            return "automation_library"
    except Exception as e:
        print(f"  take_high_res_screenshot failed: {{e}}")
    try:
        world = _get_editor_world()
        if world is not None:
            cmd = 'HighResShot {{}}x{{}} filename="{{}}"'.format(
                SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT, out_path
            )
            unreal.KismetSystemLibrary.execute_console_command(world, cmd)
            time.sleep(3.0)
            if os.path.isfile(out_path):
                return "console_highresshot"
    except Exception as e:
        print(f"  HighResShot console command failed: {{e}}")
    return None


def _measure_frame_time_via_fps_chart(world):
    """Primary strategy: StartFPSChart/StopFPSChart console commands,
    parsing the CSV they write under Saved/Profiling/FPSChartStats/."""
    try:
        saved_dir = unreal.Paths.project_saved_dir()
        saved_dir = unreal.Paths.convert_relative_path_to_full(saved_dir)
        chart_dir = os.path.join(saved_dir, "Profiling", "FPSChartStats")
        csv_glob = os.path.join(chart_dir, "**", "*.csv")
        before = set(glob.glob(csv_glob, recursive=True))
        unreal.KismetSystemLibrary.execute_console_command(world, "StartFPSChart")
        time.sleep(MEASUREMENT_WINDOW_S)
        unreal.KismetSystemLibrary.execute_console_command(world, "StopFPSChart")
        time.sleep(1.0)
        after = set(glob.glob(csv_glob, recursive=True))
        new_only = after - before
        new_files = sorted(new_only or after, key=os.path.getmtime)
        if not new_files:
            return None, 0, "no FPSChartStats CSV appeared after StopFPSChart"
        csv_path = new_files[-1]
        with open(csv_path, "r") as f:
            header = f.readline().strip().split(",")
            row = f.readline().strip().split(",")
        cols = {{h.strip().lower(): v for h, v in zip(header, row)}}
        frame_count = None
        for key in ("frame count", "framecount", "numframes"):
            if key in cols:
                frame_count = int(float(cols[key]))
                break
        avg_ms = None
        for key in ("avg frametime", "avgframetime", "average frame time"):
            if key in cols:
                avg_ms = float(cols[key])
                break
        if avg_ms is None and frame_count:
            avg_ms = (MEASUREMENT_WINDOW_S * 1000.0) / frame_count
        if avg_ms is None:
            return (
                None,
                frame_count or 0,
                f"could not find frame-time column in {{csv_path}}",
            )
        return avg_ms, frame_count or 0, f"StartFPSChart/StopFPSChart CSV: {{csv_path}}"
    except Exception as e:
        return None, 0, f"FPS chart strategy raised: {{e}}"


def _measure_frame_time_via_frame_count(world):
    """Fallback strategy: sample SystemLibrary.get_frame_count() before/after
    a fixed sleep. Counts engine ticks, not confirmed to equal viewport
    redraws outside of realtime/PIE -- see module docstring caveat."""
    try:
        f0 = unreal.SystemLibrary.get_frame_count()
        t0 = time.perf_counter()
        time.sleep(MEASUREMENT_WINDOW_S)
        f1 = unreal.SystemLibrary.get_frame_count()
        t1 = time.perf_counter()
        frame_delta = f1 - f0
        if frame_delta <= 0:
            return None, 0, "get_frame_count() did not advance during the window"
        avg_ms = (t1 - t0) * 1000.0 / frame_delta
        return avg_ms, frame_delta, "SystemLibrary.get_frame_count() delta"
    except Exception as e:
        return None, 0, f"get_frame_count strategy raised: {{e}}"


def main():
    print("=" * 60)
    print("GrowPy Viewport Probe")
    print("=" * 60)

    result = {{
        "schema_version": SCHEMA_VERSION,
        "engine_version": None,
        "asset_count_requested": len(ASSET_PATHS),
        "asset_count_placed": 0,
        "screenshots": {{}},
        "frame_time_ms": None,
        "frame_count_measured": 0,
        "measurement_window_s": MEASUREMENT_WINDOW_S,
        "frame_time_method": None,
        "frame_time_notes": [],
        "camera_constants": {{
            "fov_deg": CAMERA_FOV_DEG,
            "front_location": FRONT_CAMERA_LOCATION,
            "front_rotation": FRONT_CAMERA_ROTATION,
            "side_location": SIDE_CAMERA_LOCATION,
            "side_rotation": SIDE_CAMERA_ROTATION,
        }},
        "lighting_constants": {{
            "sun_rotation": SUN_ROTATION,
            "sun_intensity_lux": SUN_INTENSITY_LUX,
            "sun_color_rgb": SUN_COLOR_RGB,
        }},
        "errors": [],
    }}

    try:
        result["engine_version"] = unreal.SystemLibrary.get_engine_version()
    except Exception as e:
        result["errors"].append(f"get_engine_version failed: {{e}}")

    def _save_result():
        # Always write, even on partial failure -- mirrors
        # unreal_scripts._build_datatable_script's "save to disk first".
        try:
            os.makedirs(os.path.dirname(RESULT_JSON_PATH), exist_ok=True)
            with open(RESULT_JSON_PATH, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Wrote result JSON: {{RESULT_JSON_PATH}}")
        except Exception as e:
            print(f"  ** Could not write result JSON: {{e}}")

    if not _new_scratch_level():
        result["errors"].append("Could not load scratch level; aborting.")
        _save_result()
        return

    _clear_existing_lights()

    # --- Place assemblies at deterministic transforms ---
    placed = 0
    for i, asset_path in enumerate(ASSET_PATHS):
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if asset is None:
            result["errors"].append(f"Could not load asset: {{asset_path}}")
            continue
        location = (i * ROW_SPACING_CM, 0.0, 0.0)
        actor = _spawn_actor_from_object(asset, location, (0.0, 0.0, 0.0))
        if actor is None:
            result["errors"].append(f"Could not spawn actor for: {{asset_path}}")
            continue
        placed += 1
    result["asset_count_placed"] = placed
    print(f"Placed {{placed}}/{{len(ASSET_PATHS)}} assembly actor(s)")

    # --- Fixed lighting ---
    sun = _spawn_actor(unreal.DirectionalLight, (0.0, 0.0, 0.0), SUN_ROTATION)
    if sun is not None:
        try:
            light_comp = sun.light_component
            light_comp.set_editor_property("intensity", SUN_INTENSITY_LUX)
            light_comp.set_editor_property(
                "light_color",
                unreal.LinearColor(*SUN_COLOR_RGB, 1.0).to_color(True),
            )
        except Exception as e:
            result["errors"].append(f"Could not configure sun light: {{e}}")
    else:
        result["errors"].append("Could not spawn DirectionalLight")

    # --- Fixed cameras + screenshots ---
    world = _get_editor_world()

    front_cam = _spawn_actor(
        unreal.CameraActor, FRONT_CAMERA_LOCATION, FRONT_CAMERA_ROTATION
    )
    if front_cam is not None:
        _set_manual_exposure(front_cam)
        method = _take_screenshot(front_cam, FRONT_SCREENSHOT_PATH)
        result["screenshots"]["front"] = {{
            "path": FRONT_SCREENSHOT_PATH if method else None,
            "method": method,
        }}
        if not method:
            result["errors"].append(
                "Front screenshot capture failed (both strategies)."
            )
    else:
        result["errors"].append("Could not spawn front CameraActor")

    side_cam = _spawn_actor(
        unreal.CameraActor, SIDE_CAMERA_LOCATION, SIDE_CAMERA_ROTATION
    )
    if side_cam is not None:
        _set_manual_exposure(side_cam)
        method = _take_screenshot(side_cam, SIDE_SCREENSHOT_PATH)
        result["screenshots"]["side"] = {{
            "path": SIDE_SCREENSHOT_PATH if method else None,
            "method": method,
        }}
        if not method:
            result["errors"].append("Side screenshot capture failed (both strategies).")
    else:
        result["errors"].append("Could not spawn side CameraActor")

    # --- Frame time ---
    if world is not None:
        avg_ms, frame_count, note = _measure_frame_time_via_fps_chart(world)
        if avg_ms is None:
            result["frame_time_notes"].append(f"FPS chart strategy failed: {{note}}")
            avg_ms, frame_count, note = _measure_frame_time_via_frame_count(world)
            if avg_ms is not None:
                result["frame_time_method"] = "get_frame_count_delta"
        else:
            result["frame_time_method"] = "fps_chart_csv"
        result["frame_time_notes"].append(note)
        result["frame_time_ms"] = avg_ms
        result["frame_count_measured"] = frame_count
    else:
        result["errors"].append("No editor world -- skipped frame-time measurement.")

    gc.collect()
    unreal.SystemLibrary.collect_garbage()

    _save_result()

    print("")
    print("=" * 60)
    print(
        f"Viewport probe complete: {{placed}}/{{len(ASSET_PATHS)}} placed, "
        f"frame_time_ms={{result['frame_time_ms']}}, "
        f"method={{result['frame_time_method']}}, "
        f"{{len(result['errors'])}} error(s)"
    )
    print("=" * 60)


main()
'''


def generate_viewport_probe_script(
    output_dir: Path,
    asset_paths: list[str],
    *,
    width: int = DEFAULT_SCREENSHOT_WIDTH,
    height: int = DEFAULT_SCREENSHOT_HEIGHT,
    measurement_window_s: float = DEFAULT_MEASUREMENT_WINDOW_S,
) -> Path:
    """Write the UE-side viewport probe script to ``output_dir``.

    Returns the path to the generated script. Does not deliver it -- see
    :func:`run_viewport_probe` for that.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / SCRIPT_NAME
    result_json_path = output_dir / RESULT_JSON_NAME
    screenshot_dir = output_dir / "screenshots"

    body = _SCRIPT_BODY.format(
        schema_version=SCHEMA_VERSION,
        count=len(asset_paths),
        script_path=str(script_path.resolve()).replace("\\", "/"),
        asset_paths=list(asset_paths),
        result_json_path=str(result_json_path.resolve()).replace("\\", "/"),
        screenshot_dir=str(screenshot_dir.resolve()).replace("\\", "/"),
        width=width,
        height=height,
        measurement_window_s=measurement_window_s,
        row_spacing=ASSEMBLY_ROW_SPACING_CM,
        camera_fov=CAMERA_FOV_DEG,
        front_cam_loc=_fmt_tuple(FRONT_CAMERA_LOCATION),
        front_cam_rot=_fmt_tuple(FRONT_CAMERA_ROTATION),
        side_cam_loc=_fmt_tuple(SIDE_CAMERA_LOCATION),
        side_cam_rot=_fmt_tuple(SIDE_CAMERA_ROTATION),
        sun_rot=_fmt_tuple(SUN_ROTATION),
        sun_intensity=SUN_INTENSITY_LUX,
        sun_color=_fmt_tuple(SUN_COLOR_RGB),
        exposure_bias=EXPOSURE_BIAS,
        exposure_iso=EXPOSURE_ISO,
        exposure_aperture=EXPOSURE_APERTURE_FSTOP,
        exposure_shutter=EXPOSURE_SHUTTER_SPEED,
    )

    script_path.write_text(body, encoding="utf-8")
    logger.info("Generated viewport probe script: %s", script_path)
    return script_path


def run_viewport_probe(
    output_dir: Path,
    asset_paths: list[str],
    *,
    width: int = DEFAULT_SCREENSHOT_WIDTH,
    height: int = DEFAULT_SCREENSHOT_HEIGHT,
    measurement_window_s: float = DEFAULT_MEASUREMENT_WINDOW_S,
    port: int = 6776,
    timeout: float = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate the viewport probe script and, unless dry_run, deliver it.

    dry_run writes the script to disk and returns it without touching the
    network/UE at all. A live run delivers the script over Remote
    Execution (``ue_remote.run_file``, same primitive ue_exec uses) and
    reads back the JSON result file the script writes.
    """
    output_dir = Path(output_dir)
    script_path = generate_viewport_probe_script(
        output_dir,
        asset_paths,
        width=width,
        height=height,
        measurement_window_s=measurement_window_s,
    )
    script_text = script_path.read_text(encoding="utf-8")

    if dry_run:
        return {
            "dry_run": True,
            "script_path": str(script_path),
            "script": script_text,
            "asset_count": len(asset_paths),
        }

    from growpy.io.unreal.ue_remote import run_file

    result_json_path = output_dir / RESULT_JSON_NAME
    if result_json_path.exists():
        # Stale result from a previous run -- don't let it masquerade as
        # this run's output if the script fails before writing a new one.
        result_json_path.unlink()

    try:
        remote_result = run_file(
            str(script_path), timeout=timeout, command_endpoint=("127.0.0.1", port)
        )
    except (ConnectionError, RuntimeError) as e:
        return {
            "dry_run": False,
            "ok": False,
            "error": str(e),
            "script_path": str(script_path),
        }

    remote_success = bool(remote_result.get("success"))
    output_lines = [
        line.get("output", "") for line in (remote_result.get("output") or [])
    ]

    payload = None
    if result_json_path.is_file():
        try:
            payload = json.loads(result_json_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Could not parse result JSON at %s: %s", result_json_path, e)

    return {
        "dry_run": False,
        "ok": remote_success and payload is not None and not payload.get("errors"),
        "remote_exec_success": remote_success,
        "result_json_path": str(result_json_path),
        "payload": payload,
        "raw_output": output_lines,
        "script_path": str(script_path),
    }


def _print_summary(record: dict[str, Any]) -> None:
    print("=" * 72)
    print("GrowPy UE Viewport Probe")
    print("=" * 72)
    if not record.get("remote_exec_success"):
        print(f"Remote-exec FAILED: {record.get('error', 'unknown error')}")
        return
    payload = record.get("payload")
    if payload is None:
        print("Script ran but no result JSON was found/parsed.")
        return
    print(f"Engine version:      {payload.get('engine_version')}")
    print(
        f"Assemblies placed:   {payload.get('asset_count_placed')}"
        f"/{payload.get('asset_count_requested')}"
    )
    for view, info in (payload.get("screenshots") or {}).items():
        print(f"Screenshot [{view:>5}]: {info.get('path')} (via {info.get('method')})")
    print(
        f"Frame time:          {payload.get('frame_time_ms')} ms "
        f"over {payload.get('frame_count_measured')} frame(s) "
        f"in a {payload.get('measurement_window_s')}s window "
        f"(method: {payload.get('frame_time_method')})"
    )
    for note in payload.get("frame_time_notes") or []:
        print(f"  note: {note}")
    if payload.get("errors"):
        print(f"Errors ({len(payload['errors'])}):")
        for err in payload["errors"]:
            print(f"  - {err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Places assemblies at deterministic transforms in a scratch UE "
            "level, sets a fixed camera/lighting, captures front/side "
            "screenshots, and measures frame time via Remote Execution."
        ),
    )
    parser.add_argument(
        "output_dir",
        help="Directory to write the generated script and read back results.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--assets",
        nargs="+",
        default=None,
        help="Explicit UE Content Browser asset paths to place.",
    )
    source.add_argument(
        "--tree-inventory",
        type=Path,
        default=None,
        help=(
            "Path to tree_inventory.json (written by "
            "import_batch_100_datatable.py / growpy-ue-import-probe) to "
            "source assembly paths from."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of assemblies to place (default 5).",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_SCREENSHOT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_SCREENSHOT_HEIGHT)
    parser.add_argument(
        "--measurement-window",
        type=float,
        default=DEFAULT_MEASUREMENT_WINDOW_S,
        help="Frame-time measurement window in seconds (default 5.0).",
    )
    parser.add_argument("--port", type=int, default=6776)
    parser.add_argument("--timeout", type=float, default=0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the generated script to disk and print it; deliver nothing.",
    )
    parser.add_argument(
        "--json", default=None, help="Write the JSON record to this path."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if args.tree_inventory is not None:
        if not args.tree_inventory.is_file():
            logger.error("Tree inventory not found: %s", args.tree_inventory)
            sys.exit(1)
        try:
            rows = json.loads(args.tree_inventory.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Could not parse tree inventory JSON: %s", e)
            sys.exit(1)
        assets = [r["SkeletalMesh"] for r in rows[: args.count] if "SkeletalMesh" in r]
    elif args.assets:
        assets = list(args.assets[: args.count])
    else:
        parser.error("Provide --assets or --tree-inventory to source assemblies from.")

    if not assets:
        logger.error("No assemblies to place (empty source).")
        sys.exit(1)

    record = run_viewport_probe(
        Path(args.output_dir),
        assets,
        width=args.width,
        height=args.height,
        measurement_window_s=args.measurement_window,
        port=args.port,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(record["script"])
        logger.info("Generated script (not delivered): %s", record["script_path"])
    else:
        _print_summary(record)

    if args.json:
        Path(args.json).write_text(json.dumps(record, indent=2), encoding="utf-8")
        logger.info("Wrote JSON measurement record: %s", args.json)

    if args.dry_run:
        sys.exit(0)
    sys.exit(0 if record.get("ok") else 1)


if __name__ == "__main__":
    main()

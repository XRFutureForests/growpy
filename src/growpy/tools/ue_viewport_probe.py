"""Measurement probe: deterministic screenshot + frame-time capture in UE.

Generates a standalone UE Python script -- following the same
generate-a-script-and-deliver-via-Remote-Execution pattern already used by
``growpy.io.unreal.nanite_voxelize_script``, ``wind_import_script``, and
``pve_import_script`` -- that, inside the editor:

1. Loads a blank scratch map (transient, never written to disk) and
   **verifies it actually loaded**, aborting rather than falling through
   into whatever level the user had open.
2. Places N assemblies at deterministic transforms.
3. Spawns exactly one directional light at the fixed transform baked into
   this module -- see the "DETERMINISTIC CONSTANTS" section below. Any
   pre-existing Light actors in the scratch map are removed first so
   lighting is fully determined by this script.
4. Captures front/side images through ``SceneCapture2D`` actors carrying
   the fixed camera constants.
5. Measures render cost and editor tick rate, and reports how many samples
   / frames each number covers.
6. Writes a JSON result file to disk (host-readable) -- mirroring
   ``unreal_scripts._build_datatable_script``'s "always save to disk first"
   pattern, so a partial failure downstream does not lose what succeeded.

The Remote Execution tick model (verified against UE 5.7.4)
-----------------------------------------------------------
A script delivered over Remote Execution runs **synchronously on the game
thread**. While it runs the editor does not tick, so:

* ``time.sleep()`` inside the script measures nothing -- ``get_frame_count()``
  cannot advance, because no frame can be rendered until the script returns.
* Anything that *queues* work for a later tick never completes before the
  script returns. That is why ``AutomationLibrary.take_high_res_screenshot``
  and the ``HighResShot`` console command both failed here: the returned
  ``AutomationEditorTask`` stayed pending. Worse, those abandoned requests
  outlive the script's Python scope and crashed the editor
  (EXCEPTION_ACCESS_VIOLATION in python311.dll) once GC collected them.

Two mechanisms work instead, and this module uses both:

* **Synchronous rendering** -- ``SceneCaptureComponent2D.capture_scene()``
  renders the scene to a render target on demand, with no dependency on
  the editor viewport, its realtime flag, or its visibility.
  ``RenderingLibrary.export_render_target`` then writes a PNG. This is the
  screenshot path, and it is deterministic: framing comes entirely from the
  capture component's transform/FOV, never from the viewport's size or the
  user's editor layout.
* **Arm-and-collect** -- ``unreal.register_slate_post_tick_callback`` *does*
  fire on real editor ticks after the script returns. Frame timing is armed
  in the script and accumulated across genuine ticks; the callback rewrites
  the result JSON with ``"complete": true`` when the window closes. The host
  polls that file rather than blocking the editor.

Frame-time caveat (read before trusting the number)
---------------------------------------------------
``UEditorEngine::ShouldThrottleCPUUsage()`` clamps the editor to 3.0 Hz
whenever its window is not the foreground application -- the usual state
when driving it over Remote Execution. Measured backgrounded: 333.4 ms/tick
with a 331.9-336.1 ms spread, invariant to scene content, with the Slate
delta pinned at exactly 125 ms. No lever reachable from Python defeats
this: ``Slate.bAllowThrottling``, ``t.IdleWhenNotForeground`` and
``t.MaxFPS`` were all already 0, and ``EditorPerformanceSettings``
exposes no properties through Python reflection. Only giving the editor
window foreground focus lifts it -- measured 35.0 ms/tick over 143 frames
with the same scene once focused.

So ``frame_time_ms`` is a *real* measurement over *real* counted frames,
but while ``editor_throttled`` is true it reports the idle floor and says
nothing about how expensive the assemblies are to draw. ``render_time_ms``
-- timed ``capture_scene()`` calls with a GPU flush -- is the number that
actually tracks scene cost, and it is unaffected by the throttle.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("growpy.ue_viewport_probe")

SCHEMA_VERSION = "2.0"

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

# Number of timed capture_scene() renders used for render_time_ms.
RENDER_SAMPLE_COUNT = 10

# Transient scratch map. new_map_from_template with save_existing_map=False
# writes nothing to disk and raises no save prompt -- unlike
# LevelEditorSubsystem.new_level(asset_path), which *saves a new level
# asset* at the path it is given and therefore fails outright against
# /Engine paths.
SCRATCH_LEVEL_TEMPLATE = "/Engine/Maps/Templates/Template_Default"

# UEditorEngine::ShouldThrottleCPUUsage() pins a background editor to ~3 Hz.
EDITOR_THROTTLE_HZ = 3.0
# Above this per-frame cost the editor is idle-bound, not scene-bound, so
# frame_time_ms says nothing about asset cost. Deliberately a wide
# threshold rather than a narrow band around the 3 Hz floor: measured
# backgrounded rates vary (333.4 ms with 3 assemblies, 277.9 ms with 9),
# while a focused editor rendering the same scene sat at 35.0 ms.
EDITOR_IDLE_FRAME_MS = 100.0

RESULT_JSON_NAME = "growpy_viewport_probe_result.json"
SCRIPT_NAME = "growpy_viewport_probe.py"


def _fmt_tuple(t: tuple[float, ...]) -> str:
    return "(" + ", ".join(repr(float(v)) for v in t) + ")"


_SCRIPT_BODY = '''"""
GrowPy Viewport Probe - Auto-generated (schema v{schema_version}).

Places {count} assembly/assemblies at deterministic transforms in a transient
scratch map, sets fixed lighting and fixed capture cameras (see the constants
below -- these are baked in by the host-side generator and must be
byte-identical across probe rounds), exports front/side PNGs via SceneCapture2D,
times scene rendering, and then arms a slate post-tick callback that measures
the editor tick rate across real frames. Writes a JSON result file next to this
script; the host polls it for "complete": true.

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r"{script_path}").read())
"""

import gc
import json
import os
import time
import unreal


SCHEMA_VERSION = "{schema_version}"
ASSET_PATHS = {asset_paths!r}
RESULT_JSON_PATH = r"{result_json_path}"
SCREENSHOT_DIR = r"{screenshot_dir}"
SCREENSHOT_WIDTH = {width}
SCREENSHOT_HEIGHT = {height}
MEASUREMENT_WINDOW_S = {measurement_window_s}
ROW_SPACING_CM = {row_spacing}
RENDER_SAMPLE_COUNT = {render_samples}
SCRATCH_LEVEL_TEMPLATE = "{scratch_template}"
EDITOR_THROTTLE_HZ = {throttle_hz}
EDITOR_IDLE_FRAME_MS = {idle_frame_ms}

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

VIEWS = (
    ("front", FRONT_CAMERA_LOCATION, FRONT_CAMERA_ROTATION),
    ("side", SIDE_CAMERA_LOCATION, SIDE_CAMERA_ROTATION),
)


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


def _world_path():
    w = _get_editor_world()
    try:
        return str(w.get_path_name()) if w is not None else None
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


def _rotator(rotation):
    """Build an unreal.Rotator from a (pitch, yaw, roll) tuple.

    unreal.Rotator's POSITIONAL order is (roll, pitch, yaw) -- verified
    live: unreal.Rotator(0, 90, 0).get_forward_vector() is (0, 0, 1),
    i.e. pitched straight up, not yawed to +Y. The constants in this
    module are documented as (pitch, yaw, roll), so they must be passed
    by keyword or the side camera stares at the sky and the sun points
    somewhere other than SUN_ROTATION says.
    """
    pitch, yaw, roll = rotation
    return unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)


def _spawn_actor(actor_class, location, rotation):
    """Multi-strategy actor spawn (EditorActorSubsystem, then legacy)."""
    loc = unreal.Vector(*location)
    rot = _rotator(rotation)
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
    rot = _rotator(rotation)
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


def _new_scratch_map():
    """Open a transient blank map, discarding the current one without saving.

    EditorLoadingAndSavingUtils.new_map_from_template(path, save_existing_map)
    creates an in-memory world and writes no asset. LevelEditorSubsystem's
    new_level()/new_level_from_template() are deliberately NOT used: their
    asset_path argument is a *destination to save a new level asset to*, so
    passing an /Engine template path fails and -- if the caller ignores the
    return value -- leaves the user's own level open to be spawned into.

    Returns (ok, note).
    """
    before = _world_path()
    # new_blank_map first: Template_Default ships a SkyDome whose sky
    # material stamps "YOUR SCENE CONTAINS A SKYDOME MESH..." across every
    # captured frame, which would swamp a screenshot diff. A blank map
    # leaves only what this script spawns.
    for label, fn in (
        (
            "new_blank_map",
            lambda: unreal.EditorLoadingAndSavingUtils.new_blank_map(False),
        ),
        (
            "new_map_from_template",
            lambda: unreal.EditorLoadingAndSavingUtils.new_map_from_template(
                SCRATCH_LEVEL_TEMPLATE, False
            ),
        ),
    ):
        try:
            fn()
        except Exception as e:
            print(f"  {{label}} raised: {{e}}")
            continue
        after = _world_path()
        if after is not None and after != before:
            return True, f"{{label}} -> {{after}} (was {{before}})"
        print(f"  {{label}} did not change the open world (still {{after}})")
    return False, f"scratch map did not load; editor world still {{before}}"


def _clear_existing_lights():
    """Remove any Light-derived actors the template map ships with, so
    lighting is fully determined by SUN_ROTATION/SUN_INTENSITY_LUX below,
    not by whatever the template happens to contain."""
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


def _apply_manual_exposure(capture_component):
    """Fix exposure so captures don't shift with scene content."""
    try:
        pp = capture_component.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property(
            "auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL
        )
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", EXPOSURE_BIAS)
        pp.set_editor_property("override_camera_iso", True)
        pp.set_editor_property("camera_iso", EXPOSURE_ISO)
        pp.set_editor_property("override_camera_shutter_speed", True)
        pp.set_editor_property("camera_shutter_speed", 1.0 / EXPOSURE_SHUTTER_SPEED)
        pp.set_editor_property("override_depth_of_field_fstop", True)
        pp.set_editor_property("depth_of_field_fstop", EXPOSURE_APERTURE_FSTOP)
        capture_component.set_editor_property("post_process_settings", pp)
        return True
    except Exception as e:
        print(f"  Could not fix capture exposure: {{e}}")
        return False


def _make_capture(world, location, rotation):
    """Spawn a SceneCapture2D carrying the fixed camera constants.

    Returns (actor, component, render_target) or (None, None, None).

    SceneCapture2D is used rather than AutomationLibrary.take_high_res_screenshot
    because the latter only queues a request for a later viewport draw, which
    never arrives inside a Remote Execution call -- see the module docstring.
    """
    try:
        rt = unreal.RenderingLibrary.create_render_target2d(
            world,
            SCREENSHOT_WIDTH,
            SCREENSHOT_HEIGHT,
            unreal.TextureRenderTargetFormat.RTF_RGBA8,
        )
        actor = _spawn_actor(unreal.SceneCapture2D, location, rotation)
        if actor is None:
            return None, None, None
        comp = actor.capture_component2d
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("fov_angle", CAMERA_FOV_DEG)
        comp.set_editor_property(
            "capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
        )
        comp.set_editor_property("capture_every_frame", False)
        comp.set_editor_property("capture_on_movement", False)
        _apply_manual_exposure(comp)
        return actor, comp, rt
    except Exception as e:
        print(f"  Could not build SceneCapture2D: {{e}}")
        return None, None, None


def _flush_gpu(world, render_target):
    """Force the render thread to finish the pending capture.

    read_render_target_raw_pixel flushes rendering commands before reading,
    so timing a capture_scene() + this pair measures real render work rather
    than the cost of enqueueing a command.
    """
    unreal.RenderingLibrary.read_render_target_raw_pixel(world, render_target, 0, 0)


def _export_png(world, render_target, name):
    """Export the render target to SCREENSHOT_DIR/<name>.png. Returns path or None."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    filename = name + ".png"
    out_path = os.path.join(SCREENSHOT_DIR, filename)
    if os.path.isfile(out_path):
        os.remove(out_path)
    try:
        unreal.RenderingLibrary.export_render_target(
            world, render_target, SCREENSHOT_DIR, filename
        )
    except Exception as e:
        print(f"  export_render_target failed for {{name}}: {{e}}")
        return None
    if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
        # Normalise separators: SCREENSHOT_DIR is baked in with forward
        # slashes but os.path.join adds a backslash on Windows, which makes
        # the recorded path awkward to diff across rounds.
        return out_path.replace("\\\\", "/")
    print(f"  export_render_target produced no file for {{name}}")
    return None


def _median(values):
    s = sorted(values)
    n = len(s)
    if not n:
        return None
    if n % 2:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def _time_renders(world, comp, render_target):
    """Time RENDER_SAMPLE_COUNT synchronous renders, plus the flush baseline.

    Returns (render_stats, baseline_stats), each a dict or None.
    """
    try:
        # Baseline: the readback/flush cost alone, with no capture queued.
        base = []
        for _ in range(RENDER_SAMPLE_COUNT):
            t0 = time.perf_counter()
            _flush_gpu(world, render_target)
            base.append((time.perf_counter() - t0) * 1000.0)

        samples = []
        for _ in range(RENDER_SAMPLE_COUNT):
            t0 = time.perf_counter()
            comp.capture_scene()
            _flush_gpu(world, render_target)
            samples.append((time.perf_counter() - t0) * 1000.0)

        def _stats(vals):
            return {{
                "samples": len(vals),
                "median_ms": _median(vals),
                "mean_ms": sum(vals) / len(vals),
                "min_ms": min(vals),
                "max_ms": max(vals),
            }}

        return _stats(samples), _stats(base)
    except Exception as e:
        print(f"  Render timing failed: {{e}}")
        return None, None


def main():
    print("=" * 60)
    print("GrowPy Viewport Probe")
    print("=" * 60)

    result = {{
        "schema_version": SCHEMA_VERSION,
        "complete": False,
        "engine_version": None,
        "scratch_map": None,
        "asset_count_requested": len(ASSET_PATHS),
        "asset_count_placed": 0,
        "screenshots": {{}},
        "screenshot_method": "scene_capture_2d",
        "render_time_ms": None,
        "render_time_stats": None,
        "render_flush_baseline": None,
        "render_time_method": None,
        "frame_time_ms": None,
        "frame_rate_hz": None,
        "frame_count_measured": 0,
        "measurement_window_s": MEASUREMENT_WINDOW_S,
        "frame_time_method": None,
        "editor_throttled": None,
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

    def _save_result():
        # Always write, even on partial failure -- mirrors
        # unreal_scripts._build_datatable_script's "save to disk first".
        try:
            os.makedirs(os.path.dirname(RESULT_JSON_PATH), exist_ok=True)
            with open(RESULT_JSON_PATH, "w") as f:
                json.dump(result, f, indent=2, default=str)
        except Exception as e:
            print(f"  ** Could not write result JSON: {{e}}")

    def _finish(reason):
        """Terminal path for a run that cannot measure frame time."""
        result["complete"] = True
        result["frame_time_notes"].append(reason)
        _save_result()
        print(f"Viewport probe aborted: {{reason}}")

    try:
        result["engine_version"] = unreal.SystemLibrary.get_engine_version()
    except Exception as e:
        result["errors"].append(f"get_engine_version failed: {{e}}")

    # --- Scratch map. Abort rather than touch the user's open level. ---
    ok, note = _new_scratch_map()
    result["scratch_map"] = note
    if not ok:
        result["errors"].append(
            "Refusing to place actors: " + note
        )
        _finish("no scratch map, nothing measured")
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

    world = _get_editor_world()
    if world is None:
        result["errors"].append("No editor world after scratch map load.")
        _finish("no editor world")
        return

    # --- Fixed-camera captures (synchronous; no viewport involvement) ---
    spawned_captures = []
    for name, location, rotation in VIEWS:
        actor, comp, rt = _make_capture(world, location, rotation)
        if comp is None:
            result["errors"].append(f"Could not create {{name}} SceneCapture2D")
            result["screenshots"][name] = {{"path": None, "method": None}}
            continue
        spawned_captures.append((actor, rt, comp))
        try:
            comp.capture_scene()
            _flush_gpu(world, rt)
        except Exception as e:
            result["errors"].append(f"{{name}} capture_scene failed: {{e}}")
        path = _export_png(world, rt, name)
        result["screenshots"][name] = {{
            "path": path,
            "method": "scene_capture_2d" if path else None,
        }}
        if path:
            print(f"Captured {{name}}: {{path}}")
        else:
            result["errors"].append(f"{{name.capitalize()}} capture failed to export.")

    # --- Render cost (unaffected by the editor idle throttle) ---
    if spawned_captures:
        _actor, rt, comp = spawned_captures[0]
        stats, baseline = _time_renders(world, comp, rt)
        if stats is not None:
            result["render_time_stats"] = stats
            result["render_time_ms"] = stats["median_ms"]
            result["render_flush_baseline"] = baseline
            result["render_time_method"] = (
                "scene_capture_2d capture_scene()+GPU flush, "
                f"{{SCREENSHOT_WIDTH}}x{{SCREENSHOT_HEIGHT}}, front camera"
            )
        else:
            result["errors"].append("Render timing produced no samples.")

    # --- Tear down capture actors before the tick window opens ---
    for actor, rt, _comp in spawned_captures:
        try:
            actor.destroy_actor()
        except Exception:
            pass
        try:
            unreal.RenderingLibrary.release_render_target2d(rt)
        except Exception:
            pass

    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage()
    except Exception:
        pass

    _save_result()
    print(
        f"Synchronous phase done; arming a {{MEASUREMENT_WINDOW_S}}s tick "
        "measurement. The host polls the result JSON for completion."
    )

    # --- Frame time: arm-and-collect across real editor ticks ---
    # A slate post-tick callback is the only way to observe frames from
    # Python: this script blocks the game thread, so sleeping here and
    # sampling get_frame_count() around the sleep measures zero frames.
    state = {{"t0": None, "f0": None, "n": 0, "handle": None, "done": False}}

    def _on_tick(_delta_seconds):
        if state["done"]:
            return
        now = time.perf_counter()
        if state["t0"] is None:
            # Discard the first tick: it straddles this script's own
            # execution and would inflate the window.
            state["t0"] = now
            try:
                state["f0"] = unreal.SystemLibrary.get_frame_count()
            except Exception:
                state["f0"] = None
            return
        state["n"] += 1
        elapsed = now - state["t0"]
        if elapsed < MEASUREMENT_WINDOW_S:
            return

        state["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(state["handle"])
        except Exception as e:
            print(f"  unregister_slate_post_tick_callback failed: {{e}}")

        frames = state["n"]
        engine_frames = None
        try:
            if state["f0"] is not None:
                engine_frames = unreal.SystemLibrary.get_frame_count() - state["f0"]
        except Exception:
            pass

        per_frame_ms = elapsed * 1000.0 / frames if frames else None
        result["frame_time_ms"] = per_frame_ms
        result["frame_count_measured"] = frames
        result["measurement_window_s"] = elapsed
        result["frame_time_method"] = "slate_post_tick_wall_clock"
        result["frame_time_notes"].append(
            f"{{frames}} slate post-tick callbacks over {{elapsed:.3f}}s"
            + (
                f"; engine frame counter advanced {{engine_frames}}"
                if engine_frames is not None
                else ""
            )
        )

        result["frame_rate_hz"] = 1000.0 / per_frame_ms if per_frame_ms else None
        throttled = per_frame_ms is not None and per_frame_ms >= EDITOR_IDLE_FRAME_MS
        result["editor_throttled"] = bool(throttled)
        if throttled:
            result["frame_time_notes"].append(
                f"{{per_frame_ms:.1f}} ms/frame "
                f"({{1000.0 / per_frame_ms:.1f}} Hz) is at the idle floor "
                "UEditorEngine::ShouldThrottleCPUUsage() imposes on a "
                "background editor (~{{:.0f}} Hz), NOT a measure of scene "
                "cost -- compare it against render_time_ms. To get a real "
                "editor frame time, re-run with the editor window focused "
                "in the foreground.".format(EDITOR_THROTTLE_HZ)
            )
        if frames < 2:
            result["frame_time_notes"].append(
                "Fewer than 2 frames counted -- this number is noise."
            )

        result["complete"] = True
        _save_result()
        print(
            f"Frame timing complete: {{per_frame_ms}} ms over {{frames}} frame(s)."
        )

    try:
        state["handle"] = unreal.register_slate_post_tick_callback(_on_tick)
    except Exception as e:
        result["errors"].append(f"Could not arm tick measurement: {{e}}")
        _finish(f"register_slate_post_tick_callback failed: {{e}}")


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
    output_dir = Path(output_dir)
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
        render_samples=RENDER_SAMPLE_COUNT,
        scratch_template=SCRATCH_LEVEL_TEMPLATE,
        throttle_hz=EDITOR_THROTTLE_HZ,
        idle_frame_ms=EDITOR_IDLE_FRAME_MS,
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


def _read_payload(result_json_path: Path) -> dict[str, Any] | None:
    if not result_json_path.is_file():
        return None
    try:
        return json.loads(result_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("Result JSON at %s not readable yet: %s", result_json_path, e)
        return None


def _collect_payload(
    result_json_path: Path,
    *,
    timeout_s: float,
    poll_interval_s: float,
) -> dict[str, Any] | None:
    """Poll the result JSON until the in-editor script marks it complete.

    Remote Execution returns as soon as the script's synchronous phase ends;
    the frame-time measurement is still running on later editor ticks and
    rewrites this file when it finishes. Polling from the host keeps the
    editor free to tick -- blocking inside the editor would measure nothing.
    """
    deadline = time.monotonic() + timeout_s
    payload = None
    while True:
        candidate = _read_payload(result_json_path)
        if candidate is not None:
            payload = candidate
            if payload.get("complete"):
                return payload
        if time.monotonic() >= deadline:
            if payload is not None:
                payload.setdefault("frame_time_notes", []).append(
                    f"Host stopped polling after {timeout_s:.1f}s with "
                    "'complete' still false; frame-time fields may be missing."
                )
            return payload
        time.sleep(poll_interval_s)


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
    collect_timeout_s: float | None = None,
    poll_interval_s: float = 0.5,
) -> dict[str, Any]:
    """Generate the viewport probe script and, unless dry_run, deliver it.

    dry_run writes the script to disk and returns it without touching the
    network/UE at all. A live run delivers the script over Remote
    Execution (``ue_remote.run_file``, same primitive ue_exec uses), then
    polls the JSON result file until the in-editor tick measurement marks
    it complete.
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

    # The editor only ticks once the script returns, so the frame-time
    # window elapses after remote-exec has already handed control back.
    if collect_timeout_s is None:
        collect_timeout_s = measurement_window_s + 15.0
    payload = _collect_payload(
        result_json_path,
        timeout_s=collect_timeout_s,
        poll_interval_s=poll_interval_s,
    )

    return {
        "dry_run": False,
        "ok": remote_success and payload is not None and not payload.get("errors"),
        "remote_exec_success": remote_success,
        "measurement_complete": bool(payload and payload.get("complete")),
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
    print(f"Scratch map:         {payload.get('scratch_map')}")
    print(
        f"Assemblies placed:   {payload.get('asset_count_placed')}"
        f"/{payload.get('asset_count_requested')}"
    )
    for view, info in (payload.get("screenshots") or {}).items():
        print(f"Screenshot [{view:>5}]: {info.get('path')} (via {info.get('method')})")

    stats = payload.get("render_time_stats") or {}
    baseline = payload.get("render_flush_baseline") or {}
    print(
        f"Render time:         {payload.get('render_time_ms')} ms (median of "
        f"{stats.get('samples')} sample(s), "
        f"min {stats.get('min_ms')} / max {stats.get('max_ms')})"
    )
    if baseline:
        print(
            f"  flush baseline:    {baseline.get('median_ms')} ms median "
            f"({baseline.get('samples')} sample(s), readback only, no render)"
        )
    if payload.get("render_time_method"):
        print(f"  method:            {payload['render_time_method']}")

    frames = payload.get("frame_count_measured") or 0
    hz = payload.get("frame_rate_hz")
    print(
        f"Frame time:          {payload.get('frame_time_ms')} ms "
        + (f"({hz:.1f} Hz) " if isinstance(hz, (int, float)) else "")
        + f"over {frames} frame(s) "
        f"in a {payload.get('measurement_window_s')}s window "
        f"(method: {payload.get('frame_time_method')})"
    )
    if payload.get("editor_throttled"):
        print("  ** editor throttled -- frame time is an idle floor, not scene cost.")
    if frames and frames < 2:
        print("  ** single-frame measurement -- this is noise, not a frame time.")
    if not payload.get("complete"):
        print("  ** measurement did not complete within the host polling window.")
    for note in payload.get("frame_time_notes") or []:
        print(f"  note: {note}")
    if payload.get("errors"):
        print(f"Errors ({len(payload['errors'])}):")
        for err in payload["errors"]:
            print(f"  - {err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Places assemblies at deterministic transforms in a transient UE "
            "scratch map, sets fixed capture cameras/lighting, exports "
            "front/side PNGs, and measures render and frame time via Remote "
            "Execution."
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
    parser.add_argument(
        "--collect-timeout",
        type=float,
        default=None,
        help=(
            "Seconds to poll the result JSON for the in-editor frame-time "
            "measurement to finish (default: measurement window + 15)."
        ),
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
        collect_timeout_s=args.collect_timeout,
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

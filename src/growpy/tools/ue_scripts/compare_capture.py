# ruff: noqa: E501, UP031, E741 -- ported line for line from the editor scripts that made
# the 2026-11 compare boards; reflowing them is not worth a behaviour slip
"""Photograph every tree of the open compare level alone (growpy-ue-compare; runs inside the editor).

Per COMPARE_ tree: whole tree from the side, the crown, the view from below.

Tick-driven: the camera is aimed, then the editor renders SETTLE_S seconds of frames before the
shot is exported. Shooting everything inside one Python call gave Nanite no frame to stream its
pages, so new meshes came out as their coarsest voxel squares (2026-11-14). The script returns at
once; it writes <out>/<MODE>/DONE when the last shot is out (the session waits for it).

JOB (runpy init_globals): the job JSON (out, crown_base, sweep); MODE: the context compare_context.py
set (light | dark | forest). Ported from capture_compare.py (2026-11-14..19).
"""

import json
import math
import os
import time

import unreal

if not globals().get("JOB") or globals().get("MODE") not in ("light", "dark", "forest"):
    raise RuntimeError(
        "compare_capture.py: needs JOB and MODE light|dark|forest; run it through growpy-ue-compare"
    )
CONTEXT = globals()["MODE"]
with open(globals()["JOB"], encoding="utf-8") as _fh:
    job = json.load(_fh)

OUT = os.path.join(job["out"], CONTEXT)
RES = 1024
SETTLE_S = 4.0
NEW_TREE_S = (
    12.0  # first shot of a tree: its pages stream in only once the others are hidden
)
els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
zero = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
mpc = unreal.load_asset(
    "/ProceduralVegetationEditor/SampleAssets/Materials/MaterialFunctions/MPC_GlobalFoliageActor"
)
# Season: the studio has no foliage actor, so the global Season Strength sits at the MPC default and Seasons-ON
# leaves render brown. Boards render at mid-summer (job "season_strength", default 0 = summer on
# BP_TwinClock.SeasonStrengthForDay) instead of Seasons-off material copies. The parameter is found by name
# (the plugin's spelling is not ours to rely on); None = the MPC has no such scalar.
SEASON_STRENGTH = float(job.get("season_strength", 0.0))
SEASON_PARAM = next(
    (
        str(p.get_editor_property("parameter_name"))
        for p in (mpc.get_editor_property("scalar_parameters") if mpc else [])
        if "season" in str(p.get_editor_property("parameter_name")).lower()
        and "strength" in str(p.get_editor_property("parameter_name")).lower()
    ),
    None,
)
print("COMPARE season parameter", SEASON_PARAM, SEASON_STRENGTH)
unreal.SystemLibrary.execute_console_command(world, "r.TextureStreaming 0")
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(
    world, RES, RES, unreal.TextureRenderTargetFormat.RTF_RGBA8
)
cap = els.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 0), zero)
cc = cap.capture_component2d
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
cc.set_editor_property("texture_target", rt)
cc.set_editor_property(
    "primitive_render_mode",
    unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST,
)
cc.set_editor_property(
    "capture_every_frame", True
)  # render every tick, so Nanite streams what it sees
for a in (
    els.get_all_level_actors()
):  # an older build of the level may still hold the foliage actor
    if a.get_actor_label() == "COMPARE_GlobalFoliage":
        els.destroy_actor(a)
# Studio backdrop (owner 2026-11-17: black sky + grey floor made the sheets unreadable): the shot shows the tree and
# the unlit dome of compare_level.studio(), not the ground, at a fixed exposure so the bright backdrop does
# not darken the tree. A level built before the studio falls back to the old tree + ground (black sky).
EXPOSURE_BIAS = 1.0  # studio test 2026-11-17 12:45 (bias -2..1 x dome brightness 2, 4): +1 with 4 reads best
BRIGHTNESS = 4.0
studio = [
    a for a in els.get_all_level_actors() if a.get_actor_label() == "COMPARE_Studio"
]
backdrop = studio or [
    a for a in els.get_all_level_actors() if a.get_actor_label() == "COMPARE_Ground"
]
# context (fleck check 2026-11-19): dark = dome brightness 0.25, forest = dome 1.5 plus the COMPARE_ctx_* ground
# and neighbour actors in the show-only list; ctx actors are never trees
if CONTEXT == "forest":
    backdrop = backdrop + [
        a
        for a in els.get_all_level_actors()
        if a.get_actor_label().startswith("COMPARE_ctx_")
    ]
BRIGHTNESS = {"dark": 0.25, "forest": 1.5}.get(CONTEXT, BRIGHTNESS)
SKIP = (
    "COMPARE_Label",
    "COMPARE_Sun",
    "COMPARE_Sky",
    "COMPARE_Global",
    "COMPARE_Ground",
    "COMPARE_PlayerStart",
    "COMPARE_Studio",
    "COMPARE_ctx_",
)
trees = [
    a
    for a in els.get_all_level_actors()
    if a.get_actor_label().startswith("COMPARE_")
    and not a.get_actor_label().startswith(SKIP)
]
dome_mi = None
if studio:
    dome_mi = studio[0].static_mesh_component.create_dynamic_material_instance(0)
    pps = cc.get_editor_property("post_process_settings")
    pps.set_editor_property("override_auto_exposure_method", True)
    pps.set_editor_property(
        "auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL
    )
    pps.set_editor_property(
        "override_auto_exposure_apply_physical_camera_exposure", True
    )
    pps.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    pps.set_editor_property("override_auto_exposure_bias", True)
    cc.set_editor_property("post_process_settings", pps)
    cc.set_editor_property("post_process_blend_weight", 1.0)
# test tiles: "<label part> <bias> <brightness>" (growpy-ue-compare --sweep)
sweep = [list(s) for s in job.get("sweep", [])] if studio else []
if sweep:
    trees = [a for a in trees if any(s[0] in a.get_actor_label() for s in sweep)]


def look(bias, brightness):
    pps = cc.get_editor_property("post_process_settings")
    pps.set_editor_property("auto_exposure_bias", bias)
    cc.set_editor_property("post_process_settings", pps)
    dome_mi.set_scalar_parameter_value("Brightness", brightness)


# crown view framing: mesh name -> crown base in m (growpy-ue-compare --crown-base; absent -> the old fixed aim)
CROWN_BASE = job.get("crown_base") or {}
LIMB = job.get("limb") or {}
shots = []  # (actor, location, rotation, fov, file name[, bias, brightness])
for a in trees:
    origin, extent = a.get_actor_bounds(False)
    h = max(2 * extent.z, 100.0)
    p = a.get_actor_location()
    name = a.get_actor_label()[len("COMPARE_") :]
    dist = 0.6 * h / math.tan(math.radians(17.5))
    shots.append(
        (a, unreal.Vector(p.x - dist, p.y, 0.5 * h), zero, 35.0, name + "_tree")
    )
    mesh_name = name.split("_", 1)[-1]  # "<tag>_SK_..." -> "SK_..."
    if mesh_name in CROWN_BASE:
        # framed on the crown itself, crown base (target-sheet rule, m) to top (2026-11-17: the fixed 0.45 h aim
        # showed only the bare bole of the pines, crown base 5 m at h10 and 14.5 m at h20)
        cb = max(0.0, CROWN_BASE[mesh_name] * 100.0 - 100.0)
        span = max(h - cb, 200.0)
        d = 0.6 * span / math.tan(math.radians(22.5))
        shots.append(
            (
                a,
                unreal.Vector(p.x - d, p.y, cb + 0.5 * span),
                zero,
                45.0,
                name + "_crown",
            )
        )
    else:
        shots.append(
            (
                a,
                unreal.Vector(p.x - 0.4 * h, p.y, 0.45 * h),
                unreal.Rotator(roll=0.0, pitch=5.0, yaw=0.0),
                45.0,
                name + "_crown",
            )
        )
    if mesh_name in LIMB:
        # limb-end close-up (E131): 5 m from the crown's +Y edge at the given height, edge 1.5 m inside the frame
        shots.append(
            (
                a,
                unreal.Vector(origin.x - 500.0, origin.y + extent.y - 150.0, LIMB[mesh_name] * 100.0),
                zero,
                40.0,
                name + "_limb",
            )
        )
    if job.get("base"):
        # stem-base close-up (E147): eye height 1.6 m, 3.5 m from the stem, aimed at 0.9 m
        shots.append((a, unreal.Vector(p.x - 350.0, p.y, 160.0), unreal.Rotator(roll=0.0, pitch=-11.0, yaw=0.0), 45.0, name + "_base"))
    shots.append(
        (
            a,
            unreal.Vector(p.x - 0.15 * h, p.y, 170.0),
            unreal.Rotator(roll=0.0, pitch=55.0, yaw=0.0),
            70.0,
            name + "_below",
        )
    )
if sweep:  # test tiles: the tree and below views of the matching trees once per (bias, brightness)
    shots = [
        s[:4] + ("%s_b%s_l%s" % (s[4], b, l), float(b), float(l))
        for s in shots
        if not s[4].endswith("_crown")
        for part, b, l in sweep
        if part in s[4]
    ]
shots = [s if len(s) == 7 else s + (EXPOSURE_BIAS, BRIGHTNESS) for s in shots]

state = {"i": -1, "since": 0.0, "handle": None, "settle": SETTLE_S}


def aim(i):
    actor, loc, rot, fov, _, bias, brightness = shots[i]
    if dome_mi:
        look(bias, brightness)
    state["settle"] = SETTLE_S
    if i == 0 or shots[i - 1][0] != actor:
        # Every visible tree asks Nanite for its pages, also in the editor viewport; with ~30 trees the
        # pool thrashes and random trees stay voxel squares (round 2, 2026-11-14). Hide all others.
        for t in trees:
            t.set_is_temporarily_hidden_in_editor(t != actor)
            t.set_actor_hidden_in_game(t != actor)
        state["settle"] = NEW_TREE_S
    if mpc:  # Health above 1 turns every masked leaf into a square
        unreal.MaterialLibrary.set_scalar_parameter_value(world, mpc, "Health", 1.0)
        if SEASON_PARAM:  # mid-summer, Seasons switch ON (owner 2026-11-26), not Seasons-off copies
            unreal.MaterialLibrary.set_scalar_parameter_value(world, mpc, SEASON_PARAM, SEASON_STRENGTH)
    cc.clear_show_only_components()  # show_only_actors is not editable from Python (5.8)
    # forest context (E124, 2026-11-19): only neighbours beyond the subject (camera sits at -X), else the neighbours
    # of the row in front stand between camera and tree
    ax = actor.get_actor_location().x
    for g in [actor] + [
        b
        for b in backdrop
        if not b.get_actor_label().startswith("COMPARE_ctx_n")
        or b.get_actor_location().x > ax
    ]:
        cc.show_only_actor_components(g, False)
    cc.set_editor_property("fov_angle", fov)
    cap.set_actor_location_and_rotation(loc, rot, False, False)


def tick(dt):
    try:
        now = time.time()
        if state["i"] >= 0 and now - state["since"] < state["settle"]:
            cc.capture_scene()  # a rendered frame per tick, whether or not the viewport is realtime
            return
        if state["i"] >= 0:
            unreal.RenderingLibrary.export_render_target(
                world, rt, OUT, shots[state["i"]][4] + ".png"
            )
        state["i"] += 1
        if state["i"] >= len(shots):
            unreal.unregister_slate_post_tick_callback(state["handle"])
            els.destroy_actor(cap)
            for t in trees:
                t.set_is_temporarily_hidden_in_editor(False)
                t.set_actor_hidden_in_game(False)
            open(os.path.join(OUT, "DONE"), "w").write(str(len(trees)))
            print("COMPARE captured %d trees -> %s" % (len(trees), OUT))
            return
        aim(state["i"])
        state["since"] = now
    except Exception as e:  # never leave a dead callback ticking
        unreal.unregister_slate_post_tick_callback(state["handle"])
        open(os.path.join(OUT, "DONE"), "w").write("error: %s" % e)
        raise


state["handle"] = unreal.register_slate_post_tick_callback(tick)
print(
    "COMPARE capturing %d trees, %d shots, %.0f s each -> %s"
    % (len(trees), len(shots), SETTLE_S, OUT)
)

"""Lay the exported PVE catalog out in gallery levels, to judge it by eye.

The catalog's acceptance is optical (owner direction, 2026-09-15). ``growpy-pve-shots``
renders every tree from fixed framings one pair at a time, which took 12-14 h for the
h05-h45 catalog; a level holding a species' trees side by side is judged in minutes, in
the editor or in VR, and stays current: rerun this after a re-export and it rebuilds in
place (owner, 2026-09-25).

One level per species by default (``/Game/Levels/TreeGallery/TreeGallery_<Species>``),
built one after another. The whole catalog in one level does not fit a 64 GB
workstation: loading all 216 meshes took the editor to 43 GB before a single tree was
placed, and the first spawn then overflowed the GPUScene upload pool even at
``r.GPUScene.MaxPooledUploadBufferSize=16000000`` (2026-09-25). ``--level`` puts the
selected species into one named level instead, for a side-by-side of a few.

Memory still builds up across levels in one editor session, garbage collection
notwithstanding: 12 GB after the first species, 51 GB after ten (2026-09-25). On a
64 GB machine run the species in two halves (``--species``) with an editor restart in
between.

Layout, seen from the front (looking +X): one block per species, one row per stand
radius (r00 open-grown, r07 dense, r10 moderate), one column per stage height from left
to right. Every row is as deep, and every column as wide, as the widest crown in it, so
nothing overlaps. A label strip in front of each block names the species, the rows and
the columns. Lit like ECOSENSE (BP_Sky_Sphere, one low sun, the PVE global foliage
actor, which drives foliage colour) on flat ground at z = 0, with a PlayerStart in
front.

The generated scripts (``growpy_pve_gallery_<species>.py`` beside the manifest) measure,
lay out and place in the editor by themselves, so they can also be rerun with
``growpy-ue-exec``. Everything they place carries the ``GALLERY_`` label prefix and is
replaced on a rerun.

Two things it will not do:

* place a mesh with more than 32,767 bones. Spawning one crashes the editor
  (``Array index out of bounds: -32748 into an array of size 51120``, 2026-09-25), and
  a level holding one would crash on every open. The count comes from the skeleton's
  reference pose, which needs no component; the cell gets a text marker instead.
* animate wind. The trees are SkeletalMeshActors; PVE wind needs an instanced skinned
  mesh component with a transform provider, which is what ``PCG_Trees`` spawns.

``--shots DIR`` then photographs every stand row twice (h05-h25 and h30 up) with all
other trees hidden, for review away from the editor: seen from the front, the rows of a
block stand behind one another, and a whole block only fits the frame from so far away
that Nanite shows its crowns as voxels. The level viewport renders the shots, so the
editor has to be in front.

Usage::

    growpy-pve-gallery data/output/forest/unreal_scripts/pve_export_manifest.json
    growpy-pve-gallery <manifest> --species european_beech silver_fir
    growpy-pve-gallery <manifest> --shots data/tmp/gallery_shots
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path

logger = logging.getLogger("growpy.pve_gallery")

DEFAULT_FOLDER = "/Game/Levels/TreeGallery"
LABEL_PREFIX = "GALLERY_"
# Unreal indexes bones with a signed 16-bit type; one more and the editor dies on
# spawn (see module docstring).
MAX_BONES = 32767
# ECOSENSE's lighting, as the ShotStage level mirrors it.
SUN_ROTATION = {"roll": 180.0, "pitch": -11.1, "yaw": -35.3}
SUN_INTENSITY = 10.0
SKY_CLASS = "/Engine/EngineSky/BP_Sky_Sphere.BP_Sky_Sphere_C"
FOLIAGE_CLASS = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/GlobalFoliageActor/"
    "BP_GlobalFoliageActor_UE5.BP_GlobalFoliageActor_UE5_C"
)
PLANE_MESH = "/Engine/BasicShapes/Plane.Plane"
RADIUS_NAMES = {0: "open-grown", 7: "dense", 10: "moderate"}

_TREE_ID = re.compile(r"^r(\d+)_h(\d+)m$")


def gallery_records(manifest: dict, species: list[str] | None = None) -> list[dict]:
    """One record per exported mesh, sorted species -> radius -> stage."""
    from growpy.tools.pve_catalog import species_display_name

    records = []
    for graph in manifest["graphs"]:
        for mesh in graph["meshes"]:
            sp = mesh.get("species")
            tree_id = mesh.get("tree_id") or ""
            match = _TREE_ID.match(tree_id)
            if not sp or not match:
                raise ValueError(
                    f"manifest mesh {mesh.get('mesh_name')!r} carries no species / "
                    f"r<NN>_h<NN>m tree_id -- re-run the plan"
                )
            if species and sp not in species:
                continue
            records.append(
                {
                    "key": f"{sp}__{tree_id}",
                    "species": sp,
                    "species_label": species_display_name(sp),
                    "tree_id": tree_id,
                    "radius": int(match.group(1)),
                    "stage": int(match.group(2)),
                    "asset": mesh["asset"],
                }
            )
    return sorted(records, key=lambda r: (r["species"], r["radius"], r["stage"]))


def gallery_layout(records, gap_cm=800.0, block_gap_cm=3000.0):
    """Grid positions for the gallery, in cm.

    X runs away from the viewer: one block per species (in record order), one row per
    radius within it (ascending), each row as deep as its widest crown plus gap_cm, with
    a block_gap_cm label strip in front of every block. Y runs left to right: one
    column per stage (ascending), each as wide as the widest crown of that stage plus
    gap_cm. Records need key, species, radius, stage and width_cm.

    Self-contained on purpose: the generated editor script embeds this source.
    """
    stages = sorted({r["stage"] for r in records})
    columns = {}
    y = 0.0
    for stage in stages:
        width = max(r["width_cm"] for r in records if r["stage"] == stage) + gap_cm
        columns[stage] = {"y": y + width / 2.0, "y0": y, "y1": y + width}
        y += width
    species_order = []
    for r in records:
        if r["species"] not in species_order:
            species_order.append(r["species"])
    positions = {}
    blocks = []
    x = 0.0
    for species in species_order:
        members = [r for r in records if r["species"] == species]
        block = {"species": species, "label_x": x + block_gap_cm / 2.0, "rows": []}
        x += block_gap_cm
        block["x0"] = x
        for radius in sorted({r["radius"] for r in members}):
            row = [r for r in members if r["radius"] == radius]
            depth = max(r["width_cm"] for r in row) + gap_cm
            centre = x + depth / 2.0
            for r in row:
                positions[r["key"]] = (centre, columns[r["stage"]]["y"])
            block["rows"].append({"radius": radius, "x": centre})
            x += depth
        block["x1"] = x
        blocks.append(block)
    return {
        "positions": positions,
        "columns": columns,
        "blocks": blocks,
        "extent_cm": (x, y),
    }


UE_BODY = """
eal = unreal.EditorAssetLibrary
els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
lvl = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
report = {"level": LEVEL, "placed": [], "skipped": [], "missing": []}

# 1. open (or create) the gallery level. Switching away from a level with unsaved
#    changes opens a save dialog, which blocks a remote script indefinitely.
world = ues.get_editor_world()
current = world.get_path_name().split(".")[0] if world else ""
if current != LEVEL:
    utils = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_name() for p in utils.get_dirty_map_packages()]
    if dirty:
        raise RuntimeError(
            "unsaved changes in %s: save or discard them first, switching levels "
            "would open a save dialog and block this script" % dirty
        )
    if eal.does_asset_exist(LEVEL):
        lvl.load_level(LEVEL)
    else:
        folder = LEVEL.rsplit("/", 1)[0]
        if not eal.does_directory_exist(folder):
            eal.make_directory(folder)
        try:
            created = lvl.new_level(LEVEL, False)  # (path, is_partitioned_world)
        except TypeError:
            created = lvl.new_level(LEVEL)
        if not created:
            raise RuntimeError("could not create %s" % LEVEL)
    # the previous gallery's meshes are unreferenced now; free them before loading
    unreal.SystemLibrary.collect_garbage()
for actor in els.get_all_level_actors():
    if actor.get_actor_label().startswith(PREFIX):
        els.destroy_actor(actor)

# 2. measure every mesh without spawning it
records = []
meshes = {}
for rec in RECORDS:
    if not eal.does_asset_exist(rec["asset"]):
        report["missing"].append(rec["asset"])
        continue
    mesh = eal.load_asset(rec["asset"])
    extent = mesh.get_bounds().box_extent
    pose = mesh.get_editor_property("skeleton").get_reference_pose()
    rec = dict(rec)
    rec["width_cm"] = 2.0 * max(extent.x, extent.y)
    rec["height_cm"] = 2.0 * extent.z
    rec["bones"] = len(unreal.AnimPoseExtensions.get_bone_names(pose))
    records.append(rec)
    meshes[rec["key"]] = mesh
if not records:
    raise RuntimeError("none of the %d meshes exists" % len(RECORDS))
layout = gallery_layout(records, GAP_CM, BLOCK_GAP_CM)
extent_x, extent_y = layout["extent_cm"]
zero = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)


def spawn_class(cls, label, loc, rot=zero, folder="Gallery/Environment"):
    if isinstance(cls, str):
        cls = unreal.load_class(None, cls)
    actor = els.spawn_actor_from_class(cls, loc, rot)
    actor.set_actor_label(PREFIX + label)
    actor.set_folder_path(folder)
    return actor


def text(label, words, x, y, size):
    # Yaw 180: the text faces -X, towards a viewer standing in front of the grid.
    actor = spawn_class(
        unreal.TextRenderActor, "Label_" + label, unreal.Vector(x, y, 150.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0), "Gallery/Labels",
    )
    comp = actor.get_editor_property("text_render")
    comp.set_text(words)
    comp.set_world_size(size)
    comp.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    comp.set_text_render_color(unreal.Color(255, 255, 255, 255))
    return actor


# 3. environment: ECOSENSE light, sky, foliage actor, ground, a start in front
sun = spawn_class(unreal.DirectionalLight, "Sun", unreal.Vector(0.0, 0.0, 0.0),
                  unreal.Rotator(**SUN_ROTATION))
light = sun.get_component_by_class(unreal.DirectionalLightComponent)
light.set_editor_property("intensity", SUN_INTENSITY)
light.set_editor_property("atmosphere_sun_light", True)
sky = spawn_class(SKY_CLASS, "SkySphere", unreal.Vector(0.0, 0.0, 0.0))
try:
    sky.set_editor_property("directional_light_actor", sun)
except Exception:
    pass
spawn_class(FOLIAGE_CLASS, "GlobalFoliage", unreal.Vector(0.0, 0.0, 0.0))
margin = 10000.0
ground = spawn_class(unreal.StaticMeshActor, "Ground",
                     unreal.Vector(extent_x / 2.0, extent_y / 2.0, 0.0))
ground.static_mesh_component.set_static_mesh(unreal.load_asset(PLANE_MESH))
ground.set_actor_scale3d(unreal.Vector((extent_x + 2 * margin) / 100.0,
                                       (extent_y + 2 * margin) / 100.0, 1.0))
spawn_class(unreal.PlayerStart, "PlayerStart",
            unreal.Vector(-1500.0, extent_y / 2.0, 100.0))

# 4. trees, or a marker where a tree cannot be placed
for rec in records:
    x, y = layout["positions"][rec["key"]]
    folder = "Gallery/" + rec["species"]
    if rec["bones"] > MAX_BONES:
        words = "%s\\nnot placed:\\n%d bones" % (rec["tree_id"], rec["bones"])
        text(rec["key"], words, x, y, 150.0)
        report["skipped"].append({"key": rec["key"], "bones": rec["bones"]})
        continue
    where = unreal.Vector(x, y, 0.0)
    actor = els.spawn_actor_from_object(meshes[rec["key"]], where, zero)
    actor.set_actor_label(PREFIX + rec["key"])
    actor.set_folder_path(folder)
    report["placed"].append({
        "key": rec["key"], "species": rec["species"], "stage": rec["stage"],
        "radius": rec["radius"], "x": x, "y": y, "bones": rec["bones"],
        "height_cm": rec["height_cm"], "width_cm": rec["width_cm"],
    })

# 5. labels: species, rows and columns in the strip in front of every block
labels = {r["species"]: r["species_label"] for r in records}
for block in layout["blocks"]:
    sp = block["species"]
    text(sp, labels[sp], block["label_x"], -2500.0, 500.0)
    for row in block["rows"]:
        name = RADIUS_NAMES.get(row["radius"], "")
        text("%s_r%02d" % (sp, row["radius"]), "r%02d %s" % (row["radius"], name),
             row["x"], -900.0, 250.0)
    for stage, col in layout["columns"].items():
        text("%s_h%02d" % (sp, stage), "h%02d" % stage,
             block["label_x"], col["y"], 300.0)

report["saved"] = bool(unreal.EditorLoadingAndSavingUtils.save_current_level())
report["extent_m"] = [round(extent_x / 100.0, 1), round(extent_y / 100.0, 1)]
report["blocks"] = layout["blocks"]
report["columns"] = {str(k): v for k, v in layout["columns"].items()}
unreal.log("PVEGALLERY placed %d, skipped %d over %d bones, missing %d" % (
    len(report["placed"]), len(report["skipped"]), MAX_BONES, len(report["missing"])))
unreal.log("PVEGALLERY_REPORT " + json.dumps(report))
"""


def build_ue_script(
    records: list[dict],
    *,
    level: str,
    gap_cm: float = 800.0,
    block_gap_cm: float = 3000.0,
) -> str:
    """The self-contained editor script: constants + gallery_layout + UE_BODY."""
    header = "\n".join(
        [
            '"""GrowPy PVE gallery -- auto-generated, do not edit."""',
            "import json",
            "import unreal",
            "",
            f"LEVEL = {level!r}",
            f"PREFIX = {LABEL_PREFIX!r}",
            f"MAX_BONES = {MAX_BONES!r}",
            f"GAP_CM = {float(gap_cm)!r}",
            f"BLOCK_GAP_CM = {float(block_gap_cm)!r}",
            f"SUN_ROTATION = {SUN_ROTATION!r}",
            f"SUN_INTENSITY = {SUN_INTENSITY!r}",
            f"SKY_CLASS = {SKY_CLASS!r}",
            f"FOLIAGE_CLASS = {FOLIAGE_CLASS!r}",
            f"PLANE_MESH = {PLANE_MESH!r}",
            f"RADIUS_NAMES = {RADIUS_NAMES!r}",
            f"RECORDS = {records!r}",
            "",
            "",
        ]
    )
    return header + inspect.getsource(gallery_layout) + UE_BODY


CAMERA_SCRIPT = """\
import unreal

els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in els.get_all_level_actors():
    if not actor.get_actor_label().startswith({prefix!r}):
        continue
    # trees are <species>__<tree_id>, their not-placed markers Label_<species>__...
    key = actor.get_actor_label()[len({prefix!r}):]
    if key.startswith("Label_"):
        key = key[len("Label_"):]
    if "__" in key:
        actor.set_is_temporarily_hidden_in_editor(not key.startswith({keep!r}))
unreal.SystemLibrary.execute_console_command(None, "t.IdleWhenNotForeground 0")
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
ues.set_level_viewport_camera_info(
    unreal.Vector(*{loc!r}), unreal.Rotator(roll=0.0, pitch={pitch!r}, yaw=0.0)
)
if {shoot!r}:
    unreal.AutomationLibrary.take_high_res_screenshot({width!r}, {height!r}, {name!r})
unreal.log("PVEGALLERY camera %s" % {name!r})
"""

UNHIDE_SCRIPT = """\
import unreal

els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in els.get_all_level_actors():
    if actor.get_actor_label().startswith({prefix!r}):
        actor.set_is_temporarily_hidden_in_editor(False)
"""


def row_framings(
    report: dict, species: str, radius: int, aspect: float = 16.0 / 9.0
) -> dict:
    """Camera ((x, y, z), pitch) per framing of one stand row: h05-h25, h30 and up.

    The camera stands in front of the row, far enough back that the columns of the
    framing fill the 90-degree horizontal field of view and the tallest tree in it
    fits the vertical one, at 40 % of that tree's height.
    """
    placed = [
        p for p in report["placed"] if p["species"] == species and p["radius"] == radius
    ]
    columns = {int(k): v for k, v in report["columns"].items()}
    framings = {}
    for name, low, high in (("short", 0, 25), ("tall", 30, 10**6)):
        group = [p for p in placed if low <= p["stage"] <= high]
        if not group:
            continue
        stages = sorted({p["stage"] for p in group})
        y0 = columns[stages[0]]["y0"]
        y1 = columns[stages[-1]]["y1"]
        top = max(p["height_cm"] for p in group)
        # Level camera, 90 degrees horizontal: the view is as wide as twice the
        # distance and as tall as that over the aspect. Far enough back for the
        # span, and for the 60 % of the tallest tree above the camera. (A pitch
        # of -5 cut the crown tops off, 2026-09-25.)
        back = max((y1 - y0) / 2.0, 0.6 * top * aspect) + 500.0
        framings[name] = ((group[0]["x"] - back, (y0 + y1) / 2.0, 0.4 * top), 0.0)
    return framings


def take_row_shots(
    report: dict, out_dir: Path, settle: float, size: tuple[int, int]
) -> list[Path]:
    from growpy.tools.pve_shots import _run_in_editor, _screenshot_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = _screenshot_dir()
    width, height = size
    taken = []
    try:
        for block in report["blocks"]:
            species = block["species"]
            for row in block["rows"]:
                radius = row["radius"]
                framings = row_framings(report, species, radius, width / height)
                for framing, (loc, pitch) in framings.items():
                    name = f"gallery_{species}_r{radius:02d}_{framing}"
                    spec = {
                        "prefix": LABEL_PREFIX,
                        "keep": f"{species}__r{radius:02d}_",
                        "loc": loc,
                        "pitch": pitch,
                        "width": width,
                        "height": height,
                        "name": name,
                    }
                    _run_in_editor(CAMERA_SCRIPT.format(shoot=False, **spec))
                    time.sleep(settle)
                    _run_in_editor(CAMERA_SCRIPT.format(shoot=True, **spec))
                    produced = shots_dir / f"{name}.png"
                    deadline = time.time() + 60
                    while time.time() < deadline and not produced.is_file():
                        time.sleep(1.0)
                    if not produced.is_file():
                        logger.warning("  TIMEOUT %s (is the editor in front?)", name)
                        continue
                    time.sleep(1.0)  # let the writer close it
                    target = out_dir / f"{name}.png"
                    shutil.move(str(produced), str(target))
                    taken.append(target)
                    logger.info("  %s", target.name)
    finally:
        _run_in_editor(UNHIDE_SCRIPT.format(prefix=LABEL_PREFIX))
    return taken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "manifest", type=Path, help="pve_export_manifest.json of the run"
    )
    parser.add_argument(
        "--level",
        default=None,
        help="one level for all selected species (default: one level per species "
        f"under {DEFAULT_FOLDER})",
    )
    parser.add_argument("--species", nargs="*", default=None)
    parser.add_argument("--gap-m", type=float, default=8.0, help="between crowns")
    parser.add_argument(
        "--block-gap-m",
        type=float,
        default=30.0,
        help="label strip in front of a species",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="write the UE scripts, do not run them",
    )
    parser.add_argument(
        "--shots", type=Path, default=None, help="photograph each stand row into DIR"
    )
    parser.add_argument(
        "--settle", type=float, default=20.0, help="seconds after a camera move"
    )
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = gallery_records(manifest, args.species)
    if not records:
        logger.error("nothing to place")
        return 1
    groups = gallery_groups(records, args.level)
    scripts = []
    for level, name, group in groups:
        script = args.manifest.parent / f"growpy_pve_gallery_{name}.py"
        script.write_text(
            build_ue_script(
                group,
                level=level,
                gap_cm=args.gap_m * 100.0,
                block_gap_cm=args.block_gap_m * 100.0,
            ),
            encoding="utf-8",
        )
        scripts.append(script)
        logger.info("UE script: %s (%d meshes -> %s)", script, len(group), level)
    if args.script_only:
        return 0

    reports = []
    for script in scripts:
        report = run_gallery_script(script)
        if report is None:
            return 1
        reports.append(report)
        if args.shots:
            width, height = (int(v) for v in args.size.lower().split("x"))
            taken = take_row_shots(
                report, args.shots.resolve(), args.settle, (width, height)
            )
            logger.info("  %d shot(s) in %s", len(taken), args.shots)
    report_path = args.manifest.parent / "pve_gallery_report.json"
    report_path.write_text(json.dumps(reports, indent=1), encoding="utf-8")
    logger.info("report: %s", report_path)
    return 1 if any(r["missing"] for r in reports) else 0


def gallery_groups(
    records: list[dict], level: str | None
) -> list[tuple[str, str, list[dict]]]:
    """(level path, script name, records) per gallery level to build."""
    if level:
        return [(level, level.rsplit("/", 1)[1].lower(), records)]
    from growpy.io.unreal.pve_asset_script import camel_species

    groups = []
    for species in dict.fromkeys(r["species"] for r in records):
        path = f"{DEFAULT_FOLDER}/TreeGallery_{camel_species(species)}"
        groups.append((path, species, [r for r in records if r["species"] == species]))
    return groups


def run_gallery_script(script: Path) -> dict | None:
    """Run one generated gallery script in the editor; its report, or None."""
    from growpy.io.unreal import ue_remote

    result = ue_remote.run_file(str(script), timeout=3600)
    report = None
    for line in result.get("output", []):
        text = line.get("output", "") if isinstance(line, dict) else str(line)
        if "PVEGALLERY_REPORT " in text:
            report = json.loads(text.split("PVEGALLERY_REPORT ", 1)[1])
        elif "PVEGALLERY" in text:
            logger.info("  %s", text.split("LogPython:")[-1].strip())
    if not result.get("success"):
        logger.error("editor script failed: %s", result.get("result"))
        return None
    if report is None:
        logger.error("no report from the editor")
        return None
    logger.info(
        "%s: %d placed, %d not placed (over %d bones), %d missing, %.0f x %.0f m, "
        "saved=%s",
        report["level"],
        len(report["placed"]),
        len(report["skipped"]),
        MAX_BONES,
        len(report["missing"]),
        report["extent_m"][0],
        report["extent_m"][1],
        report["saved"],
    )
    for skipped in report["skipped"]:
        logger.warning("  not placed: %s (%d bones)", skipped["key"], skipped["bones"])
    for path in report["missing"]:
        logger.warning("  missing: %s", path)
    return report


if __name__ == "__main__":
    sys.exit(main())

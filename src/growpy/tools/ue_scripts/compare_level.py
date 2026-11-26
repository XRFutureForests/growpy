# ruff: noqa: E501, UP031, E741 -- ported line for line from the editor scripts that made
# the 2026-11 compare boards; reflowing them is not worth a behaviour slip
"""Compare level from a resolved set (growpy-ue-compare; runs inside the editor).

One row per source, trees 10 m apart, each with a label (name, measured height and
crown width), a sun and sky, a ground plane and the studio dome (a 2 km unlit
sphere: backdrop and floor in one surface, owner 2026-11-17). No wind (photo
level). Prints COMPARE lines; writes <out>/compare_level.json.

Reads the job JSON whose path the caller passes as the global JOB (runpy
init_globals): level, rows (label, optional, trees with asset and tag),
assembly_tris, out. The editor's Python has no growpy: the set was resolved
by growpy-ue-compare. Ported from build_compare_conifers.py (2026-11-13..19).
"""

import json
import os
import re

import unreal

if not globals().get("JOB"):
    raise RuntimeError("compare_level.py: no JOB; run it through growpy-ue-compare")
with open(globals()["JOB"], encoding="utf-8") as _fh:
    job = json.load(_fh)

LEVEL = job["level"]
OUT = os.path.join(job["out"], "compare_level.json")
T3D_DIR = os.path.join(job["out"], "t3d")
GAP = 1000.0
ROW_GAP = 2500.0
SUN_ROTATION = {
    "roll": 180.0,
    "pitch": -11.1,
    "yaw": -35.3,
}  # as L_Release1 (ECOSENSE light)
SKY = "/Engine/EngineSky/BP_Sky_Sphere.BP_Sky_Sphere_C"
PREFIX = "COMPARE_"
BACKDROP = "/Game/Developers/Max/LiveCheck/M_StudioBackdrop"

eal = unreal.EditorAssetLibrary
els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
lvl = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
zero = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)

# an optional row (an arm that may not be exported yet) drops out when none of its assets exist
ROWS = [
    (r["label"], r["trees"])
    for r in job["rows"]
    if not r.get("optional")
    or any(eal.does_asset_exist(t["asset"]) for t in r["trees"])
]


def open_level():
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError(
            "unsaved map changes: switching levels would block on a save dialog"
        )
    if eal.does_asset_exist(LEVEL):
        lvl.load_level(LEVEL)
    elif not lvl.new_level(LEVEL, False):
        raise RuntimeError("could not create " + LEVEL)
    for a in els.get_all_level_actors():
        if a.get_actor_label().startswith(PREFIX):
            els.destroy_actor(a)


def spawn(cls, label, loc, rot=zero):
    a = els.spawn_actor_from_class(
        unreal.load_class(None, cls) if isinstance(cls, str) else cls, loc, rot
    )
    a.set_actor_label(PREFIX + label)
    return a


def label(words, x, y):
    a = spawn(
        unreal.TextRenderActor,
        "Label_%d_%d" % (x, y),
        unreal.Vector(x, y, 150.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0),
    )
    c = a.get_editor_property("text_render")
    c.set_text(words)
    c.set_world_size(80.0)
    c.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)


def backdrop_material():
    """Unlit, two-sided, emissive = scalar parameter Brightness (the studio cyclorama's surface)."""
    if eal.does_asset_exist(BACKDROP):
        return unreal.load_asset(BACKDROP)
    folder, name = BACKDROP.rsplit("/", 1)
    m = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.Material, unreal.MaterialFactoryNew()
    )
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    mel = unreal.MaterialEditingLibrary
    p = mel.create_material_expression(
        m, unreal.MaterialExpressionScalarParameter, -300, 0
    )
    p.set_editor_property("parameter_name", "Brightness")
    p.set_editor_property("default_value", 4.0)
    mel.connect_material_property(p, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    eal.save_asset(BACKDROP)
    return m


def studio(center):
    """Owner 2026-11-17: review photos on a white / light grey studio backdrop, not black sky and grey floor.
    A 2 km unlit dome around the level is backdrop and floor in one surface (compare_capture.py shows it and leaves
    the ground out); a sky light captures the dome, so it also lights the trees evenly like a light tent."""
    dome = spawn(unreal.StaticMeshActor, "Studio", center)
    smc = dome.static_mesh_component
    smc.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Sphere.Sphere"))
    smc.set_material(0, backdrop_material())
    smc.set_editor_property("cast_shadow", False)
    dome.set_actor_scale3d(unreal.Vector(4000.0, 4000.0, 4000.0))
    sky = spawn(unreal.SkyLight, "StudioSky", center)
    slc = sky.get_component_by_class(unreal.SkyLightComponent)
    slc.set_editor_property("intensity", 1.0)
    slc.set_editor_property("real_time_capture", True)
    slc.recapture_sky()


def part_tris(part_path):
    """Triangles of one assembly part mesh: registry tags first, LOD0 count of the loaded mesh as fallback."""
    pkg = part_path.split(".")[0]
    ad = eal.find_asset_data(pkg)
    tags = {}
    for tag in ("Triangles", "NaniteTriangles", "Nanite Triangles", "Vertices"):
        v = ad.get_tag_value(tag)
        if v:
            tags[tag] = int(str(v).replace(",", ""))
    if "Triangles" not in tags:
        m = eal.load_asset(pkg)
        try:
            tags["lod0"] = int(m.get_num_triangles(0))
        except Exception:
            pass
    return tags


def assembly_tris(mesh, path, tag):
    """E111 yardstick (2026-11-18): sum over Nanite assembly instances of each part mesh's triangles, the
    same rule as the plan's 'planned triangles'. Instances per part from the T3D Nodes (PartIndex), parts from the
    T3D Parts (mesh object paths), as the 2026-09-15 MegaPlants audit read them."""
    t3d = os.path.join(T3D_DIR, "%s_%s.t3d" % (tag, path.rsplit("/", 1)[1]))
    os.makedirs(os.path.dirname(t3d), exist_ok=True)
    task = unreal.AssetExportTask()
    task.object, task.filename, task.exporter = mesh, t3d, unreal.ObjectExporterT3D()
    task.automated, task.prompt, task.replace_identical = True, False, True
    unreal.Exporter.run_asset_export_task(task)
    raw = open(t3d, "rb").read()
    text = (
        raw.decode("utf-16")
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
        else raw.decode("utf-8", "replace")
    )
    counts = {}
    for k in re.findall(r"PartIndex=(\d+)", text):
        counts[int(k)] = counts.get(int(k), 0) + 1
    i = text.find("Parts=(")
    parts = re.findall(r"MeshObjectPath=\"?([^\",)]+)", text[i:]) if i >= 0 else []
    if not parts:
        parts = re.findall(r"(/Game/[^\"',)\s]+SKM_[^\"',)\s]+)", text)
    rows, total = [], 0
    for k, p in enumerate(parts):
        t = part_tris(p)
        n = counts.get(k, 0)
        tri = t.get(
            "NaniteTriangles",
            t.get("Nanite Triangles", t.get("Triangles", t.get("lod0", 0))),
        )
        total += n * tri
        rows.append({"part": p.rsplit("/", 1)[-1], "instances": n, "tris": t})
    return {
        "parts": len(parts),
        "instances": sum(counts.values()),
        "assembly_tris": total,
        "part_rows": rows,
    }


def main():
    open_level()
    sun = spawn(
        unreal.DirectionalLight,
        "Sun",
        unreal.Vector(0, 0, 0),
        unreal.Rotator(**SUN_ROTATION),
    )
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property(
        "intensity", 10.0
    )
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property(
        "atmosphere_sun_light", True
    )
    sky = spawn(SKY, "Sky", unreal.Vector(0, 0, 0))
    try:
        sky.set_editor_property("directional_light_actor", sun)
    except Exception:
        pass
    # no BP_GlobalFoliageActor: it drives the foliage MPC (Health) and turned leaves into squares in photos;
    # compare_capture.py sets Health and the summer Season Strength on the MPC itself, Seasons stays ON
    width = GAP * max(len(t) for _, t in ROWS)
    ground = spawn(
        unreal.StaticMeshActor,
        "Ground",
        unreal.Vector(len(ROWS) * ROW_GAP / 2, width / 2, 0),
    )
    ground.static_mesh_component.set_static_mesh(
        unreal.load_asset("/Engine/BasicShapes/Plane.Plane")
    )
    ground.set_actor_scale3d(
        unreal.Vector((len(ROWS) * ROW_GAP + 20000) / 100, (width + 20000) / 100, 1)
    )
    spawn(unreal.PlayerStart, "PlayerStart", unreal.Vector(-1500, width / 2, 100))
    studio(unreal.Vector(len(ROWS) * ROW_GAP / 2, width / 2, 0))
    out = []
    for r, (source, trees) in enumerate(ROWS):
        x = r * ROW_GAP
        label(source.upper(), x, -800.0)
        for i, tree in enumerate(trees):
            path, tag = tree["asset"], tree["tag"]
            row = {"source": source, "asset": path}
            mesh = eal.load_asset(path) if eal.does_asset_exist(path) else None
            if mesh is None:
                row["error"] = "missing"
            else:
                e = mesh.get_bounds().box_extent
                row["height_m"] = round(2 * e.z / 100, 2)
                row["width_m"] = round(2 * max(e.x, e.y) / 100, 2)
                ad = eal.find_asset_data(path)
                for key, rtag in (
                    ("bones", "Bones"),
                    ("triangles", "Triangles"),
                    ("vertices", "Vertices"),
                ):
                    value = ad.get_tag_value(
                        rtag
                    )  # registry tags, as dump_catalog_bones.py
                    if value:
                        row[key] = int(str(value).replace(",", ""))
                if (
                    "triangles" not in row
                ):  # no registry tag: count LOD0 off the loaded mesh
                    try:
                        row["triangles"] = (
                            int(mesh.get_num_triangles(0))
                            if hasattr(mesh, "get_num_triangles")
                            else None
                        )
                    except Exception:
                        pass
                y = i * GAP
                if job.get("assembly_tris"):
                    try:
                        row["assembly"] = assembly_tris(mesh, path, tag)
                    except (
                        Exception
                    ) as exc:  # the photos still run if the T3D read fails
                        row["assembly_error"] = repr(exc)
                # plain skeletal mesh actor, no wind: the first build with 33 wind trees and no bone
                # budget crashed the editor in DynamicWind at save (2026-11-14); photos need no wind
                els.spawn_actor_from_object(
                    mesh, unreal.Vector(x, y, 0), zero
                ).set_actor_label(PREFIX + tag + "_" + path.rsplit("/", 1)[1])
                label(
                    "%s\n%.1f m tall, %.1f m wide"
                    % (
                        path.rsplit("_", 2)[-2] + "_" + path.rsplit("_", 1)[-1],
                        row["height_m"],
                        row["width_m"],
                    ),
                    x - 300,
                    y,
                )
            out.append(row)
            print("COMPARE", json.dumps(row))
    saved = bool(unreal.EditorLoadingAndSavingUtils.save_current_level())
    os.makedirs(job["out"], exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("COMPARE done %d trees, saved %s -> %s" % (len(out), saved, OUT))


main()

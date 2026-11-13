"""Preview renders for the catalog print: every twig prototype and each species' bark.

Writes <project>/Saved/growpy_catalog_previews/<species>/twig_<name> and bark (PNG data,
no extension) plus index.json.
Run it THREE times through remote Python (growpy.io.unreal.ue_remote.run_file), a few
seconds apart: the first run builds the sandbox level and requests every texture and
Nanite page (a capture inside one call never ticks the engine, so meshes loaded from
disk still show coarse clusters); the later runs capture and overwrite the PNGs.

Sandbox level /Game/Developers/Max/CatalogPreview/L_CatalogPreview, never the twin's.
"""

import json
import math
import os

import unreal

FOLIAGE = "/Game/Generated/Trees/Foliage"
MATERIALS = "/Game/Generated/Trees/Materials"
LEVEL = "/Game/Developers/Max/CatalogPreview/L_CatalogPreview"
MPC = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MaterialFunctions/"
    "MPC_GlobalFoliageActor"
)
OUT = os.path.join(unreal.Paths.project_saved_dir(), "growpy_catalog_previews")
RES = 1024
SPACING = 1500.0  # cm between preview slots
STEM_DBH_CM = 40.0

els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eal = unreal.EditorAssetLibrary
zero = unreal.Rotator(0.0, 0.0, 0.0)

if eal.does_asset_exist(LEVEL):
    les.load_level(LEVEL)
else:
    les.new_level(LEVEL)
    for cls, rot in (
        (unreal.DirectionalLight, unreal.Rotator(roll=0.0, pitch=-40.0, yaw=35.0)),
        (unreal.SkyLight, zero),
        (unreal.SkyAtmosphere, zero),
    ):
        els.spawn_actor_from_class(cls, unreal.Vector(0, 0, 3000), rot)
world = unreal.EditorLevelLibrary.get_editor_world()
assert world.get_path_name().startswith(LEVEL), world.get_path_name()
for a in els.get_all_level_actors():
    if isinstance(a, unreal.SkyLight):
        a.light_component.set_editor_property("real_time_capture", True)
unreal.SystemLibrary.execute_console_command(
    world, "r.TextureStreaming 0"
)  # full-resolution twig and bark textures
mpc = unreal.load_asset(MPC)
if mpc:  # the foliage master reads Health here; above 1 every masked leaf is a square
    unreal.MaterialLibrary.set_scalar_parameter_value(world, mpc, "Health", 1.0)


def twig_meshes(species):
    out = []
    for folder in sorted(
        eal.list_assets(f"{FOLIAGE}/{species}", recursive=False, include_folder=True)
    ):
        name = folder.rstrip("/").split("/")[-1]
        path = f"{FOLIAGE}/{species}/{name}/StaticMeshes/SM_{name}_ZUP"
        if eal.does_asset_exist(path):
            out.append((name, path))
    return out


def triangles(mesh):
    try:
        return int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 -- informative only
        return None


rt = unreal.RenderingLibrary.create_render_target2d(
    world, RES, RES, unreal.TextureRenderTargetFormat.RTF_RGBA8
)
cap = els.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 0), zero)
cc = cap.capture_component2d
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
cc.set_editor_property("texture_target", rt)
cc.set_editor_property("fov_angle", 30.0)


def shoot(center, radius, folder, name, pitch=-25.0, yaw=35.0):
    dist = 1.15 * radius / math.tan(math.radians(15.0))
    p, y = math.radians(-pitch), math.radians(yaw)
    loc = unreal.Vector(
        center.x - dist * math.cos(p) * math.cos(y),
        center.y - dist * math.cos(p) * math.sin(y),
        center.z + dist * math.sin(p),
    )
    cap.set_actor_location_and_rotation(
        loc, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), False, False
    )
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, folder, name)


existing = {
    a.get_actor_label(): a
    for a in els.get_all_level_actors()
    if a.get_actor_label().startswith("PREV_")
}
index = {}
species_list = sorted(
    f.rstrip("/").split("/")[-1]
    for f in eal.list_assets(FOLIAGE, recursive=False, include_folder=True)
)
for row, sp in enumerate(species_list):
    folder = os.path.join(OUT, sp)
    os.makedirs(folder, exist_ok=True)
    entry = {"twigs": [], "bark": None}
    for col, (name, path) in enumerate(twig_meshes(sp)):
        label = f"PREV_{sp}_{name}"
        mesh = unreal.load_asset(path)
        actor = existing.get(label)
        if actor is None:
            actor = els.spawn_actor_from_class(
                unreal.StaticMeshActor,
                unreal.Vector(col * SPACING, row * SPACING, 200.0),
                zero,
            )
            actor.set_actor_label(label)
            actor.static_mesh_component.set_static_mesh(mesh)
        origin, extent = actor.get_actor_bounds(False)
        shoot(origin, max(extent.x, extent.y, extent.z, 1.0), folder, f"twig_{name}")
        entry["twigs"].append(
            {
                "name": name,
                "mesh": path,
                "png": f"twig_{name}",  # export_render_target writes no extension
                "size_cm": [
                    round(2 * extent.x, 1),
                    round(2 * extent.y, 1),
                    round(2 * extent.z, 1),
                ],
                "triangles": triangles(mesh),
            }
        )
    bark = f"{MATERIALS}/{sp}/MI_{sp}_bark"
    if eal.does_asset_exist(bark):
        label = f"PREV_{sp}_bark"
        actor = existing.get(label)
        if actor is None:
            x = -2 * SPACING
            actor = els.spawn_actor_from_class(
                unreal.StaticMeshActor, unreal.Vector(x, row * SPACING, 0.0), zero
            )
            actor.set_actor_label(label)
            comp = actor.static_mesh_component
            comp.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cylinder"))
            actor.set_actor_scale3d(
                unreal.Vector(STEM_DBH_CM / 100.0, STEM_DBH_CM / 100.0, 1.6)
            )
            comp.set_material(0, unreal.load_asset(bark))
            for i, v in enumerate(
                [STEM_DBH_CM, STEM_DBH_CM / 100.0, 25.0]
            ):  # trunk master: dbh_cm, DBH m, height m
                comp.set_default_custom_primitive_data_float(i, v)
        origin, extent = actor.get_actor_bounds(False)
        shoot(
            origin, max(extent.x, extent.z) * 0.6, folder, "bark", pitch=-5.0, yaw=0.0
        )
        mi = unreal.load_asset(bark)
        parent = mi.get_editor_property("parent")
        entry["bark"] = {
            "material": bark,
            "parent": parent.get_path_name() if parent else None,
            "png": "bark",
        }
    index[sp] = entry
    with open(os.path.join(folder, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=1)
els.destroy_actor(cap)
les.save_current_level()
print(f"PREVIEWS {len(index)} species -> {OUT}")

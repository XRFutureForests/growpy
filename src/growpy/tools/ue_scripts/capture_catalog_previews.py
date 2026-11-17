"""Preview renders for the catalog print: the twig prototypes and each species' bark.

Writes <project>/Saved/growpy_catalog_previews/<species>/twig_<name> and bark (PNG data,
no extension), a <name>_mask beside each (only the subject rendered; alpha = inverse
opacity, so the print can put the subject on white) and index.json. A twig is marked
"used" when a catalog graph references it. The bark is shot on the species' own catalog
trunk (r07, the height nearest 20 m, from data/input/tree_catalog.toml) at eye height,
so the bark shows with the trunk's real wraps and DBH instead of on a test cylinder.
Run it THREE times through remote Python (growpy.io.unreal.ue_remote.run_file), a few
seconds apart: the first run builds the sandbox level and requests every texture and
Nanite page (a capture inside one call never ticks the engine, so meshes loaded from
disk still show coarse clusters); the later runs capture and overwrite the PNGs.

Sandbox level /Game/Developers/Max/CatalogPreview/L_CatalogPreview, never the twin's.
"""

import json
import math
import os
import tomllib

import unreal

FOLIAGE = "/Game/Generated/Trees/Foliage"
MATERIALS = "/Game/Generated/Trees/Materials"
GRAPHS = "/Game/Generated/Trees/Graphs/"
LEVEL = "/Game/Developers/Max/CatalogPreview/L_CatalogPreview"
MANIFEST = os.environ.get(
    "GROWPY_TREE_CATALOG", "D:/Git/work/growpy/data/input/tree_catalog.toml"
)
MPC = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MaterialFunctions/"
    "MPC_GlobalFoliageActor"
)
OUT = os.path.join(unreal.Paths.project_saved_dir(), "growpy_catalog_previews")
RES = 1024
SPACING = 1500.0  # cm between preview slots
BARK_ROW_X = -6000.0  # the trunks stand apart from the twigs
# One editor cannot hold every species' twigs plus the catalog trunks (99 % commit,
# 2026-11-13): run the twigs in one session and the bark one species per session.
# The caller says which in <OUT>/parts.json, e.g. {"parts": ["bark"], "species":
# "norway_spruce"} (a file, because the batch editor does not inherit the caller's env).
try:
    with open(os.path.join(OUT, "parts.json"), encoding="utf-8") as fh:
        _sel = json.load(fh)
except (OSError, ValueError):
    _sel = {}
PARTS = set(_sel.get("parts", ["twigs", "bark"]))
ONLY = _sel.get("species")

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


def used_by_catalog(path):
    refs = eal.find_package_referencers_for_asset(path, False)
    return any(str(r).startswith(GRAPHS) for r in refs)


def triangles(mesh):
    try:
        return int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 -- informative only
        return None


def catalog_trunks():
    """Species -> (mesh path, DBH cm, height m) of the r07 tree nearest 20 m."""
    try:
        with open(MANIFEST, "rb") as fh:
            trees = tomllib.load(fh)["trees"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        unreal.log_warning(f"no tree catalog manifest ({exc}); no bark shots")
        return {}
    out = {}
    for species, by_id in trees.items():
        r07 = [t for t in by_id.values() if t.get("radius") == 7]
        if not r07:
            continue
        t = min(r07, key=lambda t: abs(t["height_m"] - 20.0))
        # the skinned mesh: loading the static twin builds its Nanite foliage (99 % commit)
        mesh = t.get("mesh")
        out[species] = (mesh, float(t["dbh_cm"]), float(t["height_m"]))
    return out


rt = unreal.RenderingLibrary.create_render_target2d(
    world, RES, RES, unreal.TextureRenderTargetFormat.RTF_RGBA8
)
cap = els.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 0), zero)
cc = cap.capture_component2d
cc.set_editor_property("texture_target", rt)


def mem(step):
    """Log this process's commit and the system's, to find what fills memory."""
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t)
            for n in (
                "PeakWorkingSetSize WorkingSetSize QuotaPeakPagedPoolUsage "
                "QuotaPagedPoolUsage QuotaPeakNonPagedPoolUsage QuotaNonPagedPoolUsage "
                "PagefileUsage PeakPagefileUsage PrivateUsage"
            ).split()
        ]

    c = PMC()
    c.cb = ctypes.sizeof(c)
    ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb
    )
    print(f"MEM {step}: private {c.PrivateUsage / 2**30:.1f} GB")


def sharpen(materials):
    """Full mips for these materials' textures only; r.TextureStreaming 0 with the
    catalog trunks loaded ran the editor out of memory (98 % commit, 2026-11-13)."""
    for m in materials:
        if m is None:
            continue
        textures = list(
            unreal.MaterialEditingLibrary.get_used_textures(m.get_base_material())
        )
        while isinstance(m, unreal.MaterialInstance):  # overrides up the chain
            textures += [
                p.parameter_value
                for p in m.get_editor_property("texture_parameter_values")
            ]
            m = m.get_editor_property("parent")
        for tex in textures:
            if tex:
                tex.set_force_mip_levels_to_be_resident(600.0, 0)


def shoot(actor, loc, rot, fov, folder, name):
    """The view as rendered, then the subject alone for the white-background mask."""
    cap.set_actor_location_and_rotation(loc, rot, False, False)
    cc.set_editor_property("fov_angle", fov)
    cc.set_editor_property(
        "capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    )
    cc.set_editor_property(
        "primitive_render_mode",
        unreal.SceneCapturePrimitiveRenderMode.PRM_RENDER_SCENE_PRIMITIVES,
    )
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, folder, name)
    mem(f"{name} colour")
    # SceneColor (HDR) carries inverse opacity in alpha: 1 where nothing was drawn
    cc.set_editor_property(
        "capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR
    )
    cc.set_editor_property(
        "primitive_render_mode",
        unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST,
    )
    cc.clear_show_only_components()  # show_only_actors is not editable from Python
    cc.show_only_actor_components(actor)
    cc.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, folder, f"{name}_mask")


def orbit(center, radius, pitch=-25.0, yaw=35.0):
    dist = 1.15 * radius / math.tan(math.radians(15.0))
    p, y = math.radians(-pitch), math.radians(yaw)
    loc = unreal.Vector(
        center.x - dist * math.cos(p) * math.cos(y),
        center.y - dist * math.cos(p) * math.sin(y),
        center.z + dist * math.sin(p),
    )
    return loc, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


existing = {
    a.get_actor_label(): a
    for a in els.get_all_level_actors()
    if a.get_actor_label().startswith("PREV_")
}
for label in [k for k in existing if k.endswith("_bark")]:  # the old test cylinders
    els.destroy_actor(existing.pop(label))
trunks = catalog_trunks()
index = {}
species_list = sorted(
    f.rstrip("/").split("/")[-1]
    for f in eal.list_assets(FOLIAGE, recursive=False, include_folder=True)
)
for row, sp in enumerate(species_list):
    if ONLY and sp != ONLY:
        continue
    folder = os.path.join(OUT, sp)
    os.makedirs(folder, exist_ok=True)
    try:  # keep the part this run does not redo
        with open(os.path.join(folder, "index.json"), encoding="utf-8") as fh:
            entry = json.load(fh)
    except (OSError, ValueError):
        entry = {"twigs": [], "bark": None}
    if "twigs" in PARTS:
        entry["twigs"] = []
    for col, (name, path) in enumerate(twig_meshes(sp) if "twigs" in PARTS else []):
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
        mem(f"{name} loaded")
        sharpen(m.material_interface for m in mesh.static_materials)
        mem(f"{name} sharpened")
        origin, extent = actor.get_actor_bounds(False)
        loc, rot = orbit(origin, max(extent.x, extent.y, extent.z, 1.0))
        shoot(actor, loc, rot, 30.0, folder, f"twig_{name}")
        mem(f"{name} shot")
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
                "used": used_by_catalog(path),
            }
        )
    bark = f"{MATERIALS}/{sp}/MI_{sp}_bark"
    trunk = trunks.get(sp)
    if (
        "bark" in PARTS
        and eal.does_asset_exist(bark)
        and trunk
        and eal.does_asset_exist(trunk[0] or "")
    ):
        mesh_path, dbh_cm, height_m = trunk
        label = f"PREV_{sp}_trunk"
        actor = existing.get(label)
        if actor is None:
            mesh = unreal.load_asset(mesh_path)
            loc = unreal.Vector(BARK_ROW_X, row * SPACING, 0.0)
            if isinstance(mesh, unreal.SkeletalMesh):
                actor = els.spawn_actor_from_class(unreal.SkeletalMeshActor, loc, zero)
                comp = actor.skeletal_mesh_component
                comp.set_skeletal_mesh_asset(mesh)
            else:
                actor = els.spawn_actor_from_class(unreal.StaticMeshActor, loc, zero)
                comp = actor.static_mesh_component
                comp.set_static_mesh(mesh)
            actor.set_actor_label(label)
            # the trunk master reads dbh_cm, DBH m, height m from custom primitive data
            for i, v in enumerate([dbh_cm, dbh_cm / 100.0, height_m]):
                comp.set_default_custom_primitive_data_float(i, v)
        sharpen([unreal.load_asset(bark)])
        # eye height, about 4 stem diameters off: a stem section filling the frame
        base = actor.get_actor_location()
        dist = max(4.0 * dbh_cm, 80.0)
        shoot(
            actor,
            unreal.Vector(base.x - dist, base.y, base.z + 150.0),
            zero,
            40.0,
            folder,
            "bark",
        )
        mi = unreal.load_asset(bark)
        parent = mi.get_editor_property("parent")
        entry["bark"] = {
            "material": bark,
            "parent": parent.get_path_name() if parent else None,
            "png": "bark",
            "trunk": mesh_path,
            "dbh_cm": dbh_cm,
        }
    index[sp] = entry
    with open(os.path.join(folder, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=1)
els.destroy_actor(cap)
if "bark" not in PARTS:  # never save the trunks: the next session would load them all
    les.save_current_level()
print(f"PREVIEWS {len(index)} species -> {OUT}")

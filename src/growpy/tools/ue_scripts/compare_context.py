# ruff: noqa: E501, UP031, E741 -- ported line for line from the editor scripts that made
# the 2026-11 compare boards; reflowing them is not worth a behaviour slip
"""Backdrop of the built compare level (growpy-ue-compare; runs inside the editor).

MODE (runpy init_globals): light (the review convention: the studio dome at its
material default), dark (the dome dimmed), forest (a dark ground plane and catalog
neighbour trees 12-20 m behind each tree, on the side away from the camera, which
sits at -X), or save (save the scratch level). Every context actor is labelled
COMPARE_ctx_* so the next build or context clears it; the dome change is a dynamic
material instance (nothing saved). The neighbours come from the job JSON (JOB).
Ported from fleck_ctx_ue.py (needle-fleck check, 2026-11-19).
"""

import json

import unreal

if not globals().get("JOB") or globals().get("MODE") not in (
    "light",
    "dark",
    "forest",
    "save",
):
    raise RuntimeError(
        "compare_context.py: needs JOB and MODE light|dark|forest|save; run it through growpy-ue-compare"
    )
MODE = globals()["MODE"]
with open(globals()["JOB"], encoding="utf-8") as _fh:
    job = json.load(_fh)

els = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
NEIGHBOURS = [(path, float(dx), float(dy)) for path, dx, dy in job["neighbours"]]
BRIGHT = {"light": None, "dark": 0.25, "forest": 1.2}
BACKDROP = "/Game/Developers/Max/LiveCheck/M_StudioBackdrop"


def actors():
    return els.get_all_level_actors()


def clear_ctx():
    for a in actors():
        if a.get_actor_label().startswith("COMPARE_ctx_"):
            els.destroy_actor(a)


def dome():
    for a in actors():
        if a.get_actor_label().endswith("Studio") and isinstance(
            a, unreal.StaticMeshActor
        ):
            return a
    return None


if MODE == "save":
    print("COMPARE ctx saved", unreal.EditorLoadingAndSavingUtils.save_current_level())
else:
    clear_ctx()
    d = dome()
    smc = d.static_mesh_component if d else None
    base = unreal.load_asset(BACKDROP)
    if smc and base:
        if BRIGHT[MODE] is None:
            smc.set_material(0, base)
        else:
            mid = smc.create_dynamic_material_instance(0, base)
            mid.set_scalar_parameter_value("Brightness", BRIGHT[MODE])
    if MODE == "forest":
        trees = [
            a
            for a in actors()
            if a.get_actor_label().startswith("COMPARE_")
            and isinstance(a, unreal.SkeletalMeshActor)
            and not a.get_actor_label().startswith("COMPARE_ctx_")
        ]
        ground = els.spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(0.0, 0.0, -2.0)
        )
        ground.set_actor_label("COMPARE_ctx_ground")
        ground.static_mesh_component.set_static_mesh(
            unreal.load_asset("/Engine/BasicShapes/Plane.Plane")
        )
        ground.set_actor_scale3d(unreal.Vector(2000.0, 2000.0, 1.0))
        gm = ground.static_mesh_component.create_dynamic_material_instance(
            0, unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
        )
        if gm:
            gm.set_vector_parameter_value(
                "Color", unreal.LinearColor(0.035, 0.03, 0.02, 1.0)
            )
        n = 0
        for t in trees:
            p = t.get_actor_location()
            for path, dx, dy in NEIGHBOURS:
                mesh = unreal.load_asset(path)
                if mesh is None:
                    continue
                a = els.spawn_actor_from_class(
                    unreal.SkeletalMeshActor, unreal.Vector(p.x + dx, p.y + dy, p.z)
                )
                a.set_actor_label("COMPARE_ctx_n%d" % n)
                a.skeletal_mesh_component.set_skinned_asset_and_update(mesh)
                n += 1
        print(
            "COMPARE ctx forest: %d neighbours behind %d trees, ground plane"
            % (n, len(trees))
        )
    print("COMPARE ctx", MODE, "dome brightness", BRIGHT[MODE])
